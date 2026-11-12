"""Read-only cleanup reports against disposable repositories and fake owner APIs."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/node-cleanup.py"
spec = importlib.util.spec_from_file_location("node_cleanup", SCRIPT)
cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)


class NodeCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "projects"
        self.root.mkdir()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-b", "master")
        (self.repo / ".gitignore").write_text("target/\nnode_modules/\ndist/\nbuild/\n.next/\n")
        (self.repo / "source.txt").write_text("fixture source\n")
        self.git("add", ".")
        self.git("commit", "-m", "fixture")
        self.git("update-ref", "refs/remotes/origin/master", "HEAD")

    def git(self, *args, cwd=None):
        return subprocess.check_output([
            "git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
            "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null",
            "-C", str(cwd or self.repo), *args,
        ], stderr=subprocess.DEVNULL)

    def inventory(self, agents=(), workspaces=(), **kwargs):
        inventory = cleanup.Inventory(self.root, paseo=Path("/fake/paseo"), **kwargs)
        command = inventory.command

        def fake(args, timeout=10):
            if args[0] == "/fake/paseo":
                return json.dumps(workspaces if args[1] == "workspace" else agents).encode()
            return command(args, timeout)

        inventory.command = fake
        return inventory

    def row(self, inventory=None):
        report = (inventory or self.inventory()).report()
        return next(row for row in report["workspaces"] if row["path"] == str(self.repo))

    def test_clean_repository_is_review_only_never_deletable(self):
        row = self.row()
        self.assertEqual(row["disposition"], "retirement_review_only")
        self.assertEqual(row["git"]["local_only_commits"], 0)
        self.assertFalse(row["deletion_permitted"])

    def test_dirty_and_untracked_files_are_protected_without_names_in_report(self):
        (self.repo / "source.txt").write_text("changed\n")
        (self.repo / "private-untracked-name").write_text("do not print this content")
        row = self.row()
        self.assertIn("dirty_or_untracked_work", row["protected_reasons"])
        self.assertNotIn("private-untracked-name", json.dumps(row))
        self.assertNotIn("do not print this content", json.dumps(row))

    def test_unpushed_commits_and_missing_remote_refs_protect(self):
        (self.repo / "source.txt").write_text("second\n")
        self.git("commit", "-am", "second")
        self.assertIn("commits_not_in_remote_tracking_refs", self.row()["protected_reasons"])
        self.git("update-ref", "-d", "refs/remotes/origin/master")
        self.assertIn("remote_tracking_coverage_unknown", self.row()["protected_reasons"])

    def test_detached_unpublished_head_is_protected(self):
        self.git("checkout", "--detach")
        (self.repo / "source.txt").write_text("detached\n")
        self.git("commit", "-am", "detached")
        self.assertIn("commits_not_in_remote_tracking_refs", self.row()["protected_reasons"])

    def test_running_idle_and_active_workspace_references_protect(self):
        for status in ("running", "idle"):
            with self.subTest(status=status):
                inv = self.inventory(agents=[{"cwd": str(self.repo / "subdir"), "status": status}])
                self.assertIn("running_or_idle_agent_reference", self.row(inv)["protected_reasons"])
        inv = self.inventory(workspaces=[{"cwd": str(self.repo)}])
        self.assertIn("listed_paseo_workspace", self.row(inv)["protected_reasons"])

    def test_unknown_status_or_missing_active_path_fails_closed(self):
        for agent in ({"cwd": str(self.repo), "status": "new-schema-state"},
                      {"status": "running"}, {"cwd": "relative", "status": "idle"}):
            with self.subTest(agent=agent):
                row = self.row(self.inventory(agents=[agent]))
                self.assertIn("activity_unknown", row["protected_reasons"])

    def test_paseo_home_abbreviation_is_resolved_for_activity(self):
        with patch.object(Path, "home", return_value=self.root):
            row = self.row(self.inventory(agents=[{"cwd": "~/repo", "status": "running"}]))
        self.assertIn("running_or_idle_agent_reference", row["protected_reasons"])
        self.assertNotIn("activity_unknown", row["protected_reasons"])

    def test_missing_or_failed_owner_api_fails_closed(self):
        row = self.row(cleanup.Inventory(self.root))
        self.assertIn("activity_unknown", row["protected_reasons"])
        inv = self.inventory()
        original = inv.command

        def fail(args, timeout=10):
            if args[0] == "/fake/paseo":
                raise cleanup.CheckError("private credential diagnostic must not appear")
            return original(args, timeout)

        inv.command = fail
        report = inv.report()
        self.assertFalse(report["activity_known"])
        self.assertNotIn("private credential diagnostic", json.dumps(report))

    def test_mde_lifecycle_is_protected(self):
        row = self.row(self.inventory(mde_roots=[self.root]))
        self.assertIn("mde_lifecycle_not_integrated", row["protected_reasons"])

    def test_discovers_registered_worktree_not_just_main_checkout(self):
        worktree = self.root / "workspaces" / "feature"
        worktree.parent.mkdir()
        self.git("worktree", "add", "-b", "feature", str(worktree))
        report = self.inventory().report()
        self.assertIn(str(worktree), [row["path"] for row in report["workspaces"]])

    def test_symlink_and_secret_directories_are_not_traversed(self):
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "target").mkdir()
        (self.repo / "linked").symlink_to(outside, target_is_directory=True)
        secrets = self.repo / "secrets"
        secrets.mkdir()
        (secrets / "target").mkdir()
        row = self.row()
        self.assertEqual(row["artifacts"], [])
        with self.assertRaises(cleanup.CheckError):
            cleanup.local_directory(self.repo / "linked", self.root)

    def test_build_outputs_report_sizes_but_remain_unapproved(self):
        output = self.repo / "target"
        output.mkdir()
        (output / "synthetic-build-output").write_bytes(b"x" * 8192)
        row = self.row()
        artifact = row["artifacts"][0]
        self.assertEqual(artifact["path"], str(output))
        self.assertGreaterEqual(artifact["allocated_bytes"], 8192)
        self.assertFalse(row["deletion_permitted"])
        self.assertIn("not_verified_disposable", artifact["classification"])

    def test_budget_exhaustion_is_explicit_and_fail_closed(self):
        inv = self.inventory(max_entries=1)
        report = inv.report()
        self.assertFalse(report["discovery_complete"])
        self.assertTrue(report["warnings"])

    def test_git_failure_is_protected(self):
        inv = self.inventory()
        with patch.object(inv, "git", side_effect=cleanup.CheckError("unavailable")):
            row = self.row(inv)
        self.assertIn("git_state_unknown", row["protected_reasons"])
        self.assertIn("discovery_incomplete", row["protected_reasons"])

    def test_incomplete_size_check_is_not_reported_as_complete(self):
        (self.repo / "target").mkdir()
        inv = self.inventory()
        with patch.object(inv, "allocated_bytes", return_value=None):
            report = inv.report()
        self.assertFalse(report["checks_complete"])
        self.assertIn("size_check_incomplete", report["workspaces"][0]["protected_reasons"])

    def test_inherited_repository_overrides_are_not_used(self):
        with patch.dict(os.environ, {"GIT_DIR": "/unrelated/git", "GIT_WORK_TREE": "/unrelated"}):
            inv = self.inventory()
        self.assertNotIn("GIT_DIR", inv.env)
        self.assertNotIn("GIT_WORK_TREE", inv.env)
        self.assertTrue(self.row(inv)["git"]["known"])

    def test_report_does_not_change_repository_files_or_index(self):
        paths = [self.repo / "source.txt", self.repo / ".git/index", self.repo / ".git/HEAD"]
        before = {str(p): (p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).digest()) for p in paths}
        self.inventory().report()
        after = {str(p): (p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).digest()) for p in paths}
        self.assertEqual(before, after)

    def test_apply_is_rejected_before_scanning(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root), "--apply"],
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("report-only", result.stderr)
        self.assertEqual((self.repo / "source.txt").read_text(), "fixture source\n")

    def test_cli_explicit_root_json_and_no_default_scan(self):
        missing = self.base / "missing-config.json"
        result = subprocess.run([sys.executable, str(SCRIPT), "--config", str(missing)],
                                text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        result = subprocess.run([sys.executable, str(SCRIPT), "--config", str(missing),
                                 "--root", str(self.root), "--dry-run", "--json"],
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 1)  # no owner API: uncertainty is visible
        self.assertEqual(json.loads(result.stdout)["mode"], "report-only")
        self.assertNotIn("Traceback", result.stderr)

    def test_root_and_home_wide_scan_refused(self):
        for root in (Path("/"), Path.home()):
            with self.subTest(root=root):
                result = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root),
                                         "--config", str(self.base / "missing.json")],
                                        text=True, capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Refusing", result.stderr)


if __name__ == "__main__":
    unittest.main()
