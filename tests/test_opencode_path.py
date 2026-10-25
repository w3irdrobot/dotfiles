"""Read-only native OpenCode PATH policy, using disposable fixture binaries."""

import os
import re
import subprocess
import unittest

import test_custom_modules
import test_dotfiles


class OpenCodePath(unittest.TestCase):
    setUp = test_custom_modules.CustomModules.setUp
    mock = test_dotfiles.Fixture.mock
    calls = test_dotfiles.Fixture.calls
    snapshot = test_dotfiles.Fixture.snapshot
    assert_failed = test_dotfiles.Fixture.assert_failed
    run_cli = test_dotfiles.Fixture.run_cli
    minimal_modules = test_dotfiles.Fixture.minimal_modules
    fake_native = test_custom_modules.CustomModules.fake_native
    binary = test_custom_modules.CustomModules.binary
    pin = test_custom_modules.CustomModules.pin
    fake_repository = test_custom_modules.CustomModules.fake_repository
    run_module = test_custom_modules.CustomModules.run_module

    def shadow(self, directory, version="3.0.0"):
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "opencode"
        path.write_text(f'#!{test_dotfiles.BASH}\nprintf executed > "$HOME/shadow-ran"\nprintf "%s\\n" "{version}"\n')
        path.chmod(0o755)
        return path

    def guard(self):
        return subprocess.run(
            [test_dotfiles.BASH, "-c", 'set -euo pipefail; ROOT=$1; source "$ROOT/lib/dotfiles.sh"; preflight_native_opencode_paths',
             "opencode-path-test", str(self.repo)],
            cwd=self.repo, env=self.env, capture_output=True, text=True, timeout=20,
        )

    def assert_refused_read_only(self, result, before, diagnostic="shadows the pinned binary"):
        self.assert_failed(result, diagnostic)
        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.home / "shadow-ran").exists())
        self.assertFalse((self.home / "native-version-ran").exists())
        self.assertFalse(any(c[0] in ("opencode", "sudo", "pacman", "wget", "curl", "paru")
                             for c in self.calls()), self.calls())

    def assert_guard_refused(self, diagnostic="shadows the pinned binary"):
        before = self.snapshot()
        self.assert_refused_read_only(self.guard(), before, diagnostic)

    def test_all_path_entries_reject_unmanaged_any_version_without_execution(self):
        self.fake_native()
        # Native first must not conceal later unmanaged binaries.
        for location in ("home/.bun/bin", "home/npm global/bin", "usr/local/bin"):
            for version in ("2.0.29", "3.0.0", "not-a-version"):
                with self.subTest(location=location, version=version):
                    shadow = self.shadow(self.base / location, version)
                    self.env["PATH"] = os.pathsep.join((str(self.native.parent), str(self.path), str(shadow.parent)))
                    self.assert_guard_refused()
                    shadow.unlink()

    def test_empty_current_directory_entries_in_every_position(self):
        self.shadow(self.repo)
        for value in (f":{self.path}", f"{self.path}:", f"{self.path}::{self.path}"):
            with self.subTest(path=value):
                self.env["PATH"] = value
                self.assert_guard_refused()

    def test_relative_paths_and_spaces_are_not_split_or_ignored(self):
        self.shadow(self.repo / "relative bin")
        self.env["PATH"] = f"{self.path}:relative bin"
        self.assert_guard_refused()

    def test_dangling_path_symlink_is_refused(self):
        (self.path / "opencode").symlink_to(self.base / "missing")
        self.assert_guard_refused("Dangling OpenCode shadow")

    def test_executable_symlink_to_unmanaged_binary_is_refused(self):
        target = self.shadow(self.base / "manual")
        (self.path / "opencode").symlink_to(target)
        self.assert_guard_refused()

    def test_native_alias_chains_and_directory_aliases_are_allowed_unexecuted(self):
        self.fake_native()
        alias = self.base / "alias"
        alias.symlink_to(self.native)
        (self.path / "opencode").symlink_to(alias)
        directory_alias = self.base / "native bin alias"
        directory_alias.symlink_to(self.native.parent, target_is_directory=True)
        self.env["PATH"] += f":{directory_alias}"
        before = self.snapshot()
        result = self.guard()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.home / "native-version-ran").exists())

    def test_hardlink_is_not_a_native_symlink_alias(self):
        self.fake_native()
        os.link(self.native, self.path / "opencode")
        self.assert_guard_refused()

    def test_nonexecutable_path_file_is_ignored_but_startup_path_is_protected(self):
        nonexecutable = self.path / "opencode"
        nonexecutable.write_text("not executable")
        result = self.guard()
        self.assertEqual(0, result.returncode, result.stderr)
        startup = self.home / ".local/bin/opencode"
        startup.parent.mkdir(parents=True)
        startup.write_text("not executable")
        self.assert_guard_refused()

    def test_unselected_unmanaged_path_refused_before_download_for_other_groups(self):
        self.minimal_modules()
        self.mock("stow", "sys.exit(0 if '--simulate' in sys.argv else 97)")
        (self.path / "paru").unlink()
        self.shadow(self.path)
        for command in (("install",), ("update", "system")):
            for dry_run in ((), ("--dry-run",)):
                with self.subTest(command=command, dry_run=dry_run):
                    before = self.snapshot()
                    result = self.run_cli(*command, "--groups", "cloud", *dry_run)
                    self.assert_refused_read_only(result, before)

    def test_module_read_only_check_refuses_path_binary_before_repository_query(self):
        self.fake_repository()
        self.shadow(self.path)
        before = self.snapshot()
        self.assert_refused_read_only(self.run_module("opencode", "--check"), before)

    def test_standalone_bootstrap_guards_match_library_exactly(self):
        bootstrap = (test_dotfiles.ROOT / "install.sh").read_text()
        library = (test_dotfiles.ROOT / "lib/dotfiles.sh").read_text()
        for name in ("preflight_native_opencode_paths", "check_native_opencode_path"):
            with self.subTest(function=name):
                pattern = rf"^{name}\(\) \{{\n.*?^\}}"
                standalone = re.search(pattern, bootstrap, re.MULTILINE | re.DOTALL)
                shared = re.search(pattern, library, re.MULTILINE | re.DOTALL)
                self.assertIsNotNone(standalone)
                self.assertIsNotNone(shared)
                self.assertEqual(shared.group(), standalone.group())

    def test_bootstrap_missing_git_refuses_unmanaged_path_before_any_transaction(self):
        (self.path / "git").unlink()
        for location in ("home/.bun/bin", "home/npm global/bin", "usr/local/bin"):
            shadow = self.shadow(self.base / location)
            self.env["PATH"] = f"{self.path}:{shadow.parent}"
            original = shadow.read_bytes(), shadow.stat().st_mode
            for dry_run in ((), ("--dry-run",)):
                with self.subTest(location=location, dry_run=dry_run):
                    before = self.snapshot()
                    result = self.run_cli(*dry_run, bootstrap=True)
                    self.assert_refused_read_only(result, before)
                    self.assertEqual(original, (shadow.read_bytes(), shadow.stat().st_mode))
            shadow.unlink()

    def test_bootstrap_missing_git_allows_native_alias_without_execution_in_dry_run(self):
        (self.path / "git").unlink()
        self.fake_native()
        (self.path / "opencode").symlink_to(self.native)
        before = self.snapshot()
        result = self.run_cli("--dry-run", bootstrap=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.home / "native-version-ran").exists())
        self.assertFalse(any(c[0] in ("opencode", "pacman", "sudo", "wget", "curl")
                             for c in self.calls()), self.calls())


if __name__ == "__main__":
    unittest.main()
