#!/usr/bin/env python3
"""Non-destructive workspace inventory with optional private history; no delete mode."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid


SKIP = {
    ".git", ".cache", ".cargo", ".nix", ".direnv", ".venv", "venv",
    "secrets", "env", "state", "logs", "node_modules", "target", "dist",
    "build", ".next", "result", "vendor",
}
OUTPUTS = {"target", "node_modules", "dist", "build", ".next"}
HIDDEN_ROOTS = {".worktrees", ".paseo-worktrees"}


class CheckError(RuntimeError):
    pass


def overlaps(left, right):
    return left == right or left in right.parents or right in left.parents


def inside(path, root):
    return path == root or root in path.parents


def local_directory(value, root=None):
    path = Path(value).expanduser().absolute()
    if not path.is_dir() or path.resolve() != path:
        raise CheckError(f"Not a real, non-symlink directory: {path}")
    if root is not None and not inside(path, root):
        raise CheckError(f"Directory lies outside the configured root: {path}")
    return path


def history_directory(value=None):
    state = Path(os.environ.get("XDG_STATE_HOME", str(Path.home()/".local/state")))
    return Path(value).expanduser().absolute() if value else state.absolute()/"node-cleanup/history"


def preserved_paths(history):
    paths = {Path.home()/".cache/build-metrics", history, history_directory().parent,
             Path.home()/".local/libexec/cargo-metrics"}
    if os.environ.get("CARGO_METRICS_DIR"):
        paths.add(Path(os.environ["CARGO_METRICS_DIR"]).expanduser().absolute())
    # Resolve aliases for protection only, never for traversal.
    return tuple(sorted({p.resolve() for p in paths} | paths))


def save_history(report, directory):
    """Publish a complete immutable JSON document, never overwrite old history."""
    if directory.resolve() != directory:
        raise CheckError("History directory must not contain symlink or non-canonical components")
    # mkdir(parents=True) would give intermediate directories default permissions.
    missing = []
    path = directory
    while not path.exists():
        missing.append(path)
        path = path.parent
    for path in reversed(missing):
        path.mkdir(mode=0o700, exist_ok=True)
    def verify_private(path):
        stat = path.stat()
        if path.is_symlink() or stat.st_uid != os.getuid() or stat.st_mode & 0o077:
            raise CheckError("History directory must be private (0700), owned, and not symlinked")
    verify_private(directory)
    day = directory/report["generated_at"][:10]
    day.mkdir(mode=0o700, exist_ok=True)
    verify_private(day)
    destination = day/(report["report_id"] + ".json")
    temporary = day/("." + str(uuid.uuid4()) + ".tmp")
    report["history"] = {"enabled": True, "saved": True, "path": str(destination)}
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "w") as output:
            json.dump(report, output, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        # Hard-link publication is atomic and refuses an existing destination.
        os.link(temporary, destination)
        parent_fd = os.open(day, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


class Inventory:
    def __init__(self, root, paseo=None, mde_roots=(), seconds=120, max_entries=50000,
                 usage_paths=(), protected_paths=None):
        self.root = root
        self.paseo = paseo
        self.mde_roots = tuple(mde_roots)
        self.usage_paths = tuple(usage_paths)
        self.protected_paths = (preserved_paths(history_directory()) if protected_paths is None
                                else tuple(protected_paths))
        self.deadline = time.monotonic() + seconds
        self.max_entries = max_entries
        self.entries = 0
        self.warnings = []
        self.complete = True
        self.active_paths = []
        self.workspace_paths = []
        self.activity_known = False
        self.env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0"}
        for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR",
                     "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES"):
            self.env.pop(name, None)

    def command(self, args, timeout=10):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise CheckError("Report time budget exhausted")
        try:
            result = subprocess.run(
                args, capture_output=True, env=self.env,
                timeout=min(timeout, remaining), check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise CheckError(f"{Path(args[0]).name} check unavailable or timed out") from error
        if result.returncode:
            # Do not print command diagnostics: providers can include private state.
            raise CheckError(f"{Path(args[0]).name} check failed (exit {result.returncode})")
        return result.stdout

    def activity(self):
        if not self.paseo:
            self.warnings.append("Paseo activity was not configured; all work is protected.")
            return
        try:
            workspaces = json.loads(self.command(
                [str(self.paseo), "workspace", "ls", "--background", "--json"], 20))
            agents = json.loads(self.command(
                [str(self.paseo), "ls", "-a", "-g", "--json"], 20))
            if not isinstance(workspaces, list) or not isinstance(agents, list):
                raise CheckError("Unexpected Paseo listing schema")
            for workspace in workspaces:
                if not isinstance(workspace, dict) or not isinstance(workspace.get("cwd"), str):
                    raise CheckError("Paseo workspace has no usable path")
                self.workspace_paths.append(self.activity_path(workspace["cwd"]))
            for agent in agents:
                if not isinstance(agent, dict) or agent.get("status") not in {"running", "idle", "closed"}:
                    raise CheckError("Unknown Paseo agent status")
                if agent["status"] != "closed":
                    if not isinstance(agent.get("cwd"), str):
                        raise CheckError("Active Paseo agent has no usable path")
                    self.active_paths.append(self.activity_path(agent["cwd"]))
            self.activity_known = True
        except (CheckError, ValueError, TypeError):
            self.warnings.append("Paseo activity could not be established; all work is protected.")

    @staticmethod
    def activity_path(value):
        # Paseo's agent list abbreviates this user's home, unlike workspace ls.
        # Do not interpret shell variables or arbitrary relative paths.
        path = Path.home()/value[2:] if value.startswith("~/") else Path(value)
        if not path.is_absolute():
            raise CheckError("Paseo returned a relative workspace path")
        # Resolve references for comparison only; never traverse these paths.
        return path.resolve()

    def discover(self):
        repositories = set()
        stack = [(self.root, 0)]
        try:
            while stack:
                directory, depth = stack.pop()
                if any(inside(directory, p) for p in self.protected_paths):
                    continue
                if time.monotonic() >= self.deadline:
                    raise CheckError("Discovery time budget exhausted")
                with os.scandir(directory) as entries:
                    children = []
                    has_git = False
                    for entry in entries:
                        self.entries += 1
                        if self.entries > self.max_entries:
                            raise CheckError("Discovery entry budget exhausted")
                        if entry.name == ".git" and not entry.is_symlink():
                            has_git = True
                        if entry.is_dir(follow_symlinks=False):
                            children.append(entry)
                if has_git:
                    repositories.add(directory)
                for entry in children:
                    if entry.name in SKIP:
                        continue
                    if entry.name.startswith(".") and entry.name not in HIDDEN_ROOTS:
                        continue
                    # A repository is one unit; find its additional worktrees below.
                    if has_git and entry.name != ".worktrees":
                        continue
                    if depth >= 8:
                        self.complete = False
                        warning = "Discovery depth limit reached; some non-Git subdirectories were not inventoried."
                        if warning not in self.warnings:
                            self.warnings.append(warning)
                        continue
                    stack.append((Path(entry.path), depth + 1))
            # Git owns the worktree registry, including worktrees outside .worktrees.
            for repo in sorted(repositories.copy()):
                try:
                    raw = self.git(repo, "worktree", "list", "--porcelain", "-z")
                    for field in raw.split(b"\0"):
                        if field.startswith(b"worktree "):
                            p = Path(os.fsdecode(field[9:]))
                            if inside(p, self.root) and not any(
                                    inside(p, protected) for protected in self.protected_paths):
                                repositories.add(local_directory(p, self.root))
                except CheckError:
                    self.complete = False
                    self.warnings.append(f"Worktree registry incomplete: {repo}")
        except (CheckError, OSError) as error:
            self.complete = False
            self.warnings.append(str(error) if isinstance(error, CheckError)
                                 else "A discovery directory could not be read")
        return sorted(repositories)

    def git(self, repo, *args):
        return self.command([
            "git", "--no-optional-locks", "-c", "core.fsmonitor=false",
            "-c", "core.untrackedCache=false", "-C", str(repo), *args,
        ])

    def git_state(self, repo):
        result = {"known": False, "dirty": None, "local_only_commits": None}
        try:
            result["dirty"] = bool(self.git(
                repo, "status", "--porcelain=v1", "-z", "--untracked-files=normal"))
            refs = self.git(repo, "for-each-ref", "--format=%(refname)", "refs/remotes/")
            if refs.strip():
                count = self.git(repo, "rev-list", "--count", "HEAD", "--branches", "--not", "--remotes")
                result["local_only_commits"] = int(count.strip())
            result["known"] = True
        except (CheckError, ValueError):
            pass
        return result

    def outputs(self, repo):
        found = []
        stack = [(repo, 0)]
        visited = 0
        while stack:
            directory, depth = stack.pop()
            if time.monotonic() >= self.deadline or visited >= 5000:
                return found, False
            try:
                with os.scandir(directory) as entries:
                    for entry in entries:
                        visited += 1
                        if visited > 5000:
                            return found, False
                        if not entry.is_dir(follow_symlinks=False):
                            continue
                        path = Path(entry.path)
                        if any(inside(path, p) for p in self.protected_paths):
                            continue
                        if entry.name in OUTPUTS:
                            found.append(path)
                        elif depth < 4 and entry.name not in SKIP and not entry.name.startswith("."):
                            # Other repositories are inventoried independently.
                            if not os.path.lexists(path/".git"):
                                stack.append((path, depth + 1))
            except OSError:
                return found, False
        return sorted(found), True

    def allocated_bytes(self, path):
        try:
            output = self.command(["du", "-s", "-B1", "-x", "--", str(path)], 15)
            return int(output.split(b"\t", 1)[0])
        except (CheckError, ValueError):
            return None

    def workspace(self, repo):
        git = self.git_state(repo)
        protected = []
        if any(overlaps(repo, p) for p in self.protected_paths):
            protected.append("historical_data_or_collector_overlap")
        if not self.activity_known:
            protected.append("activity_unknown")
        if any(overlaps(repo, p) for p in self.workspace_paths):
            protected.append("listed_paseo_workspace")
        if any(overlaps(repo, p) for p in self.active_paths):
            protected.append("running_or_idle_agent_reference")
        if any(inside(repo, p) for p in self.mde_roots):
            protected.append("mde_lifecycle_not_integrated")
        if not git["known"]:
            protected.append("git_state_unknown")
        if git["dirty"]:
            protected.append("dirty_or_untracked_work")
        if git["local_only_commits"] is None:
            protected.append("remote_tracking_coverage_unknown")
        elif git["local_only_commits"]:
            protected.append("commits_not_in_remote_tracking_refs")
        paths, outputs_complete = self.outputs(repo)
        artifacts = [{"path": str(p), "allocated_bytes": self.allocated_bytes(p),
                      "classification": ("protected_historical_data_overlap" if any(
                          overlaps(p, kept) for kept in self.protected_paths)
                          else "possible_build_output_not_verified_disposable")}
                     for p in paths]
        if not outputs_complete:
            protected.append("build_output_scan_incomplete")
        if any(a["allocated_bytes"] is None for a in artifacts):
            protected.append("size_check_incomplete")
        try:
            age = round(max(0, (time.time() - repo.stat().st_mtime)/86400), 1)
        except OSError:
            age = None
            protected.append("workspace_disappeared")
        return {"path": str(repo), "directory_metadata_age_days": age,
                "git": git, "artifacts": artifacts, "protected_reasons": protected,
                "disposition": "protected" if protected else "retirement_review_only",
                "deletion_permitted": False}

    def report(self):
        started = datetime.now(timezone.utc).isoformat()
        self.activity()
        # Sample explicitly configured shared caches before repository discovery
        # consumes the budget. Each du is independent: overlapping sizes are not additive.
        tracked_usage = []
        for path in self.usage_paths:
            try:
                if not os.path.lexists(path):
                    size, status = 0, "missing"
                else:
                    local_directory(path)
                    size = self.allocated_bytes(path)
                    status = "measured" if size is not None else "unavailable"
            except (CheckError, OSError):
                size, status = None, "unavailable"
            tracked_usage.append({"path": str(path), "allocated_bytes": size,
                                  "status": status, "method": "du_allocated_bytes",
                                  "observed_at": datetime.now(timezone.utc).isoformat(),
                                  "deletion_permitted": False})
        repositories = self.discover()
        records = [self.workspace(repo) for repo in repositories]
        if not self.complete:
            for record in records:
                record["protected_reasons"].append("discovery_incomplete")
                record["disposition"] = "protected"
        usage = shutil.disk_usage(self.root)
        checks_complete = self.complete and self.activity_known and all(
            entry["status"] != "unavailable" for entry in tracked_usage) and all(
            row["git"]["known"] and not any(reason in row["protected_reasons"] for reason in
                ("build_output_scan_incomplete", "size_check_incomplete", "workspace_disappeared"))
            for row in records
        )
        return {"schema": "node-cleanup-report-v1", "mode": "report-only",
                "report_id": str(uuid.uuid4()), "event": "inventory_not_cleanup",
                "started_at": started, "hostname": os.uname().nodename,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "root": str(self.root), "discovery_complete": self.complete,
                "checks_complete": checks_complete,
                "activity_known": self.activity_known, "workspaces": records,
                "tracked_usage": tracked_usage,
                "preserved_data": [{"path": str(p), "policy": "keep",
                                    "deletion_permitted": False} for p in self.protected_paths],
                "storage": {"total_bytes": usage.total, "used_bytes": usage.used,
                            "free_bytes": usage.free, "method": "shutil_disk_usage",
                            "advisory_free_bytes": 200*1024**3,
                            "below_advisory": usage.free < 200*1024**3},
                "warnings": self.warnings + [
                    "Sizes are du allocated-byte estimates, not guaranteed reclaimable space; do not sum overlapping paths.",
                    "Btrfs shared extents and retained snapshots are not accounted for; quota/exclusive accounting was not changed.",
                    "Directory mtime is not last-use time. Local remote-tracking refs are not proof that every commit is pushed; no fetch was run.",
                    "No process/open-file census or Maple task API integration: even review-only rows are not deletion approvals.",
                    "Unregistered/non-Git workspaces, unconfigured external targets/caches, and container volumes are outside this report.",
                    "An inventory event does not indicate cleanup occurred. Measurements are not an atomic filesystem snapshot.",
                ]}


def human(report):
    gib = 1024**3
    lines = [f"Node cleanup: REPORT ONLY — {report['generated_at']}",
             f"Root: {report['root']}",
             f"Free: {report['storage']['free_bytes']/gib:.1f} GiB (advisory: 200 GiB)", ""]
    for item in report.get("tracked_usage", []):
        size = item["allocated_bytes"]
        label = f"{size/gib:.2f} GiB" if size is not None else "size unknown"
        lines.append(f"Tracked usage ({item['status']}): {label}  {item['path']}")
    for item in report.get("preserved_data", []):
        lines.append(f"Keep historical data/collector: {item['path']}")
    if report.get("history", {}).get("saved"):
        lines.append("History saved: " + report["history"]["path"])
    for row in report["workspaces"]:
        lines.append(f"{row['disposition']}: {row['path']}")
        if row["protected_reasons"]:
            lines.append("  Reasons: " + ", ".join(row["protected_reasons"]))
        for artifact in row["artifacts"]:
            size = artifact["allocated_bytes"]
            label = f"{size/gib:.2f} GiB" if size is not None else "size unknown"
            lines.append(f"  Build-output estimate: {label}  {artifact['path']}")
    lines += ["", *["Warning: " + w for w in report["warnings"]]]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path,
                        default=Path.home()/".config/node-cleanup/config.json")
    parser.add_argument("--root", type=Path, help="Explicit inventory root; overrides config")
    parser.add_argument("--dry-run", action="store_true", help="Report only (also the default)")
    parser.add_argument("--json", action="store_true", help="Machine-readable report")
    history_options = parser.add_mutually_exclusive_group()
    history_options.add_argument("--save-history", dest="save_history", action="store_true",
                                 help="Save a private dated JSON report, even when checks are incomplete")
    history_options.add_argument("--no-history", dest="save_history", action="store_false",
                                 help="Do not write history (overrides node config)")
    parser.set_defaults(save_history=None)
    parser.add_argument("--history-dir", type=Path, help="Override the private history directory")
    parser.add_argument("--apply", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.apply:
        parser.error("This first version is report-only; deletion/retirement is not implemented")
    config = {}
    try:
        if args.config.is_file():
            config = json.loads(args.config.read_text())
            if not isinstance(config, dict):
                raise CheckError("Configuration must be a JSON object")
        value = args.root or config.get("root")
        if not value:
            raise CheckError("Provide --root or a node-local config with an explicit root")
        root = local_directory(value)
        if root == Path(root.anchor) or root == Path.home() or root in Path.home().parents:
            raise CheckError("Refusing filesystem-root or home-wide inventory")
        paseo = Path(config["paseo"]).expanduser() if config.get("paseo") else None
        mde_roots = [local_directory(p, root) for p in config.get("mde_roots", [])]
        seconds = config.get("max_seconds", 120)
        if not isinstance(seconds, int) or not 1 <= seconds <= 600:
            raise CheckError("max_seconds must be an integer between 1 and 600")
        history = history_directory(args.history_dir or config.get("history_dir"))
        enabled = config.get("save_history", False) if args.save_history is None else args.save_history
        if not isinstance(enabled, bool):
            raise CheckError("save_history must be a boolean")
        usage_values = config.get("usage_paths", [])
        if not isinstance(usage_values, list) or len(usage_values) > 32 or any(
                not isinstance(p, str) or not Path(p).expanduser().is_absolute() for p in usage_values):
            raise CheckError("usage_paths must be a list of at most 32 absolute directory paths")
        usage_paths = [Path(p).expanduser().absolute() for p in usage_values]
        report = Inventory(root, paseo, mde_roots, seconds, usage_paths=usage_paths,
                           protected_paths=preserved_paths(history)).report()
        report["collector_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        report["history"] = {"enabled": enabled, "saved": False}
        if enabled:
            try:
                save_history(report, history)
            except (CheckError, OSError) as error:
                report["history"] = {"enabled": True, "saved": False}
                report["warnings"].append(f"History was not saved: {error}")
                report["checks_complete"] = False
    except (CheckError, OSError, ValueError, TypeError) as error:
        parser.exit(1, f"node-cleanup: {error}\n")
    print(json.dumps(report, indent=2) if args.json else human(report))
    return 0 if report["checks_complete"] else 1


if __name__ == "__main__":
    sys.exit(main())
