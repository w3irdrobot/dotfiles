"""Pinned upstream OpenCode fixtures and native Bitwarden shell integration."""

import hashlib
import io
import re
import subprocess
import tarfile
import unittest

import test_dotfiles


class CustomModules(unittest.TestCase):
    mock = test_dotfiles.Fixture.mock
    calls = test_dotfiles.Fixture.calls
    snapshot = test_dotfiles.Fixture.snapshot
    assert_failed = test_dotfiles.Fixture.assert_failed

    def setUp(self):
        test_dotfiles.Fixture.setUp(self)
        self.native = self.home / ".local/share/dotfiles/opencode/2.1.4/opencode"
        self.native.parent.mkdir(parents=True)
        self.module = self.repo / "modules/opencode.sh"
        for name in ("modules/opencode.sh", "lib/dotfiles.sh", "install.sh"):
            path = self.repo / name
            path.write_text(path.read_text().replace(
                "$HOME/.local/share/dotfiles/opencode/2.1.4/opencode", str(self.native)))
        self.mock("sha256sum", """import hashlib
line = sys.stdin.read().rstrip('\u005cn')
digest, path = line.split('  ', 1)
with open(path, 'rb') as source:
    actual = hashlib.sha256(source.read()).hexdigest()
sys.exit(0 if digest == actual else 1)
""")
        self.mock("curl", """import shutil
shutil.copyfile(os.environ['TEST_ARCHIVE'], sys.argv[sys.argv.index('--output') + 1])
""")
        self.mock("tar", """import tarfile
from pathlib import Path
target = Path(sys.argv[sys.argv.index('--directory') + 1]) / 'package/bin/opencode'
target.parent.mkdir(parents=True)
with tarfile.open(sys.argv[sys.argv.index('--file') + 1], 'r:gz') as archive:
    member = archive.getmember('package/bin/opencode')
    if member.issym():
        target.symlink_to(member.linkname)
    else:
        target.write_bytes(archive.extractfile(member).read())
""")
        self.mock("chmod", """args = [a for a in sys.argv[1:] if a != '--']
os.chmod(args[1], int(args[0], 8))
""")

    def pin(self, key, digest):
        self.module.write_text(re.sub(rf"readonly {key}=.*", f"readonly {key}={digest}", self.module.read_text()))

    def fake_repository(self, **kwargs):
        # Compatibility for PATH fixtures; pinned installation never queries RPMs.
        pass

    def binary(self, version="2.1.4", status=0):
        return (f'#!{test_dotfiles.BASH}\n'
                '[[ $1 == --version ]] || exit 97\n'
                'printf executed > "$HOME/native-version-ran"\n'
                f'printf "%s\\n" "{version}"\nexit {status}\n').encode()

    def fake_native(self, version="2.1.4", status=0):
        self.native.write_bytes(self.binary(version, status))
        self.native.chmod(0o755)
        self.pin("OPENCODE_BINARY_SHA256", hashlib.sha256(self.native.read_bytes()).hexdigest())

    def archive(self, version="2.1.4", corrupt_binary=False):
        binary = self.binary(version)
        path = self.base / "upstream.tgz"
        with tarfile.open(path, "w:gz") as archive:
            info = tarfile.TarInfo("package/bin/opencode")
            info.size = len(binary)
            archive.addfile(info, io.BytesIO(binary))
        self.env["TEST_ARCHIVE"] = str(path)
        self.pin("OPENCODE_ARCHIVE_SHA256", hashlib.sha256(path.read_bytes()).hexdigest())
        digest = hashlib.sha256(binary).hexdigest() if not corrupt_binary else "0" * 64
        self.pin("OPENCODE_BINARY_SHA256", digest)

    def run_module(self, name, *args):
        return subprocess.run(
            [test_dotfiles.BASH, str(self.repo / "modules" / f"{name}.sh"), *args],
            cwd=self.repo, env=self.env, capture_output=True, text=True, timeout=20,
        )

    def test_fresh_preflight_is_read_only_without_network_or_execution(self):
        before = self.snapshot()
        result = self.run_module("opencode", "--check")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(before, self.snapshot())
        self.assertFalse(any(c[0] in ("curl", "tar", "sudo", "dnf", "rpm") for c in self.calls()))

    def test_existing_pinned_binary_is_hashed_not_executed_during_check(self):
        self.fake_native()
        result = self.run_module("opencode", "--check")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse((self.home / "native-version-ran").exists())
        self.assertTrue(any(c[0] == "sha256sum" for c in self.calls()))

    def test_edited_pinned_binary_is_preserved_and_refused_without_execution(self):
        self.fake_native()
        self.native.write_bytes(self.binary("3.0.0"))
        before = self.native.read_bytes()
        self.assert_failed(self.run_module("opencode", "--check"), "checksum mismatch")
        self.assertEqual(before, self.native.read_bytes())
        self.assertFalse((self.home / "native-version-ran").exists())

    def test_install_checks_archive_and_binary_before_publishing(self):
        self.archive()
        result = self.run_module("opencode")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue((self.home / ".local/bin/opencode").is_symlink())
        self.assertEqual(self.native.read_bytes(), self.binary())
        self.assertTrue((self.home / "native-version-ran").exists())
        self.assertEqual([], list(self.native.parent.glob(".download.*")))
        self.assertFalse(any(c[0] in ("sudo", "dnf", "rpm", "npm", "node") for c in self.calls()))

    def test_archive_checksum_failure_never_extracts_or_executes(self):
        self.archive()
        self.pin("OPENCODE_ARCHIVE_SHA256", "0" * 64)
        self.assert_failed(self.run_module("opencode"), "archive checksum mismatch")
        self.assertFalse(self.native.exists())
        self.assertFalse(any(c[0] == "tar" for c in self.calls()))
        self.assertFalse((self.home / "native-version-ran").exists())

    def test_failed_download_cleans_staging_and_can_be_retried(self):
        self.archive()
        self.mock("curl", "sys.exit(43)")
        result = self.run_module("opencode")
        self.assertEqual(43, result.returncode, result.stderr)
        self.assertFalse(self.native.exists())
        self.assertEqual([], list(self.native.parent.glob(".download.*")))
        self.mock("curl", "import shutil; shutil.copyfile(os.environ['TEST_ARCHIVE'], sys.argv[sys.argv.index('--output') + 1])")
        result = self.run_module("opencode")
        self.assertEqual(0, result.returncode, result.stderr)

    def test_nonexecutable_pinned_binary_is_not_repaired_or_executed(self):
        self.fake_native()
        self.native.chmod(0o644)
        self.assert_failed(self.run_module("opencode", "--check"), "non-executable")
        self.assertEqual(0o644, self.native.stat().st_mode & 0o777)
        self.assertFalse((self.home / "native-version-ran").exists())

    def test_binary_checksum_failure_never_executes_or_publishes(self):
        self.archive(corrupt_binary=True)
        self.assert_failed(self.run_module("opencode"), "binary checksum mismatch")
        self.assertFalse(self.native.exists())
        self.assertFalse((self.home / "native-version-ran").exists())

    def test_wrong_reported_version_never_publishes(self):
        self.archive(version="1.8.0")
        self.assert_failed(self.run_module("opencode"), "must report pinned V2")
        self.assertFalse(self.native.exists())
        self.assertFalse((self.home / ".local/bin/opencode").exists())

    def test_repeat_install_reuses_verified_binary_without_download_or_execution(self):
        self.fake_native()
        for _ in range(2):
            result = self.run_module("opencode")
            self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse((self.home / "native-version-ran").exists())
        self.assertFalse(any(c[0] in ("curl", "tar") for c in self.calls()))

    def test_binary_symlink_and_conflicting_parent_are_refused(self):
        self.native.symlink_to(self.base / "missing")
        self.assert_failed(self.run_module("opencode", "--check"), "symlink")
        self.native.unlink()
        self.native.parent.rmdir()
        self.native.parent.symlink_to(self.base / "missing")
        self.assert_failed(self.run_module("opencode", "--check"), "Conflicting OpenCode parent")

    def test_metadata_has_no_v1_rpm_or_global_node_toolchain(self):
        text = (self.repo / "modules/opencode.conf").read_text()
        packages = next(line.split("=", 1)[1].split() for line in text.splitlines() if line.startswith("packages="))
        self.assertTrue(set(packages).isdisjoint({"opencode", "nodejs", "npm"}))

    def test_bitwarden_metadata_reports_manual_native_rpm_without_custom_installer(self):
        for metadata in (self.repo / "modules").glob("*.conf"):
            if metadata.name != "bitwarden.conf":
                metadata.unlink()
        result = subprocess.run(
            [test_dotfiles.BASH, "-c", 'set -euo pipefail; ROOT=$1; source "$ROOT/lib/dotfiles.sh"; GROUPS_CSV=desktop; MODULES_CSV=""; validate_groups; load_modules',
             "bitwarden-metadata", str(self.repo)],
            cwd=self.repo, env=self.env, capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("Manual application setup required: bitwarden", result.stderr)
        self.assertFalse((self.repo / "modules/bitwarden.sh").exists())

    def run_agent_helper(self, local_override=False):
        script = 'set -euo pipefail; source "$1"; source "$1"; if [[ $2 == local ]]; then source "$HOME/.config/bash/variables.sh"; fi; printf "%s" "$SSH_AUTH_SOCK"'
        return subprocess.run(
            [test_dotfiles.BASH, "-c", script, "bitwarden-agent", str(self.repo / "shell/bitwarden.sh"),
             "local" if local_override else "default"],
            cwd=self.repo, env=self.env, capture_output=True, text=True, timeout=20,
        )

    def test_bitwarden_agent_defaults_to_native_socket_without_side_effects(self):
        before = self.snapshot()
        result = self.run_agent_helper()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(str(self.home / ".bitwarden-ssh-agent.sock"), result.stdout)
        self.assertEqual(before, self.snapshot())
        self.assertEqual([], self.calls())

    def test_bitwarden_agent_preserves_explicit_socket_including_empty(self):
        for socket in (str(self.home / "other-agent.sock"), ""):
            self.env["SSH_AUTH_SOCK"] = socket
            result = self.run_agent_helper()
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(socket, result.stdout)

    def test_bitwarden_local_variables_override_default(self):
        variables = self.home / ".config/bash/variables.sh"
        variables.parent.mkdir(parents=True)
        variables.write_text('export SSH_AUTH_SOCK="$HOME/local-agent.sock"\n')
        result = self.run_agent_helper(local_override=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(str(self.home / "local-agent.sock"), result.stdout)
