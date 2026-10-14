"""Native Nix and nono artifact fixtures; no host installation or real downloads."""

from pathlib import Path
import os
import shutil
import socket
import subprocess
import unittest

import test_dotfiles


class Artifacts(unittest.TestCase):
    # Reuse the isolated PATH/home setup without inheriting its CLI test cases.
    mock = test_dotfiles.Fixture.mock
    calls = test_dotfiles.Fixture.calls
    snapshot = test_dotfiles.Fixture.snapshot
    assert_failed = test_dotfiles.Fixture.assert_failed

    def setUp(self):
        test_dotfiles.Fixture.setUp(self)
        self.nix_root = self.base / "nix"
        self.nix_binary = self.base / "usr/bin/nix"
        self.nix_socket = self.nix_root / "var/nix/daemon-socket/socket"
        self.nix_configuration = self.base / "etc/nix"
        module = self.repo / "modules/nix.sh"
        module.write_text(module.read_text().replace("/usr/bin/nix", str(self.nix_binary)))
        self.mock("pacman", f"""args = sys.argv[1:]
if args == ['-Qqo', '--', {str(self.nix_binary)!r}]:
    owner = os.environ.get('TEST_NIX_OWNER', '')
    if owner:
        print(owner)
    sys.exit(int(os.environ.get('TEST_NIX_OWNERSHIP_STATUS', '0' if owner else '1')))
if args == ['-Qq', 'nix']:
    sys.exit(0 if os.environ.get('TEST_NIX_INSTALLED') == '1' else 1)
sys.exit(97)""")
        self.mock("sudo", """import subprocess
if sys.argv[1:] != ['systemctl', 'enable', '--now', 'nix-daemon.service']:
    sys.exit(97)
sys.exit(subprocess.run(sys.argv[1:], check=False).returncode)""")
        self.mock("systemctl", """args = sys.argv[1:]
if args == ['enable', '--now', 'nix-daemon.service']:
    sys.exit(int(os.environ.get('TEST_SERVICE_ENABLE_STATUS', '0')))
if args == ['is-active', '--quiet', 'nix-daemon.service']:
    sys.exit(int(os.environ.get('TEST_SERVICE_ACTIVE_STATUS', '0')))
sys.exit(97)""")
        self.mock("timeout", """import subprocess
sys.exit(subprocess.run(sys.argv[3:], check=False).returncode)""")
        self.mock("wget", """from pathlib import Path
target = next(a.split('=', 1)[1] for a in sys.argv if a.startswith('--output-document='))
Path(target).write_bytes(b'fixture archive, not a real release')""")
        self.mock("sha256sum", "sys.stdin.read(); sys.exit(0)")
        self.mock("tar", "sys.exit(97)")
        self.mock("install", "sys.exit(97)")
        cmp_binary = shutil.which("cmp")
        self.assertIsNotNone(cmp_binary, "cmp is needed for byte comparison fixtures")
        (self.path / "cmp").symlink_to(cmp_binary)

    def run_nix(self, function="setup_nix", *args, dry_run=False):
        # Source only the module under test, not mutable integration dispatch.
        script = """set -euo pipefail
die() { printf '%s\\n' "$*" >&2; exit 1; }
log() { printf '%s\\n' "$*" >&2; }
run() { if ((! DRY_RUN)); then "$@"; fi; }
source "$1"
DRY_RUN=$2
"$3" "${@:4}"
printf 'continued\\n'
"""
        return subprocess.run(
            [test_dotfiles.BASH, "-c", script, "artifact-test",
             str(self.repo / "modules/nix.sh"), str(int(dry_run)), function, *args],
            cwd=self.repo, env=self.env, capture_output=True, text=True, timeout=20,
        )

    def run_nono(self):
        return subprocess.run(
            [test_dotfiles.BASH, str(self.repo / "modules/nono.sh")],
            cwd=self.repo, env=self.env, capture_output=True, text=True, timeout=20,
        )

    def existing_nix(self):
        self.nix_binary.parent.mkdir(parents=True)
        self.mock("nix-fixture", """from pathlib import Path
args = sys.argv[1:]
if args == ['--extra-experimental-features', 'nix-command flakes', 'store', 'ping', '--store', 'daemon']:
    sys.exit(int(os.environ.get('TEST_NIX_PING_STATUS', '0')))
if args == ['config', 'show']:
    config = Path(os.environ['HOME']) / '.config/nix/nix.conf'
    print(config.read_text() if config.exists() else 'experimental-features = ', end='\\n')
    sys.exit(int(os.environ.get('TEST_NIX_CONFIG_STATUS', '0')))
sys.exit(97)
""")
        shutil.move(self.path / "nix-fixture", self.nix_binary)
        self.env["TEST_NIX_OWNER"] = "nix"
        self.env["TEST_NIX_INSTALLED"] = "1"
        self.nix_socket.parent.mkdir(parents=True)
        cwd = Path.cwd()
        try:
            os.chdir(self.nix_socket.parent)
            with socket.socket(socket.AF_UNIX) as daemon:
                daemon.bind("socket")
        finally:
            os.chdir(cwd)
        # Deliberately stale socket: only the mocked ping can establish health.

    def assert_no_later_phase(self, result):
        self.assertNotIn("continued", result.stdout)

    def test_native_nix_preflight_accepts_fresh_host_read_only(self):
        result = self.run_nix("preflight_nix")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse(self.nix_root.exists())
        self.assertFalse(self.nix_configuration.exists())
        self.assertEqual({}, self.snapshot())
        self.assertTrue(all(c[0] == "pacman" for c in self.calls()))

    def test_native_nix_preflight_accepts_package_owned_existing_store(self):
        self.existing_nix()
        self.nix_configuration.mkdir(parents=True)
        (self.nix_configuration / "nix.conf").write_text("build-users-group = nixbld\n")
        result = self.run_nix("preflight_nix")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(all(c[0] == "pacman" for c in self.calls()))

    def test_native_nix_preflight_refuses_upstream_and_partial_paths(self):
        for path in (self.nix_root, self.nix_configuration):
            with self.subTest(path=path):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.mkdir()
                result = self.run_nix("preflight_nix")
                self.assert_failed(result, "Never mix installation methods")
                self.assertTrue(path.is_dir())
                self.assert_no_later_phase(result)
                path.rmdir()
                path.symlink_to(self.base / "missing-store")
                result = self.run_nix("preflight_nix")
                self.assert_failed(result, "Never mix installation methods")
                self.assertTrue(path.is_symlink())
                path.unlink()
        self.assertTrue(all(c[0] == "pacman" for c in self.calls()))

    def test_native_nix_preflight_refuses_unowned_binary_without_executing_it(self):
        self.nix_binary.parent.mkdir(parents=True)
        self.nix_binary.write_text('#!/usr/bin/env bash\nprintf executed > "$HOME/unowned-ran"\n')
        self.nix_binary.chmod(0o755)
        before = self.nix_binary.read_bytes()
        for owner in ("", "other-package"):
            with self.subTest(owner=owner):
                self.env["TEST_NIX_OWNER"] = owner
                result = self.run_nix("preflight_nix")
                self.assert_failed(result, "Unmanaged or partial")
                self.assertEqual(before, self.nix_binary.read_bytes())
                self.assertFalse((self.home / "unowned-ran").exists())

    def test_native_nix_preflight_refuses_path_only_installation(self):
        self.mock("nix", "sys.exit(97)")
        result = self.run_nix("preflight_nix")
        self.assert_failed(result, "Unmanaged or partial")
        self.assertFalse(any(c[0] == "nix" for c in self.calls()))

    def test_native_nix_preflight_refuses_missing_owned_binary_and_query_errors(self):
        self.env["TEST_NIX_OWNER"] = "nix"
        result = self.run_nix("preflight_nix")
        self.assert_failed(result, "Package-owned native Nix is incomplete")
        del self.env["TEST_NIX_OWNER"]
        self.env["TEST_NIX_INSTALLED"] = "1"
        result = self.run_nix("preflight_nix")
        self.assert_failed(result, "missing its owned native binary")
        del self.env["TEST_NIX_INSTALLED"]
        self.env["TEST_NIX_OWNERSHIP_STATUS"] = "97"
        result = self.run_nix("preflight_nix")
        self.assert_failed(result, "Could not inspect native Nix package ownership")

    def test_native_nix_setup_requires_installed_owned_package(self):
        result = self.run_nix()
        self.assert_failed(result, "Install the native nix package")
        self.assertFalse(any(c[0] in ("sudo", "systemctl") for c in self.calls()))

    def test_native_nix_dry_run_has_no_service_binary_or_file_effects(self):
        for installed in (False, True):
            with self.subTest(installed=installed):
                if installed:
                    self.existing_nix()
                before = self.snapshot()
                result = self.run_nix(dry_run=True)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual(before, self.snapshot())
                self.assertTrue(all(c[0] == "pacman" for c in self.calls()))
                if installed:
                    result = self.run_nix("validate_nix", dry_run=True)
                    self.assertEqual(0, result.returncode, result.stderr)
                    self.assertEqual(before, self.snapshot())
                    self.assertTrue(all(c[0] == "pacman" for c in self.calls()))

    def test_native_nix_setup_bootstraps_before_user_features_are_linked_idempotently(self):
        self.existing_nix()
        self.nix_configuration.mkdir(parents=True)
        system_config = self.nix_configuration / "nix.conf"
        system_config.write_text("build-users-group = nixbld\n")
        before = self.snapshot()
        for args in ((), ("--bootstrap",)):
            result = self.run_nix("setup_nix", *args)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(before, self.snapshot())
        self.assertEqual("build-users-group = nixbld\n", system_config.read_text())
        sudo_calls = [c for c in self.calls() if c[0] == "sudo"]
        self.assertEqual([["sudo", "systemctl", "enable", "--now", "nix-daemon.service"]] * 2, sudo_calls)
        nix_calls = [c for c in self.calls() if c[0] == "nix"]
        self.assertEqual(4, len(nix_calls))
        self.assertTrue(all("nix-command flakes" in c and "ping" in c for c in nix_calls))

    def test_native_nix_service_failure_stops_before_ping(self):
        self.existing_nix()
        self.env["TEST_SERVICE_ENABLE_STATUS"] = "1"
        result = self.run_nix()
        self.assert_failed(result, "Could not enable/start")
        self.assertFalse(any(c[0] == "nix" for c in self.calls()))
        self.assert_no_later_phase(result)

    def test_native_nix_daemon_failure_stops_after_service_enable(self):
        self.existing_nix()
        self.env["TEST_NIX_PING_STATUS"] = "1"
        result = self.run_nix()
        self.assert_failed(result, "daemon is not responding")
        self.assertTrue(any(c[:3] == ["systemctl", "enable", "--now"] for c in self.calls()))
        self.assert_no_later_phase(result)

    def test_native_nix_inactive_service_and_missing_socket_are_not_accepted(self):
        self.existing_nix()
        self.env["TEST_SERVICE_ACTIVE_STATUS"] = "1"
        self.assert_failed(self.run_nix("validate_nix", "bootstrap"), "service is not active")
        del self.env["TEST_SERVICE_ACTIVE_STATUS"]
        self.nix_socket.unlink()
        self.assert_failed(self.run_nix("validate_nix", "bootstrap"), "socket is missing")
        self.assertFalse(any(c[0] == "nix" for c in self.calls()))

    def test_native_nix_client_validation_requires_linked_stow_features(self):
        self.existing_nix()
        result = self.run_nix("validate_nix")
        self.assert_failed(result, "link the user nix.conf")
        target = self.home / ".config/nix/nix.conf"
        target.parent.mkdir(parents=True)
        source = self.repo / "stow/nix/.config/nix/nix.conf"
        self.assertEqual("experimental-features = nix-command flakes\n", source.read_text())
        target.symlink_to(source)
        before = self.snapshot()
        result = self.run_nix("validate_nix", "client")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(before, self.snapshot())
        self.env["TEST_NIX_CONFIG_STATUS"] = "1"
        self.assert_failed(self.run_nix("validate_nix"), "configuration could not be read")

    def test_native_nix_metadata_has_repository_package(self):
        fields = dict(line.split("=", 1) for line in
                      (self.repo / "modules/nix.conf").read_text().splitlines()
                      if line and not line.startswith("#"))
        self.assertEqual("core", fields["group"])
        self.assertEqual("nix", fields["packages"])

    def nono_target(self):
        return self.home / ".local/share/dotfiles/nono/0.80.0/nono"

    def mock_nono_archive(self, binary):
        self.mock("tar", f"sys.stdout.buffer.write({binary!r})")

    def test_nono_checksum_failure_prevents_extraction_and_install(self):
        self.mock_nono_archive(b"#!/bin/sh\nexit 0\n")
        self.mock("sha256sum", "sys.stdin.read(); sys.exit(1)")
        result = self.run_nono()
        self.assert_failed(result)
        self.assertFalse(any(c[0] in ("tar", "install") for c in self.calls()))
        self.assertEqual({}, self.snapshot())
        self.assertNotIn("nono installed.", result.stderr)

    def test_nono_matching_nonexecutable_target_is_refused(self):
        binary = b"#!/bin/sh\nexit 0\n"
        self.mock_nono_archive(binary)
        target = self.nono_target()
        target.parent.mkdir(parents=True)
        target.write_bytes(binary)
        target.chmod(0o644)
        link = self.home / ".local/bin/nono"
        link.parent.mkdir(parents=True)
        for linked in (False, True):
            with self.subTest(linked=linked):
                if linked:
                    link.symlink_to(target)
                before = self.snapshot()
                result = self.run_nono()
                self.assert_failed(result, "repair its executable permissions")
                self.assertEqual(before, self.snapshot())
                self.assertEqual(0o644, target.stat().st_mode & 0o777)
                self.assertFalse(any(c[0] == "install" for c in self.calls()))
                self.assertNotIn("nono installed.", result.stderr)

    def test_nono_matching_executable_target_is_idempotent(self):
        binary = b"#!/bin/sh\nexit 0\n"
        self.mock_nono_archive(binary)
        target = self.nono_target()
        target.parent.mkdir(parents=True)
        target.write_bytes(binary)
        target.chmod(0o755)
        link = self.home / ".local/bin/nono"
        link.parent.mkdir(parents=True)
        link.symlink_to(target)
        before = self.snapshot()
        for _ in range(2):
            result = self.run_nono()
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(before, self.snapshot())
        self.assertFalse(any(c[0] == "install" for c in self.calls()))


if __name__ == "__main__":
    unittest.main()
