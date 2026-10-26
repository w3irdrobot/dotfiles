"""Native Bitwarden RPM and notice fixtures; no installation or vault access."""

import hashlib
import json
from pathlib import Path
import subprocess
import unittest

import test_dotfiles


class Bitwarden(unittest.TestCase):
    mock = test_dotfiles.Fixture.mock
    calls = test_dotfiles.Fixture.calls
    snapshot = test_dotfiles.Fixture.snapshot
    assert_failed = test_dotfiles.Fixture.assert_failed
    run_cli = test_dotfiles.Fixture.run_cli

    def setUp(self):
        test_dotfiles.Fixture.setUp(self)
        self.payload = self.base / "fixture.rpm"
        self.payload.write_bytes(b"synthetic public RPM fixture, not an executable")
        self.pin_path = self.repo / "modules/bitwarden-release.json"
        pin = json.loads(self.pin_path.read_text())
        pin["sha256"] = hashlib.sha256(self.payload.read_bytes()).hexdigest()
        self.pin_path.write_text(json.dumps(pin))
        self.target = self.home / f".cache/dotfiles/bitwarden/{pin['version']}/Bitwarden-{pin['version']}-x86_64.rpm"
        self.binary = self.base / "usr/bin/bitwarden"
        self.env.update(TEST_PAYLOAD=str(self.payload), TEST_VERSION=pin["version"])
        self.mock("curl", """import shutil
sys.exit(43) if os.environ.get('TEST_DOWNLOAD_FAIL') == '1' else None
shutil.copyfile(os.environ['TEST_PAYLOAD'], sys.argv[sys.argv.index('--output') + 1])
""")
        self.mock("sha256sum", """import hashlib
digest, path = sys.stdin.read().strip().split('  ', 1)
with open(path, 'rb') as source:
    actual = hashlib.sha256(source.read()).hexdigest()
sys.exit(0 if digest == actual else 1)
""")
        self.mock("rpm", """args = sys.argv[1:]
if os.environ.get('TEST_RPM_ERROR') == '1': sys.exit(97)
if '-qp' in args:
    print(os.environ.get('TEST_HEADER', 'bitwarden|' + os.environ['TEST_VERSION'] + '|1|x86_64'))
elif '-qf' in args:
    if os.environ.get('TEST_UNOWNED_LAUNCHER') and args[-1].endswith('/usr/bin/bitwarden'): sys.exit(1)
    print(os.environ.get('TEST_OWNER', 'bitwarden'))
elif '-q' in args:
    installed = os.environ.get('TEST_INSTALLED', '')
    if not installed: sys.exit(1)
    print(installed)
else:
    sys.exit(97)
""")
        self.mock("sudo", """args = sys.argv[1:]
if args[0] != 'dnf': sys.exit(97)
if 'repoquery' in args:
    for name in args[args.index('--queryformat') + 2:]: print(name)
elif any(a in args for a in ('upgrade', 'install', 'makecache')):
    pass
else:
    sys.exit(97)
""")

    def library(self, body="install_packages", dry_run=False):
        script = '''set -euo pipefail
ROOT=$1; DRY_RUN=$2
source "$ROOT/lib/dotfiles.sh"
MODULES=(bitwarden); PACKAGES=(libsecret python3 curl)
'''
        return subprocess.run(
            [test_dotfiles.BASH, "-c", script + body + "\n", "bitwarden-fixture", str(self.repo), str(int(dry_run))],
            cwd=self.base, env=self.env, text=True, capture_output=True, timeout=20,
        )

    def installed(self, version="2026.10.1"):
        self.env["TEST_INSTALLED"] = version
        self.binary.parent.mkdir(parents=True, exist_ok=True)
        self.binary.write_text('#!/usr/bin/env bash\nexit 97\n')
        self.binary.chmod(0o755)

    def transactions(self):
        return [c for c in self.calls() if c[:2] == ["sudo", "dnf"] and any(a in c for a in ("install", "upgrade"))]

    def test_verified_local_rpm_is_prepared_before_protected_upgrade_and_install(self):
        result = self.library()
        self.assertEqual(0, result.returncode, result.stderr)
        transactions = self.transactions()
        self.assertEqual(2, len(transactions))
        self.assertIn(str(self.target), transactions[1])
        verification = [i for i, c in enumerate(self.calls()) if c[0] == "rpm" and "-qp" in c]
        self.assertEqual(2, len(verification))
        self.assertLess(verification[0], self.calls().index(transactions[0]))
        self.assertLess(self.calls().index(transactions[0]), verification[1])
        self.assertLess(verification[1], self.calls().index(transactions[1]))
        self.assertEqual(self.payload.read_bytes(), self.target.read_bytes())
        self.assertEqual([], list(self.target.parent.glob(".download.*")))
        self.assertFalse(any(c[0] in ("bitwarden", "gpg") for c in self.calls()))
        self.assertFalse(any("--nogpgcheck" in c for c in self.calls()))

    def test_bad_hash_or_wrong_rpm_header_never_starts_package_transactions(self):
        for field, value in (("sha256", "0" * 64), ("header", "other|2026.10.1|1|x86_64"),
                             ("header", "bitwarden|2026.10.0|1|x86_64"), ("header", "bitwarden|2026.10.1|1|aarch64")):
            with self.subTest(field=field, value=value):
                self.log.unlink(missing_ok=True)
                pin = json.loads(self.pin_path.read_text())
                pin["sha256"] = "0" * 64 if field == "sha256" else hashlib.sha256(self.payload.read_bytes()).hexdigest()
                self.pin_path.write_text(json.dumps(pin))
                if field == "header": self.env["TEST_HEADER"] = value
                self.assert_failed(self.library())
                self.assertEqual([], self.transactions())
                self.assertFalse(self.target.exists())

    def test_equal_or_newer_installed_version_is_kept_without_download_or_downgrade(self):
        for version in ("2026.10.1", "2026.11.0"):
            self.log.unlink(missing_ok=True)
            self.installed(version)
            result = self.library()
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("no downgrade or re-download", result.stderr)
            self.assertFalse(any(c[0] == "curl" for c in self.calls()))
            self.assertNotIn(str(self.target), self.transactions()[-1])

    def test_old_installed_version_receives_the_reviewed_rpm(self):
        self.installed("2026.9.1")
        result = self.library()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn(str(self.target), self.transactions()[-1])

    def test_query_errors_missing_native_binary_and_wrong_owner_refuse_preflight(self):
        self.env["TEST_RPM_ERROR"] = "1"
        self.assert_failed(self.library(), "Could not inspect")
        del self.env["TEST_RPM_ERROR"]
        self.env["TEST_INSTALLED"] = "2026.10.1"
        self.assert_failed(self.library(), "missing its native executable")
        self.installed()
        self.env["TEST_OWNER"] = "unmanaged"
        self.assert_failed(self.library(), "owned by the bitwarden RPM")
        self.assertEqual([], self.transactions())

    def test_download_failure_cleans_staging_without_installing(self):
        self.env["TEST_DOWNLOAD_FAIL"] = "1"
        result = self.library()
        self.assertEqual(43, result.returncode, result.stderr)
        self.assertFalse(self.target.exists())
        self.assertEqual([], list(self.target.parent.glob(".download.*")))
        self.assertEqual([], self.transactions())

    def test_valid_cache_is_reused_but_conflicting_cache_is_not_overwritten(self):
        self.target.parent.mkdir(parents=True)
        self.target.write_bytes(b"unmanaged cache")
        self.assert_failed(self.library(), "checksum mismatch")
        self.assertEqual(b"unmanaged cache", self.target.read_bytes())
        self.assertEqual([], self.transactions())
        self.target.write_bytes(self.payload.read_bytes())
        self.log.unlink(missing_ok=True)
        result = self.library()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse(any(c[0] == "curl" for c in self.calls()))

    def test_dry_run_has_no_download_privilege_or_cache_changes(self):
        before = self.snapshot()
        result = self.library(dry_run=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(before, self.snapshot())
        self.assertFalse(any(c[0] in ("curl", "sudo", "dnf", "sha256sum") for c in self.calls()))

    def test_cache_symlink_and_parent_file_conflicts_refuse_before_privilege(self):
        self.target.parent.mkdir(parents=True)
        self.target.symlink_to(self.payload)
        self.assert_failed(self.library(), "Conflicting Bitwarden RPM cache")
        self.assertEqual([], self.transactions())
        self.assertFalse(any(c[0] == "sudo" for c in self.calls()))
        self.target.unlink()
        self.env['XDG_CACHE_HOME'] = str(self.payload)
        self.assert_failed(self.library(), "Conflicting Bitwarden cache parent")

    def test_installed_rpm_validation_requires_native_package_ownership(self):
        self.installed()
        self.assertEqual(0, self.library('validate_bitwarden_install').returncode)
        self.env['TEST_OWNER'] = 'unmanaged'
        self.assert_failed(self.library('validate_bitwarden_install'), 'installation is incomplete')

    def test_vendor_direct_and_alternatives_symlinks_validate_the_owned_opt_target(self):
        native = self.base / 'opt/Bitwarden/bitwarden'
        native.parent.mkdir(parents=True)
        native.write_text('never execute this fixture')
        native.chmod(0o755)
        self.binary.parent.mkdir(parents=True)
        alternative = self.base / 'etc/alternatives/bitwarden'
        alternative.parent.mkdir(parents=True)
        alternative.symlink_to(native)
        self.env['TEST_INSTALLED'] = '2026.10.1'
        self.env['TEST_UNOWNED_LAUNCHER'] = '1'
        for target in (native, alternative):
            self.binary.symlink_to(target)
            self.log.unlink(missing_ok=True)
            result = self.library('preflight_bitwarden; validate_bitwarden_install')
            self.assertEqual(0, result.returncode, result.stderr)
            owners = [call[-1] for call in self.calls() if call[0] == 'rpm' and '-qf' in call]
            self.assertTrue(owners)
            self.assertEqual({str(native.resolve())}, set(owners))
            self.binary.unlink()

    def test_vendor_launcher_cannot_point_to_an_arbitrary_or_dangling_target(self):
        target = self.base / 'unexpected-executable'
        target.write_text('never execute')
        target.chmod(0o755)
        self.binary.parent.mkdir(parents=True)
        self.binary.symlink_to(target)
        self.assert_failed(self.library('preflight_bitwarden'), 'unexpected executable')
        target.unlink()
        self.assert_failed(self.library('preflight_bitwarden'), 'missing its native executable')
        self.assertEqual([], self.transactions())

    def test_update_notices_fail_visibly_without_failing_completed_os_updates(self):
        checker = self.repo / "scripts/check-updates.py"
        checker.write_text('raise SystemExit("fixture release metadata unavailable")\n')
        result = self.library("check_bitwarden_release_notice")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("release check failed", result.stderr)
        self.assertIn("status is unknown", result.stderr)

    def test_check_updates_help_and_preview_are_read_free_and_dispatch_preserves_status(self):
        checker = self.repo / "scripts/check-updates.py"
        checker.write_text('print("fixture checker"); raise SystemExit(23)\n')
        for flag in ("--help", "--dry-run"):
            result = self.run_cli("check-updates", flag)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertNotIn("fixture checker", result.stdout)
            self.assertEqual([], self.calls())
        result = self.run_cli("check-updates")
        self.assertEqual(23, result.returncode, result.stderr)
        self.assertIn("fixture checker", result.stdout)
