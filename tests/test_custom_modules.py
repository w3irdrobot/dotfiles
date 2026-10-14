"""Isolated OpenCode trust and native Bitwarden configuration checks."""

import subprocess
import unittest

import test_dotfiles


class CustomModules(unittest.TestCase):
    mock = test_dotfiles.Fixture.mock
    calls = test_dotfiles.Fixture.calls
    snapshot = test_dotfiles.Fixture.snapshot
    assert_failed = test_dotfiles.Fixture.assert_failed

    def setUp(self):
        test_dotfiles.Fixture.setUp(self)
        self.native = self.base / "usr/bin/opencode"
        self.native.parent.mkdir(parents=True)
        module = self.repo / "modules/opencode.sh"
        module.write_text(module.read_text().replace("/usr/bin/opencode", str(self.native)))

    def run_module(self, name, *args):
        return subprocess.run(
            [test_dotfiles.BASH, str(self.repo / "modules" / f"{name}.sh"), *args],
            cwd=self.repo, env=self.env, capture_output=True, text=True, timeout=20,
        )

    def fake_repository(self, version="2.0.29-1", repository="extra", name="opencode", status=0):
        metadata = f"Repository      : {repository}\nName            : {name}\nVersion         : {version}\n"
        self.mock("pacman", f"""if sys.argv[1:] != ['-Si', '--', 'opencode'] or os.environ.get('LC_ALL') != 'C':
    sys.exit(97)
print({metadata!r}, end='')
sys.exit({status})""")

    def fake_native(self, version="opencode v2.0.29", status=0):
        self.native.write_text(f"""#!{test_dotfiles.BASH}
[[ $1 == --version ]] || exit 97
printf 'executed' > "$HOME/native-version-ran"
printf '%s\\n' '{version}'
exit {status}
""")
        self.native.chmod(0o755)

    def test_opencode_repository_accepts_only_extra_v2_read_only(self):
        self.fake_native()
        for version in ("2.0.29-1", "2.1.0-2", "1:2.0.30-1"):
            with self.subTest(version=version):
                self.fake_repository(version=version)
                before = self.snapshot()
                result = self.run_module("opencode", "--check")
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual(before, self.snapshot())
                self.assertFalse((self.home / "native-version-ran").exists())
        self.assertTrue(all(c[0] in ("uname", "pacman") for c in self.calls()))

    def test_opencode_repository_rejects_other_majors_and_missing_package(self):
        self.fake_native()
        for version, status in (("1.2.3-1", 0), ("3.0.0-1", 0), ("", 1), ("", 0)):
            with self.subTest(version=version, status=status):
                self.fake_repository(version=version, status=status)
                before = self.snapshot()
                result = self.run_module("opencode", "--check")
                self.assert_failed(result)
                self.assertEqual(before, self.snapshot())
                self.assertFalse((self.home / "native-version-ran").exists())
        self.assertTrue(all(c[0] in ("uname", "pacman") for c in self.calls()))

    def test_opencode_repository_rejects_wrong_origin_or_name(self):
        for repository, name in (("custom", "opencode"), ("extra", "other-package")):
            with self.subTest(repository=repository, name=name):
                self.fake_repository(repository=repository, name=name)
                result = self.run_module("opencode", "--check")
                self.assert_failed(result, "official Extra")
                self.assertEqual({}, self.snapshot())

    def test_opencode_shadow_file_is_refused_unexecuted_and_untouched(self):
        self.fake_repository()
        self.fake_native()
        shadow = self.home / ".local/bin/opencode"
        shadow.parent.mkdir(parents=True)
        shadow.write_text('#!/usr/bin/env bash\nprintf executed > "$HOME/shadow-ran"\n')
        shadow.chmod(0o755)
        for args in (("--check",), ()):
            with self.subTest(args=args):
                before = self.snapshot()
                result = self.run_module("opencode", *args)
                self.assert_failed(result, "shadows the native package")
                self.assertEqual(before, self.snapshot())
                self.assertEqual(0o755, shadow.stat().st_mode & 0o777)
                self.assertFalse((self.home / "shadow-ran").exists())
                self.assertFalse((self.home / "native-version-ran").exists())
        self.assertFalse(any(c[0] == "pacman" for c in self.calls()))

    def test_opencode_non_native_and_dangling_shadow_symlinks_are_refused(self):
        self.fake_repository()
        shadow = self.home / ".local/bin/opencode"
        shadow.parent.mkdir(parents=True)
        manual = self.home / "manual-opencode"
        manual.write_text('#!/usr/bin/env bash\nprintf executed > "$HOME/shadow-ran"\n')
        manual.chmod(0o755)
        for target in (manual, self.home / "missing-opencode", self.native):
            with self.subTest(target=target):
                shadow.symlink_to(target)
                before = self.snapshot()
                result = self.run_module("opencode", "--check")
                diagnostic = "shadows the native package" if target.exists() else "Dangling OpenCode shadow"
                self.assert_failed(result, diagnostic)
                self.assertEqual(before, self.snapshot())
                self.assertFalse((self.home / "shadow-ran").exists())
                shadow.unlink()

    def test_opencode_native_shadow_symlink_is_allowed_without_execution_during_check(self):
        self.fake_repository()
        self.fake_native()
        shadow = self.home / ".local/bin/opencode"
        shadow.parent.mkdir(parents=True)
        shadow.symlink_to(self.native)
        before = self.snapshot()
        result = self.run_module("opencode", "--check")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.home / "native-version-ran").exists())

    def test_opencode_post_install_accepts_native_v2_without_pacman_or_path_dispatch(self):
        self.mock("opencode", "sys.exit(97)")
        for version in ("2.0.29", "opencode v2.0.29"):
            with self.subTest(version=version):
                self.fake_native(version=version)
                result = self.run_module("opencode")
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertTrue((self.home / "native-version-ran").exists())
                (self.home / "native-version-ran").unlink()
        self.assertFalse(any(c[0] in ("pacman", "opencode", "wget", "sudo") for c in self.calls()))

    def test_opencode_post_install_rejects_non_v2_and_failed_version_command(self):
        for version, status in (("1.2.3", 0), ("opencode v3.0.0", 0), ("opencode v2.0.29", 1)):
            with self.subTest(version=version, status=status):
                self.fake_native(version=version, status=status)
                self.assert_failed(self.run_module("opencode"))

    def test_opencode_post_install_requires_native_binary(self):
        result = self.run_module("opencode")
        self.assert_failed(result, "is missing")
        self.assertEqual({}, self.snapshot())

    def test_opencode_metadata_selects_native_package(self):
        fields = dict(line.split("=", 1) for line in
                      (self.repo / "modules/opencode.conf").read_text().splitlines()
                      if line and not line.startswith("#"))
        self.assertEqual("opencode", fields["packages"])

    def test_bitwarden_metadata_selects_native_package_without_custom_installer(self):
        # Exercise the real Bash metadata parser with only the shipped module.
        for metadata in (self.repo / "modules").glob("*.conf"):
            if metadata.name != "bitwarden.conf":
                metadata.unlink()
        script = """set -euo pipefail
ROOT=$1
source "$ROOT/lib/dotfiles.sh"
GROUPS_CSV=desktop MODULES_CSV=''
validate_groups
load_modules
printf '%s\\n' "${PACKAGES[@]}"
"""
        result = subprocess.run(
            [test_dotfiles.BASH, "-c", script, "native-package-test", str(self.repo)],
            cwd=self.repo, env=self.env, capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(["bitwarden"], result.stdout.splitlines())
        self.assertFalse((self.repo / "modules/bitwarden.sh").exists())
        self.assertEqual({}, self.snapshot())
        self.assertEqual([], self.calls())

    def run_agent_helper(self, local_override=False):
        helper = self.repo / "shell/bitwarden.sh"
        script = """set -euo pipefail
source "$1"
source "$1"
if [[ $2 == local ]]; then source "$3/local/bash/variables.sh"; fi
printf '%s' "$SSH_AUTH_SOCK"
"""
        return subprocess.run(
            [test_dotfiles.BASH, "-c", script, "native-agent-test", str(helper),
             "local" if local_override else "default", str(self.repo)],
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
            with self.subTest(socket=socket):
                self.env["SSH_AUTH_SOCK"] = socket
                before = self.snapshot()
                result = self.run_agent_helper()
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual(socket, result.stdout)
                self.assertEqual(before, self.snapshot())
                self.assertEqual([], self.calls())

    def test_bitwarden_local_variables_override_default(self):
        variables = self.repo / "local/bash/variables.sh"
        variables.parent.mkdir(parents=True)
        variables.write_text('export SSH_AUTH_SOCK="$HOME/local-agent.sock"\n')
        before = self.snapshot()
        result = self.run_agent_helper(local_override=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(str(self.home / "local-agent.sock"), result.stdout)
        self.assertEqual(before, self.snapshot())
        self.assertEqual([], self.calls())
        # Keep the tested source order consistent with the actual interactive shell.
        startup = (self.repo / "shell/startup.sh").read_text()
        self.assertLess(startup.index('source "${BASH_SOURCE[0]%/*}/bitwarden.sh"'),
                        startup.index('source "${BASH_SOURCE[0]%/*}/../local/bash/variables.sh"'))


if __name__ == "__main__":
    unittest.main()
