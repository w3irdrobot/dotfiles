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

    def test_history_is_private_immutable_and_independent_of_build_outputs(self):
        history = self.base / "state/node-cleanup/history"
        (self.repo / "target").mkdir()
        (self.repo / "target/artifact").write_bytes(b"x" * 8192)
        first = self.inventory().report()
        path = cleanup.save_history(first, history)
        original = path.read_bytes()
        (self.repo / "target/artifact").write_bytes(b"y" * 16384)
        second = self.inventory().report()
        second_path = cleanup.save_history(second, history)
        self.assertNotEqual(path, second_path)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(json.loads(original)["event"], "inventory_not_cleanup")
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(history.stat().st_mode & 0o777, 0o700)
        self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(list(path.parent.glob("*.tmp")), [])
        with self.assertRaises(FileExistsError):
            cleanup.save_history(first, history)
        self.assertEqual(path.read_bytes(), original)

    def test_partial_report_is_saved_with_uncertainty_intact(self):
        report = cleanup.Inventory(self.root).report()
        self.assertFalse(report["checks_complete"])
        path = cleanup.save_history(report, self.base / "history")
        saved = json.loads(path.read_text())
        self.assertFalse(saved["checks_complete"])
        self.assertTrue(saved["warnings"])
        self.assertTrue(saved["history"]["saved"])

    def test_public_or_symlinked_history_is_refused(self):
        report = self.inventory().report()
        public = self.base / "public"
        public.mkdir(mode=0o755)
        with self.assertRaises(cleanup.CheckError):
            cleanup.save_history(report, public)
        self.assertEqual(list(public.iterdir()), [])
        private = self.base / "private"
        private.mkdir(mode=0o700)
        alias = self.base / "alias"
        alias.symlink_to(private, target_is_directory=True)
        with self.assertRaises(cleanup.CheckError):
            cleanup.save_history(report, alias / "history")
        self.assertEqual(list(private.iterdir()), [])

    def test_historical_data_overlap_protects_workspace_and_artifact(self):
        metrics = self.repo / "target/metrics"
        metrics.mkdir(parents=True)
        sentinel = metrics / "sentinel.jsonl"
        sentinel.write_text('{"event":"start"}\n')
        row = self.row(self.inventory(protected_paths=[metrics]))
        self.assertIn("historical_data_or_collector_overlap", row["protected_reasons"])
        self.assertEqual(row["artifacts"][0]["classification"], "protected_historical_data_overlap")
        self.assertFalse(row["deletion_permitted"])
        self.assertEqual(sentinel.read_text(), '{"event":"start"}\n')

    def test_history_root_is_not_traversed_even_if_it_contains_a_repository(self):
        history = self.root / "retained-history"
        history.mkdir()
        (history / ".git").mkdir()
        inv = self.inventory(protected_paths=[history])
        self.assertNotIn(history, inv.discover())

    def test_metrics_override_and_default_history_are_preserved(self):
        custom = self.repo / "measurements"
        with patch.dict(os.environ, {"CARGO_METRICS_DIR": str(custom)}):
            kept = cleanup.preserved_paths(self.base / "history")
        self.assertIn(custom, kept)
        self.assertIn(Path.home()/".cache/build-metrics", kept)
        self.assertIn(self.base/"history", kept)

    def test_tracked_sizes_and_missing_directories_are_recorded(self):
        shared = self.base / "shared-cache"
        shared.mkdir()
        (shared / "artifact").write_bytes(b"x" * 8192)
        missing = self.base / "missing-cache"
        report = self.inventory(usage_paths=[shared, missing]).report()
        measured, absent = report["tracked_usage"]
        self.assertEqual(measured["status"], "measured")
        self.assertGreaterEqual(measured["allocated_bytes"], 8192)
        self.assertEqual(absent["status"], "missing")
        self.assertEqual(absent["allocated_bytes"], 0)
        self.assertFalse(missing.exists())
        self.assertIn("used_bytes", report["storage"])

    def test_tracked_size_failures_are_explicit_and_incomplete(self):
        shared = self.base / "cache"
        shared.mkdir()
        inv = self.inventory(usage_paths=[shared])
        with patch.object(inv, "allocated_bytes", return_value=None):
            report = inv.report()
        self.assertFalse(report["checks_complete"])
        self.assertEqual(report["tracked_usage"][0]["status"], "unavailable")
        self.assertIsNone(report["tracked_usage"][0]["allocated_bytes"])

    def test_cli_history_can_be_enabled_and_disabled_by_override(self):
        history = self.base / "history"
        config = self.base / "config.json"
        config.write_text(json.dumps({"root": str(self.root), "save_history": True,
                                      "history_dir": str(history)}))
        command = [sys.executable, str(SCRIPT), "--config", str(config), "--dry-run", "--json"]
        result = subprocess.run(command, text=True, capture_output=True)
        self.assertEqual(result.returncode, 1)  # Activity is unknown, but history is still useful.
        report = json.loads(result.stdout)
        self.assertTrue(report["history"]["saved"])
        self.assertEqual(json.loads(Path(report["history"]["path"]).read_text()), report)
        before = set(history.glob("*/*.json"))
        result = subprocess.run(command + ["--no-history"], text=True, capture_output=True)
        self.assertFalse(json.loads(result.stdout)["history"]["enabled"])
        self.assertEqual(set(history.glob("*/*.json")), before)

    def test_failed_history_write_is_reported_without_success_claim(self):
        history = self.base / "not-a-directory"
        history.write_text("preserve this file")
        result = subprocess.run([
            sys.executable, str(SCRIPT), "--root", str(self.root),
            "--config", str(self.base / "missing.json"), "--save-history",
            "--history-dir", str(history), "--json",
        ], text=True, capture_output=True)
        self.assertEqual(result.returncode, 1)
        report = json.loads(result.stdout)
        self.assertFalse(report["history"]["saved"])
        self.assertTrue(any("History was not saved" in w for w in report["warnings"]))
        self.assertEqual(history.read_text(), "preserve this file")

    def test_apply_cannot_write_history_even_when_enabled(self):
        history = self.base / "history"
        result = subprocess.run([
            sys.executable, str(SCRIPT), "--root", str(self.root), "--apply",
            "--save-history", "--history-dir", str(history),
        ], text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(history.exists())


if __name__ == "__main__":
    unittest.main()
