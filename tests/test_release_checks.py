"""Public desktop metadata fixtures; no real network, apps, or credentials."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check-updates.py"
SPEC = importlib.util.spec_from_file_location("release_checks", SCRIPT)
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


class ReleaseChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="release-checks-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "modules").mkdir()
        self.pin = {"version": "2026.10.1", "url": CHECK.artifact_url("2026.10.1"), "sha256": "a" * 64}
        self.write_pin()
        self.root_patch = patch.object(CHECK, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def write_pin(self):
        (self.root / "modules/bitwarden-release.json").write_text(json.dumps(self.pin))

    def release(self, version="2026.10.2", **updates):
        record = {"tag_name": f"desktop-v{version}", "draft": False, "prerelease": False,
                  "assets": [{"name": f"Bitwarden-{version}-x86_64.rpm",
                              "browser_download_url": CHECK.artifact_url(version), "digest": "sha256:" + "a" * 64}]}
        return record | updates

    def test_pin_validates_exact_upstream_artifact_and_sha256(self):
        self.assertEqual(self.pin, CHECK.load_pin())
        for field, value in (("version", "1;touch marker"), ("url", "https://example.invalid/Bitwarden.rpm"),
                             ("sha256", "missing")):
            with self.subTest(field=field):
                original = self.pin[field]
                self.pin[field] = value
                self.write_pin()
                with self.assertRaises(ValueError):
                    CHECK.load_pin()
                self.pin[field] = original
                self.write_pin()

    def test_desktop_filter_skips_browser_cli_draft_and_prerelease(self):
        records = [self.release(tag_name="browser-v2026.11.0"), self.release(tag_name="cli-v2026.11.0"),
                   self.release(draft=True), self.release(prerelease=True), self.release()]
        with patch.object(CHECK, "fetch_page", return_value=records):
            self.assertEqual("2026.10.2", CHECK.latest_desktop_release()["version"])

    def test_paginates_instead_of_assuming_global_latest_is_desktop(self):
        with patch.object(CHECK, "fetch_page", side_effect=[
            [self.release(tag_name="browser-v2026.11.0")], [self.release()]
        ]) as fetch:
            self.assertEqual("2026.10.2", CHECK.latest_desktop_release()["version"])
        self.assertEqual([1, 2], [call.args[0] for call in fetch.call_args_list])

    def test_missing_or_ambiguous_latest_rpm_fails_without_using_older_release(self):
        valid = self.release()
        for assets in ([], [valid["assets"][0], valid["assets"][0]],
                       [valid["assets"][0] | {"digest": None}],
                       [valid["assets"][0] | {"browser_download_url": "https://example.invalid/rpm"}]):
            with patch.object(CHECK, "fetch_page", return_value=[valid | {"assets": assets}, self.release("2026.10.1")]):
                with self.assertRaises(ValueError):
                    CHECK.latest_desktop_release()

    def test_network_and_exhausted_pagination_are_not_up_to_date(self):
        with patch.object(CHECK, "fetch_page", side_effect=OSError("network unavailable")):
            with self.assertRaises(OSError):
                CHECK.latest_desktop_release()
        with patch.object(CHECK, "fetch_page", return_value=[]) as fetch:
            with self.assertRaisesRegex(ValueError, "No stable desktop RPM"):
                CHECK.latest_desktop_release()
        self.assertEqual(1, fetch.call_count)
        with patch.object(CHECK, "fetch_page", return_value=[self.release(prerelease=True)]) as fetch:
            with self.assertRaisesRegex(ValueError, "ten release pages"):
                CHECK.latest_desktop_release()
        self.assertEqual(10, fetch.call_count)

    def test_reports_installed_pinned_and_published_without_changing_pin(self):
        before = (self.root / "modules/bitwarden-release.json").read_bytes()
        with patch.object(CHECK, "installed_version", return_value="2026.9.1"), patch.object(
            CHECK, "fetch_page", return_value=[self.release()]
        ), contextlib.redirect_stdout(io.StringIO()) as output:
            CHECK.check_updates()
        text = output.getvalue()
        for phrase in ("installed RPM: 2026.9.1", "pin: 2026.10.1", "desktop: 2026.10.2", "Newer desktop release available", "behind the reviewed pin"):
            self.assertIn(phrase, text)
        self.assertEqual(before, (self.root / "modules/bitwarden-release.json").read_bytes())

    def test_changed_digest_for_same_version_is_an_error(self):
        with patch.object(CHECK, "installed_version", return_value="2026.10.1"), patch.object(
            CHECK, "fetch_page", return_value=[self.release("2026.10.1", assets=[self.release("2026.10.1")["assets"][0] | {"digest": "sha256:" + "b" * 64}])]
        ), contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertRaisesRegex(ValueError, "digest changed"):
                CHECK.check_updates()
        self.assertNotIn("No newer", output.getvalue())

    def test_installed_version_uses_rpm_metadata_without_running_bitwarden(self):
        with patch.object(CHECK.shutil, "which", return_value="rpm"), patch.object(
            CHECK.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="2026.10.1\n")
        ) as run:
            self.assertEqual("2026.10.1", CHECK.installed_version())
        self.assertEqual("rpm", run.call_args.args[0][0])
        self.assertNotIn("--version", run.call_args.args[0])
        for code in (42, 97):
            with patch.object(CHECK.shutil, "which", return_value="rpm"), patch.object(
                CHECK.subprocess, "run", return_value=SimpleNamespace(returncode=code, stdout="")
            ):
                with self.assertRaisesRegex(ValueError, "Could not inspect"):
                    CHECK.installed_version()
