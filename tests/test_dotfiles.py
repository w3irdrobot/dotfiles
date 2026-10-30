"""Fixture-only CLI safety checks. Mocks are not installation verification."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")
GIT = shutil.which("git")
STOW = shutil.which("stow")


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dotfiles-tests-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home = self.base / "home"
        self.home.mkdir()
        self.repo = self.base / "repo"
        self.repo.mkdir()
        # Copy only runtime inputs, never the checkout's Git metadata or private files.
        for name in ("install.sh", ".gitignore", "bin", "lib", "modules", "stow",
                      "shell", "examples", "repos", "scripts", "agent-config"):
            source = ROOT / name
            if source.is_dir():
                shutil.copytree(source, self.repo / name, symlinks=True)
            elif source.exists():
                shutil.copy2(source, self.repo / name)
        self.path = self.base / "path"
        self.path.mkdir()
        self.log = self.base / "commands.jsonl"
        self.env = {
            "HOME": str(self.home), "PATH": str(self.path), "LC_ALL": "C",
            "XDG_CONFIG_HOME": str(self.home / ".config"),
            "XDG_DATA_HOME": str(self.home / ".local/share"),
            "XDG_STATE_HOME": str(self.home / ".local/state"),
            "TMPDIR": str(self.base), "TEST_LOG": str(self.log),
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
        }
        self.os_release = self.base / "os-release"
        self.os_release.write_text('ID=fedora\nVERSION_ID=44\nNAME="Fedora Linux"\n')
        self.terminal = self.base / "terminal-input"
        self.terminal.write_text("")
        self.destination = self.home / "projects/github.com/w3irdrobot/dotfiles"
        # Fixture copies replace only fixed host paths, not behavior or host checks.
        # This keeps Linux checks runnable on macOS without production-only test flags.
        for name in ("install.sh", "lib/dotfiles.sh", "lib/hardware.sh", "lib/fedora.sh", "lib/bitwarden.sh", "lib/discord.sh", "modules/nix.sh", "modules/system76.sh"):
            path = self.repo / name
            if path.exists():
                text = path.read_text().replace("/etc/os-release", str(self.os_release))
                if name == 'install.sh':
                    text = text.replace('/dev/tty', str(self.terminal))
                text = text.replace("/sys/class/dmi/id", str(self.base / "dmi"))
                text = text.replace("/etc/yum.repos.d", str(self.base / "repos"))
                text = text.replace("/usr/bin/bitwarden", str(self.base.resolve() / "usr/bin/bitwarden"))
                text = text.replace("/opt/Bitwarden/bitwarden", str(self.base.resolve() / "opt/Bitwarden/bitwarden"))
                text = text.replace("/usr/bin/discord", str(self.base / "usr/bin/discord"))
                for fixed in ("/usr/bin/nix", "/nix", "/etc/nix", "/run/systemd/system"):
                    text = re.sub(r"(?<![A-Za-z0-9_/])" + re.escape(fixed),
                                  str(self.base / fixed.lstrip("/")), text)
                path.write_text(text)
        (self.base / "run/systemd/system").mkdir(parents=True)
        for name in ("bash", "dirname", "basename", "readlink", "realpath", "find",
                     "sort", "cat", "grep", "sed", "awk", "tr", "cut", "head", "tail",
                     "mkdir", "mktemp", "rm", "rmdir", "ln", "cp", "mv", "chmod", "date",
                      "id", "wc", "tee", "env", "sleep", "touch", "python3"):
            target = shutil.which(name)
            if target:
                (self.path / name).symlink_to(target)
        self.mock("uname", 'print("Linux" if "-s" in sys.argv else "x86_64")')
        # Fixture hosts use a non-Btrfs root, so upgrade snapshot tests opt in.
        self.mock("findmnt", 'print("ext4") if "FSTYPE" in sys.argv else print("/")')
        for name in ("sudo", "dnf", "rpm", "pacman", "yay", "paru", "makepkg", "curl", "wget",
                     "brew", "nix-env", "systemctl", "chsh", "flatpak", "git", "stow"):
            self.mock(name, "sys.exit(97)")
        self.mock("rpm", "sys.exit(1)")
        self.mock("ghostty", "sys.exit(0)")
        self.mock("kwriteconfig6", "sys.exit(0)")
        # BSD realpath lacks GNU -m; use stdlib's equivalent in the mocked PATH.
        self.mock("realpath", "print(os.path.realpath(sys.argv[-1]))")

    def mock(self, name, body):
        path = self.path / name
        if path.is_symlink():
            path.unlink()
        path.write_text(
            f"#!{sys.executable}\nimport json, os, sys\n"
            "with open(os.environ['TEST_LOG'], 'a') as log:\n"
            "    log.write(json.dumps([os.path.basename(sys.argv[0]), *sys.argv[1:]]) + '\\n')\n"
            + body + "\n"
        )
        path.chmod(0o755)

    def calls(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def snapshot(self):
        return {str(p.relative_to(self.home)): (
            "link", os.readlink(p)) if p.is_symlink() else (
            "dir", "") if p.is_dir() else ("file", p.read_bytes())
            for p in self.home.rglob("*")}

    def run_cli(self, *args, bootstrap=False):
        script = self.repo / ("install.sh" if bootstrap else "bin/dotfiles")
        self.assertTrue(script.is_file(), f"Required CLI is missing: {script.name}")
        return subprocess.run([BASH, str(script), *args], cwd=self.repo, env=self.env,
                              text=True, capture_output=True, timeout=20)

    def assert_failed(self, result, diagnostic=None):
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        if diagnostic:
            self.assertIn(diagnostic.lower(), (result.stdout + result.stderr).lower())

    def test_invalid_arguments_do_not_mutate(self):
        for args in (("wat",), ("link", "--unknown"), ("link", "--groups"),
                     ("link", "--groups", "unknown"), ("update", "wat")):
            with self.subTest(args=args):
                before = self.snapshot()
                self.assert_failed(self.run_cli(*args))
                self.assertEqual(before, self.snapshot())
                self.assertFalse([c for c in self.calls() if c[0] != "uname"])

    def test_unsupported_host_refuses_install(self):
        self.mock("uname", 'print("FreeBSD" if "-s" in sys.argv else "x86_64")')
        self.assert_failed(self.run_cli("install"))
        self.assertEqual({}, self.snapshot())
        self.assertFalse([c for c in self.calls() if c[0] != "uname"])

    def test_unsupported_distribution_refuses_install(self):
        self.os_release.write_text("ID=ubuntu\n")
        self.assert_failed(self.run_cli("install"), "Only Fedora KDE Plasma Desktop 44")
        self.assertEqual({}, self.snapshot())
        self.assertFalse([c for c in self.calls() if c[0] != "uname"])

    def test_custom_xdg_config_home_refuses_before_mutation(self):
        self.env["XDG_CONFIG_HOME"] = str(self.home / "custom-config")
        for bootstrap, args in ((True, ()), (False, ("install",)),
                                (False, ("link",)), (False, ("update", "all"))):
            with self.subTest(bootstrap=bootstrap, args=args):
                before = self.snapshot()
                self.assert_failed(self.run_cli(*args, bootstrap=bootstrap),
                                   "Custom XDG_CONFIG_HOME is unsupported")
                self.assertEqual(before, self.snapshot())
                self.assertFalse([c for c in self.calls() if c[0] != "uname"])

    def test_shipped_metadata_can_be_planned(self):
        self.mock("stow", "sys.exit(0 if '--simulate' in sys.argv else 97)")
        result = self.run_cli("link", "--dry-run")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual({}, self.snapshot())

    def test_dry_run_never_invokes_operational_commands(self):
        self.minimal_modules()
        self.git_fixture()
        self.mock("stow", "sys.exit(0 if '--simulate' in sys.argv else 97)")
        self.mock("pacman", "sys.exit(0 if '-Si' in sys.argv else 97)")
        for args in (("install",), ("link",), ("update", "configs"),
                     ("update", "system"), ("update", "all")):
            with self.subTest(args=args):
                before = self.snapshot()
                result = self.run_cli(*args, "--dry-run")
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                self.assertEqual(before, self.snapshot(), result.stdout + result.stderr)
                self.assertFalse([c for c in self.calls() if c[0] not in
                                  ("uname", "git", "stow", "pacman")], self.calls())
                self.assertTrue(all("--simulate" in c for c in self.calls() if c[0] == "stow"))
                self.assertTrue(all("-Si" in c for c in self.calls() if c[0] == "pacman"))
                self.assertFalse(any(arg in ("fetch", "pull", "clone", "push")
                                     for c in self.calls() if c[0] == "git" for arg in c[1:]))

    def minimal_modules(self):
        (self.repo / "modules").mkdir(exist_ok=True)
        for path in (self.repo / "modules").glob("*.conf"):
            path.unlink()
        if (self.repo / "stow").exists():
            shutil.rmtree(self.repo / "stow")
        for name, group in (("fixture-core", "core"), ("fixture-ai", "ai"),
                            ("fixture-desktop", "desktop"), ("fixture-cloud", "cloud")):
            (self.repo / "modules" / f"{name}.conf").write_text(f"group={group}\npackages=\n")
            directory = self.repo / "stow" / name
            directory.mkdir(parents=True)
            (directory / f".{name}").write_text(name + "\n")

    def real_stow(self):
        if not STOW:
            self.skipTest("GNU Stow unavailable; install it to exercise real link behavior")
        version = subprocess.run([STOW, "--version"], capture_output=True, text=True, check=True)
        if "GNU Stow" not in version.stdout:
            self.skipTest("stow is not GNU Stow")
        (self.path / "stow").unlink()
        (self.path / "stow").symlink_to(STOW)
        # Stow uses /usr/bin/env perl on some platforms.
        perl = shutil.which("perl")
        if perl:
            (self.path / "perl").symlink_to(perl)

    def test_selected_modules_and_repeat_link(self):
        self.minimal_modules()
        self.real_stow()
        for _ in range(2):
            result = self.run_cli("link", "--groups", "core")
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertTrue((self.home / ".fixture-core").is_symlink())
            self.assertEqual("fixture-core\n", (self.home / ".fixture-core").read_text())
            for name in ("ai", "desktop", "cloud"):
                self.assertFalse((self.home / f".fixture-{name}").exists())

    def test_selected_module_plan_without_stow_dependency(self):
        self.minimal_modules()
        self.mock("stow", "sys.exit(0 if '--simulate' in sys.argv else 97)")
        result = self.run_cli("link", "--groups", "core,cloud", "--dry-run")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        calls = [c for c in self.calls() if c[0] == "stow"]
        self.assertTrue(calls)
        for call in calls:
            self.assertIn("fixture-core", call)
            self.assertIn("fixture-cloud", call)
            self.assertNotIn("fixture-ai", call)
            self.assertNotIn("fixture-desktop", call)
        self.assertEqual({}, self.snapshot())

    def opt_in_modules(self):
        self.minimal_modules()
        for name, group in (("fixture-desktop", "desktop"), ("fixture-cloud", "cloud")):
            (self.repo / "modules" / f"{name}.conf").write_text(
                f"group={group}\npackages={name}-package\ndefault=false\n"
            )
        self.mock("stow", "sys.exit(0 if '--simulate' in sys.argv else 97)")
        self.mock("pacman", "sys.exit(0 if '-Si' in sys.argv else 97)")

    def assert_stow_selection(self, selected, excluded):
        calls = [c for c in self.calls() if c[0] == "stow"]
        self.assertTrue(calls)
        for call in calls:
            for name in selected:
                self.assertIn(name, call)
            for name in excluded:
                self.assertNotIn(name, call)

    def test_default_false_modules_are_not_planned(self):
        self.opt_in_modules()
        result = self.run_cli("link", "--groups", "core,ai,desktop,cloud", "--dry-run")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assert_stow_selection(
            ("fixture-core", "fixture-ai"), ("fixture-desktop", "fixture-cloud")
        )
        self.assertEqual({}, self.snapshot())

    def test_explicit_modules_are_additive_across_groups(self):
        self.opt_in_modules()
        result = self.run_cli("link", "--groups", "core", "--modules",
                              "fixture-desktop,fixture-cloud", "--dry-run")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assert_stow_selection(
            ("fixture-core", "fixture-desktop", "fixture-cloud"), ("fixture-ai",)
        )
        self.assertEqual({}, self.snapshot())

    def test_dry_run_keeps_unselected_off_modules_and_local_files_untouched(self):
        self.opt_in_modules()
        target = self.home / ".fixture-cloud"
        target.write_text("local config\n")
        before = self.snapshot()
        result = self.run_cli("install", "--modules", "fixture-desktop", "--dry-run")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assert_stow_selection(
            ("fixture-core", "fixture-ai", "fixture-desktop"), ("fixture-cloud",)
        )
        self.assertEqual(before, self.snapshot())
        self.assertFalse(any("fixture-cloud-package" in c for c in self.calls()))
        self.assertFalse(any(c[0] in ("sudo", "curl", "wget", "paru") for c in self.calls()))

    def test_unknown_and_invalid_module_selectors_refuse_without_writes(self):
        self.minimal_modules()
        for value in ("unknown", "fixture-core,unknown", "", ",fixture-core",
                      "fixture-core,", "fixture-core,,fixture-ai", "../fixture-core"):
            with self.subTest(value=value):
                before = self.snapshot()
                self.assert_failed(self.run_cli("link", "--modules", value))
                self.assertEqual(before, self.snapshot())
                self.assertFalse(any(c[0] not in ("uname",) for c in self.calls()))
        self.assert_failed(self.run_cli("link", "--modules"))

    def test_invalid_default_boolean_refused_by_installer(self):
        self.minimal_modules()
        for value in ("", "False", "0", "yes", "$(touch marker)"):
            with self.subTest(value=value):
                (self.repo / "modules/fixture-desktop.conf").write_text(
                    f"group=desktop\npackages=\ndefault={value}\n"
                )
                self.assert_failed(self.run_cli("link", "--dry-run"), "default")
                self.assertEqual({}, self.snapshot())
                self.assertFalse(any(c[0] != "uname" for c in self.calls()))

    def test_custom_module_failure_stops_before_linking(self):
        self.minimal_modules()
        self.mock("sudo", "[print(a) for a in sys.argv[1:] if not a.startswith('-')] if 'repoquery' in sys.argv else None")
        self.mock("pacman", "sys.exit(0 if '-Si' in sys.argv else 1)")
        self.mock("stow", "sys.exit(0)")
        (self.repo / "modules/fixture-cloud.sh").write_text(
            "#!/usr/bin/env bash\nprintf 'fixture module failed\\n' >&2\nexit 43\n"
        )
        marker = self.base / "later-module-ran"
        (self.repo / "modules/fixture-z-after.conf").write_text("group=cloud\npackages=\n")
        (self.repo / "modules/fixture-z-after.sh").write_text(
            f"#!/usr/bin/env bash\ntouch {str(marker)!r}\n"
        )
        result = self.run_cli("install", "--groups", "cloud")
        self.assert_failed(result, "fixture module failed")
        self.assertEqual(43, result.returncode)
        self.assertFalse(marker.exists())
        self.assertEqual({}, self.snapshot())
        self.assertFalse(any(c[0] == "stow" and "--simulate" not in c for c in self.calls()))

    def test_config_updates_preserve_scope_and_opt_ins_after_one_restart(self):
        self.opt_in_modules()
        self.git_fixture()
        self.mock("stow", "sys.exit(0)")
        self.mock("sudo", "[print(a) for a in sys.argv[1:] if not a.startswith('-')] if 'repoquery' in sys.argv else None")
        self.mock("pacman", "sys.exit(0 if '-Si' in sys.argv else 1)")
        self.mock("paru", "print('paru v2.1.0') if '--version' in sys.argv else None")
        self.mock("flatpak", "sys.exit(0 if sys.argv[1:] == ['update', '--user'] else 97)")
        for scope in ("configs", "all"):
            with self.subTest(scope=scope):
                self.log.unlink(missing_ok=True)
                result = self.run_cli(
                    "update", scope, "--groups", "core", "--modules", "fixture-desktop"
                )
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                fetches = [c for c in self.calls() if c[0] == "git" and "fetch" in c]
                self.assertEqual(1, len(fetches), self.calls())
                self.assertEqual(scope == "all", any(c[0] == "sudo" for c in self.calls()))
                self.assertEqual(scope == "all", any(c == ['flatpak', 'update', '--user'] for c in self.calls()))
                self.assertIn(f"Complete: update {scope}", result.stderr)
                self.assert_stow_selection(
                    ("fixture-core", "fixture-desktop"), ("fixture-cloud",)
                )
                self.assertEqual({}, self.snapshot())

    def test_default_groups_exclude_cloud(self):
        self.minimal_modules()
        self.real_stow()
        result = self.run_cli("link")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        for name in ("core", "ai", "desktop"):
            self.assertTrue((self.home / f".fixture-{name}").is_symlink())
        self.assertFalse((self.home / ".fixture-cloud").exists())

    def test_existing_file_and_dangling_symlink_refused(self):
        self.minimal_modules()
        target = self.home / ".fixture-core"
        for dangling in (False, True):
            with self.subTest(dangling=dangling):
                if dangling:
                    target.symlink_to(self.home / "missing")
                else:
                    target.write_text("user-owned\n")
                before = self.snapshot()
                self.assert_failed(self.run_cli("link", "--groups", "core"), "conflict")
                self.assertEqual(before, self.snapshot())
                target.unlink()

    def test_parent_file_conflict_refused(self):
        self.minimal_modules()
        source = self.repo / "stow/fixture-core/.config/tool/config"
        source.parent.mkdir(parents=True)
        source.write_text("managed\n")
        (self.home / ".config").write_text("user-owned\n")
        before = self.snapshot()
        self.assert_failed(self.run_cli("link", "--groups", "core"), "conflict")
        self.assertEqual(before, self.snapshot())

    def test_symlink_parent_conflict_refused(self):
        self.minimal_modules()
        source = self.repo / "stow/fixture-core/.config/tool/config"
        source.parent.mkdir(parents=True)
        source.write_text("managed\n")
        external = self.base / "external"
        external.mkdir()
        (self.home / ".config").symlink_to(external)
        before = self.snapshot()
        self.assert_failed(self.run_cli("link", "--groups", "core"), "conflict")
        self.assertEqual(before, self.snapshot())
        self.assertEqual([], list(external.iterdir()))

    def test_metadata_is_not_executed(self):
        self.minimal_modules()
        marker = self.home / "metadata-executed"
        (self.repo / "modules/fixture-core.conf").write_text(
            f"group=core\npackages=$(touch {marker})\n"
        )
        self.assert_failed(self.run_cli("link", "--groups", "core"), "invalid package")
        self.assertFalse(marker.exists())

    def local_git(self, *args):
        self.assertIsNotNone(GIT, "git is required for local repository safety fixtures")
        return subprocess.run([GIT, "-C", str(self.repo), *args], env={
            **self.env, "PATH": os.defpath,
            "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
            "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        }, capture_output=True, text=True, check=True)

    def git_fixture(self):
        self.local_git("init", "-b", "master")
        self.local_git("add", ".")
        self.local_git("commit", "-m", "fixture")
        self.local_git("remote", "add", "origin", "git@github.com:w3irdrobot/dotfiles.git")
        self.local_git("update-ref", "refs/remotes/origin/master", "HEAD")
        self.local_git("config", "branch.master.remote", "origin")
        self.local_git("config", "branch.master.merge", "refs/heads/master")
        # Never permit real Git network operations. Read operations use fixture Git.
        self.mock("git", f"""import subprocess
args = sys.argv[1:]
if any(arg in ('clone', 'fetch', 'pull', 'push', 'ls-remote') for arg in args):
    sys.exit(0 if 'fetch' in args else 97)
sys.exit(subprocess.run([{GIT!r}, *args], check=False).returncode)""")

    def test_update_refuses_dirty_repo(self):
        self.git_fixture()
        (self.repo / "untracked-user-file").write_text("local work\n")
        before = self.snapshot()
        self.assert_failed(self.run_cli("update", "configs"), "dirty")
        self.assertEqual("local work\n", (self.repo / "untracked-user-file").read_text())
        self.assertEqual(before, self.snapshot())
        self.assertFalse(any("fetch" in call or "pull" in call for call in self.calls()))

    def test_update_refuses_unexpected_origin(self):
        self.git_fixture()
        self.local_git("remote", "set-url", "origin", "https://example.invalid/not-dotfiles.git")
        self.assert_failed(self.run_cli("update", "configs"), "unexpected origin")
        self.assertFalse(any("fetch" in call or "pull" in call for call in self.calls()))

    def test_update_refuses_divergence(self):
        self.git_fixture()
        initial = self.local_git("rev-parse", "HEAD").stdout.strip()
        (self.repo / "local-only").write_text("local\n")
        self.local_git("add", "local-only")
        self.local_git("commit", "-m", "local branch")
        local_head = self.local_git("rev-parse", "HEAD").stdout.strip()
        tree = self.local_git("rev-parse", initial + "^{tree}").stdout.strip()
        remote = self.local_git(
            "commit-tree", tree, "-p", initial, "-m", "remote branch"
        ).stdout.strip()
        self.local_git("update-ref", "refs/remotes/origin/master", remote)
        self.assert_failed(self.run_cli("update", "configs"), "diverg")
        self.assertEqual(local_head, self.local_git("rev-parse", "HEAD").stdout.strip())
        self.assertEqual("local\n", (self.repo / "local-only").read_text())

    def test_bootstrap_clone_failure_stops(self):
        self.mock("git", "sys.exit(0 if 'check-ref-format' in sys.argv else 97)")
        result = self.run_cli(bootstrap=True)
        self.assert_failed(result)
        self.assertTrue(
            any("clone" in call for call in self.calls()), result.stdout + result.stderr
        )
        self.assertFalse([c for c in self.calls() if c[0] not in ("git", "uname")])

    def test_bootstrap_dry_run_no_writes_or_network(self):
        self.mock("git", "sys.exit(0 if 'check-ref-format' in sys.argv else 97)")
        result = self.run_cli("--dry-run", bootstrap=True)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual({}, self.snapshot())
        self.assertFalse([c for c in self.calls() if c[0] not in ("uname", "git")])
        self.assertTrue(all("check-ref-format" in c for c in self.calls() if c[0] == "git"))

    def test_bootstrap_never_dispatches_path_dotfiles(self):
        self.mock("dotfiles", "sys.exit(0)")
        marker = self.base / "dispatched"
        (self.repo / "bin").mkdir(exist_ok=True)
        dispatcher = self.repo / "bin/setup"
        arguments = self.base / "dispatch-arguments"
        dispatcher.write_text(
            f"#!/usr/bin/env bash\nprintf 'local checkout' > {str(marker)!r}\n"
            f"printf '%s\\n' \"$@\" > {str(arguments)!r}\n"
        )
        dispatcher.chmod(0o755)
        self.mock("git", f"""import shutil
if 'clone' in sys.argv:
    shutil.copytree({str(self.repo)!r}, sys.argv[-1], symlinks=True)
    sys.exit(0)
if 'check-ref-format' in sys.argv:
    sys.exit(0)
sys.exit(97)""")
        result = self.run_cli(
            "--groups", "core", "--modules", "fixture-desktop,fixture-cloud", bootstrap=True
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual("local checkout", marker.read_text())
        self.assertEqual(
            ["--groups", "core", "--modules", "fixture-desktop,fixture-cloud"],
            arguments.read_text().splitlines(),
        )
        self.assertFalse(any(c[0] == "dotfiles" for c in self.calls()))

    def test_bootstrap_failed_update_stops(self):
        self.git_fixture()
        destination = self.destination
        destination.parent.mkdir(parents=True)
        shutil.copytree(self.repo, destination, symlinks=True)
        self.mock("git", f"""import subprocess
args = sys.argv[1:]
if any(arg in ('clone', 'fetch', 'pull', 'push', 'ls-remote') for arg in args):
    sys.exit(97)
sys.exit(subprocess.run([{GIT!r}, *args], check=False).returncode)""")
        self.mock("dotfiles", "sys.exit(0)")
        self.assert_failed(self.run_cli(bootstrap=True))
        self.assertTrue(any(c[0] == "git" for c in self.calls()))
        self.assertTrue(any("fetch" in c for c in self.calls()))
        self.assertFalse(any(c[0] == "dotfiles" for c in self.calls()))


if __name__ == "__main__":
    unittest.main()
