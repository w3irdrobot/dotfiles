"""Update and linking regressions using disposable homes and offline Git refs."""

import os
import shutil
import stat
import subprocess
import unittest

import test_dotfiles


class UpdateSafety(unittest.TestCase):
    # Reuse fixture helpers, not Fixture's test methods.
    setUp = test_dotfiles.Fixture.setUp
    mock = test_dotfiles.Fixture.mock
    calls = test_dotfiles.Fixture.calls
    snapshot = test_dotfiles.Fixture.snapshot
    run_cli = test_dotfiles.Fixture.run_cli
    assert_failed = test_dotfiles.Fixture.assert_failed
    minimal_modules = test_dotfiles.Fixture.minimal_modules
    local_git = test_dotfiles.Fixture.local_git
    git_fixture = test_dotfiles.Fixture.git_fixture

    def ignored_collision(self):
        self.minimal_modules()
        (self.repo / ".gitignore").write_text("local-secret\n")
        self.git_fixture()
        initial = self.local_git("rev-parse", "HEAD").stdout.strip()
        secret = self.repo / "local-secret"
        secret.write_text("upstream replacement\n")
        self.local_git("add", "--force", "local-secret")
        self.local_git("commit", "-m", "upstream adds previously ignored file")
        remote = self.local_git("rev-parse", "HEAD").stdout.strip()
        # Only our disposable fixture's refs/index move. No user checkout resets.
        self.local_git("update-ref", "refs/heads/master", initial)
        self.local_git("read-tree", initial)
        self.local_git("update-ref", "refs/remotes/origin/master", remote)
        secret.write_text("local private content\n")
        self.assertEqual("", self.local_git("status", "--porcelain").stdout)
        return initial

    def assert_protected_merge(self):
        merges = [call for call in self.calls() if call[0] == "git" and "merge" in call]
        self.assertTrue(merges, self.calls())
        self.assertTrue(all("--ff-only" in call and "--no-overwrite-ignore" in call
                            for call in merges))

    def test_config_update_preserves_ignored_local_file(self):
        initial = self.ignored_collision()
        result = self.run_cli("update", "configs")
        self.assert_failed(result, "overwritten")
        self.assert_protected_merge()
        self.assertEqual("local private content\n", (self.repo / "local-secret").read_text())
        self.assertEqual(initial, self.local_git("rev-parse", "HEAD").stdout.strip())
        self.assertFalse((self.home / ".local/bin/dotfiles").exists())

    def test_bootstrap_update_preserves_ignored_local_file(self):
        initial = self.ignored_collision()
        self.destination.parent.mkdir(parents=True)
        shutil.copytree(self.repo, self.destination, symlinks=True)
        result = self.run_cli(bootstrap=True)
        self.assert_failed(result, "overwritten")
        self.assert_protected_merge()
        self.assertEqual("local private content\n",
                         (self.destination / "local-secret").read_text())
        head = self.local_git("-C", str(self.destination), "rev-parse", "HEAD").stdout.strip()
        self.assertEqual(initial, head)
        self.assertFalse(any(call[0] == "sudo" for call in self.calls()))

    def test_unknown_update_selector_fails_before_fetch_or_merge(self):
        self.minimal_modules()
        self.git_fixture()
        for scope in ("configs", "all"):
            with self.subTest(scope=scope):
                result = self.run_cli("update", scope, "--modules", "unknown")
                self.assert_failed(result, "unknown module selector")
        self.assertFalse(any(call[0] == "git" and
                             any(arg in ("fetch", "merge") for arg in call)
                             for call in self.calls()))
        self.assertEqual({}, self.snapshot())

    def mock_linking(self):
        self.mock("stow", "sys.exit(0)")

    def test_launcher_created_on_link_and_reused(self):
        self.minimal_modules()
        self.mock_linking()
        for _ in range(2):
            result = self.run_cli("link", "--groups", "core")
            self.assertEqual(0, result.returncode, result.stderr)
            launcher = self.home / ".local/bin/dotfiles"
            self.assertTrue(launcher.is_symlink())
            self.assertEqual(str((self.repo / "bin/dotfiles").resolve()), os.readlink(launcher))
        self.assertFalse((self.repo / "stow/fixture-core/.local/bin/dotfiles").exists())

    def test_launcher_is_on_path_and_works_outside_the_checkout(self):
        self.minimal_modules()
        self.mock_linking()
        result = self.run_cli("link", "--groups", "core")
        self.assertEqual(0, result.returncode, result.stderr)
        environment = self.env | {
            "PATH": str(self.home / ".local/bin") + os.pathsep + self.env["PATH"],
        }
        before = self.snapshot()
        result = subprocess.run(
            ["dotfiles", "--help"], cwd=self.base, env=environment,
            capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("Usage: dotfiles", result.stdout)
        self.assertEqual(before, self.snapshot())

    def test_launcher_conflict_precedes_packages(self):
        self.minimal_modules()
        launcher = self.home / ".local/bin/dotfiles"
        launcher.parent.mkdir(parents=True)
        for is_link in (False, True):
            with self.subTest(is_link=is_link):
                if is_link:
                    launcher.symlink_to(self.base / "missing-command")
                else:
                    launcher.write_text("user-owned command\n")
                before = self.snapshot()
                result = self.run_cli("install")
                self.assert_failed(result, "dotfiles launcher")
                self.assertEqual(before, self.snapshot())
                self.assertFalse(any(call[0] in ("sudo", "pacman", "paru", "stow")
                                     for call in self.calls()))
                launcher.unlink()

    def test_launcher_symlink_parent_is_refused(self):
        self.minimal_modules()
        external = self.base / "external"
        external.mkdir()
        (self.home / ".local").symlink_to(external)
        result = self.run_cli("install", "--dry-run")
        self.assert_failed(result, "launcher parent")
        self.assertEqual([], list(external.iterdir()))
        self.assertFalse(any(call[0] == "sudo" for call in self.calls()))

    def test_obsolete_arch_helpers_are_not_executed(self):
        self.minimal_modules()
        self.mock_linking()
        for body in ("sys.exit(42)", 'print("not the expected AUR helper")'):
            with self.subTest(body=body):
                self.mock("paru", body)
                result = self.run_cli("install", "--groups", "core", "--dry-run")
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertFalse(any(call[0] in ("sudo", "pacman", "makepkg", "paru")
                                     for call in self.calls()))
                self.assertEqual({}, self.snapshot())

    def test_fedora_dry_run_does_not_require_arch_tools(self):
        self.minimal_modules()
        self.mock_linking()
        self.mock("paru", 'print("paru v42.8.1 - libalpm v99.0.0")')
        result = self.run_cli("install", "--groups", "core", "--dry-run")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse(any(call[0] == "paru" for call in self.calls()))
        self.assertFalse(any(call[0] == "makepkg" for call in self.calls()))
        self.assertFalse((self.home / ".local/bin/dotfiles").exists())

    def ssh_fixture(self):
        self.minimal_modules()
        (self.repo / "modules/ssh.conf").write_text("group=core\npackages=\n")
        source = self.repo / "stow/ssh/.ssh"
        source.mkdir(parents=True)
        (source / "config").write_text("Host fixture\n  HostName example.invalid\n")
        source.chmod(0o755)
        (source / "config").chmod(0o644)
        # macOS chmod treats -- after the mode as a filename. Exercise Linux argv
        # semantics in the fixture, without weakening production's Linux target.
        self.mock("chmod", """mode = int(sys.argv[1], 8)
for path in sys.argv[2:]:
    if path != '--':
        os.chmod(path, mode)""")
        self.mock_linking()
        return source

    def test_ssh_link_restores_source_and_live_directory_modes_only(self):
        source = self.ssh_fixture()
        live = self.home / ".ssh"
        live.mkdir(mode=0o755)
        key = live / "private-key-fixture"
        key.write_text("untouched fixture bytes\n")
        key.chmod(0o640)
        result = self.run_cli("link", "--groups", "core")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(0o700, stat.S_IMODE(source.stat().st_mode))
        self.assertEqual(0o600, stat.S_IMODE((source / "config").stat().st_mode))
        self.assertEqual(0o700, stat.S_IMODE(live.stat().st_mode))
        self.assertEqual(os.getuid(), live.stat().st_uid)
        self.assertEqual(0o640, stat.S_IMODE(key.stat().st_mode))
        self.assertEqual("untouched fixture bytes\n", key.read_text())

    def test_ssh_fresh_directory_created_private_after_preflight(self):
        self.ssh_fixture()
        result = self.run_cli("link", "--groups", "core")
        self.assertEqual(0, result.returncode, result.stderr)
        live = self.home / ".ssh"
        self.assertFalse(live.is_symlink())
        self.assertEqual(0o700, stat.S_IMODE(live.stat().st_mode))
        self.assertEqual(os.getuid(), live.stat().st_uid)

    def test_config_update_restores_ssh_permissions_without_installing_launcher(self):
        source = self.ssh_fixture()
        self.git_fixture()
        result = self.run_cli("update", "configs", "--groups", "core")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(0o700, stat.S_IMODE(source.stat().st_mode))
        self.assertEqual(0o600, stat.S_IMODE((source / "config").stat().st_mode))
        self.assertEqual(0o700, stat.S_IMODE((self.home / ".ssh").stat().st_mode))
        self.assertFalse((self.home / ".local/bin/dotfiles").exists())
        self.assertFalse(any(call[0] in ("sudo", "pacman", "paru") for call in self.calls()))

    def test_ssh_dry_run_does_not_create_directory_or_change_modes(self):
        source = self.ssh_fixture()
        result = self.run_cli("link", "--groups", "core", "--dry-run")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual({}, self.snapshot())
        self.assertEqual(0o755, stat.S_IMODE(source.stat().st_mode))
        self.assertEqual(0o644, stat.S_IMODE((source / "config").stat().st_mode))

    def test_ssh_check_is_read_only_and_refuses_symlink_directory(self):
        source = self.ssh_fixture()
        script = self.repo / "modules/ssh.sh"
        result = subprocess.run([test_dotfiles.BASH, str(script), "--check"],
                                cwd=self.repo, env=self.env, text=True, capture_output=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual({}, self.snapshot())
        self.assertEqual(0o755, stat.S_IMODE(source.stat().st_mode))
        external = self.base / "external-ssh"
        external.mkdir()
        (self.home / ".ssh").symlink_to(external)
        result = self.run_cli("install", "--groups", "core")
        self.assert_failed(result)
        self.assertEqual([], list(external.iterdir()))
        self.assertFalse(any(call[0] == "sudo" for call in self.calls()))

    def test_conflict_preflight_prevents_ssh_permission_changes(self):
        source = self.ssh_fixture()
        (self.home / ".fixture-core").write_text("unmanaged\n")
        result = self.run_cli("link", "--groups", "core")
        self.assert_failed(result, "conflict")
        self.assertFalse((self.home / ".ssh").exists())
        self.assertEqual(0o755, stat.S_IMODE(source.stat().st_mode))
        self.assertEqual(0o644, stat.S_IMODE((source / "config").stat().st_mode))

    def test_docker_opt_in_without_selection_fails_before_packages(self):
        self.minimal_modules()
        self.mock_linking()
        result = self.run_cli("install", "--docker-group", "--groups", "core")
        self.assert_failed(result, "requires Docker")
        self.assertFalse(any(call[0] in ("sudo", "pacman", "paru") for call in self.calls()))
        self.assertEqual({}, self.snapshot())

    def test_selected_docker_dry_run_does_not_require_installed_group(self):
        self.minimal_modules()
        self.mock_linking()
        (self.repo / "modules/docker.conf").write_text("group=cloud\npackages=docker\n")
        self.mock("pacman", "sys.exit(0 if '-Si' in sys.argv else 97)")
        result = self.run_cli("install", "--groups", "cloud", "--docker-group", "--dry-run")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual({}, self.snapshot())
        self.assertFalse(any(call[0] in ("sudo", "paru", "getent") for call in self.calls()))


if __name__ == "__main__":
    unittest.main()
