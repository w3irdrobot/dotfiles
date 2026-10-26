"""DNF/RPM fixtures, not evidence of an actual Fedora installation."""

import shlex
import shutil
import subprocess
import unittest

import test_dotfiles


class Fedora(unittest.TestCase):
    mock = test_dotfiles.Fixture.mock
    calls = test_dotfiles.Fixture.calls
    snapshot = test_dotfiles.Fixture.snapshot
    run_cli = test_dotfiles.Fixture.run_cli
    assert_failed = test_dotfiles.Fixture.assert_failed
    minimal_modules = test_dotfiles.Fixture.minimal_modules

    def setUp(self):
        test_dotfiles.Fixture.setUp(self)
        self.dest = self.base / "repos"
        self.dest.mkdir()
        (self.path / "cmp").symlink_to(shutil.which("cmp"))
        self.mock("rpm", "sys.exit(1)")
        self.mock("sudo", """from pathlib import Path
import shutil
args = sys.argv[1:]
if args[0] == 'cp':
    source, target = map(Path, args[-2:])
    if not target.exists() and not target.is_symlink():
        shutil.copy2(source, target)
elif args[0] == 'dnf':
    if os.environ.get('TEST_DNF_FAIL') in args:
        sys.exit(43)
    if 'repoquery' in args:
        start = args.index('--queryformat') + 2
        queryformat = args[start - 1].replace('\\\\n', '\\n')
        for name in args[start:]:
            if name != os.environ.get('TEST_MISSING'):
                sys.stdout.write(queryformat.replace('%{name}', name))
else:
    sys.exit(97)
""")

    def library(self, body, dry_run=False):
        return subprocess.run(
            [test_dotfiles.BASH, "-c", 'set -euo pipefail; ROOT=$1; DRY_RUN=$2; source "$ROOT/lib/dotfiles.sh"\n' + body,
             "fedora-fixture", str(self.repo), str(int(dry_run))],
            cwd=self.repo, env=self.env, text=True, capture_output=True, timeout=20,
        )

    def packages(self, modules=("brave",), packages=("brave-browser",), dry_run=False):
        body = "MODULES=(" + " ".join(map(shlex.quote, modules)) + ")\n"
        body += "PACKAGES=(" + " ".join(map(shlex.quote, packages)) + ")\ninstall_packages\n"
        return self.library(body, dry_run)

    def transactions(self):
        return [c for c in self.calls() if c[:2] == ["sudo", "dnf"] and any(a in c for a in ("upgrade", "install"))]

    def test_fedora_44_is_the_only_supported_distribution_version(self):
        self.minimal_modules()
        self.mock("stow", "sys.exit(0)")
        for text in ("ID=arch\n", "ID=manjaro\n", "ID=fedora\nVERSION_ID=43\n", "ID=fedora\nVERSION_ID=45\n"):
            self.os_release.write_text(text)
            self.assert_failed(self.run_cli("link", "--dry-run"), "Only Fedora KDE Plasma Desktop 44")
            self.assertEqual({}, self.snapshot())
        self.os_release.write_text('ID="fedora"\nVERSION_ID="44"\n')
        result = self.run_cli("link", "--dry-run")
        self.assertEqual(0, result.returncode, result.stderr)

    def test_refreshed_rpm_metadata_precedes_upgrade_and_install(self):
        result = self.packages()
        self.assertEqual(0, result.returncode, result.stderr)
        transactions = self.transactions()
        self.assertEqual(2, len(transactions))
        self.assertIn("upgrade", transactions[0])
        self.assertIn("install", transactions[1])
        for command in transactions:
            self.assertIn("--setopt=cacheonly=metadata", command)
            self.assertNotIn("--cacheonly", command)
            self.assertIn("--best", command)
            self.assertNotIn("--assumeyes", command)
        queries = [c for c in self.calls() if "repoquery" in c]
        refresh = next(c for c in self.calls() if "makecache" in c)
        self.assertLess(self.calls().index(refresh), self.calls().index(queries[0]))
        self.assertLess(self.calls().index(queries[-1]), self.calls().index(transactions[0]))
        self.assertTrue((self.dest / "dotfiles-brave.repo").is_file())

    def test_opencode_does_not_enable_the_copr_serving_v1(self):
        result = self.packages(modules=("opencode",), packages=())
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse((self.dest / "dotfiles-opencode.repo").exists())
        self.assertFalse(any("opencode" in c for c in self.transactions()))

    def test_missing_selected_package_aborts_before_upgrade(self):
        self.env["TEST_MISSING"] = "fixture-missing"
        result = self.packages(modules=(), packages=("fixture-missing",))
        self.assert_failed(result, "RPM package unavailable: fixture-missing")
        self.assertEqual([], self.transactions())

    def test_dnf5_queries_explicitly_separate_package_names(self):
        result = self.packages(modules=(), packages=('git', 'stow', 'curl'))
        self.assertEqual(0, result.returncode, result.stderr)
        queries = [c for c in self.calls() if 'repoquery' in c]
        self.assertTrue(queries)
        for query in queries:
            self.assertEqual('%{name}\\n', query[query.index('--queryformat') + 1])
        self.assertEqual(2, len(self.transactions()))

    def test_dnf_failures_stop_later_phases_and_preserve_status(self):
        for action in ("makecache", "upgrade", "install"):
            with self.subTest(action=action):
                self.log.unlink(missing_ok=True)
                self.env["TEST_DNF_FAIL"] = action
                result = self.packages(modules=(), packages=())
                self.assertEqual(43, result.returncode, result.stderr)
                if action != "install":
                    self.assertFalse(any("install" in c for c in self.transactions()))

    def test_missing_git_bootstrap_dnf_failure_stops_before_clone(self):
        (self.path / "git").unlink()
        self.env["TEST_DNF_FAIL"] = "install"
        result = self.run_cli(bootstrap=True)
        self.assertEqual(43, result.returncode, result.stderr)
        self.assertFalse(self.destination.exists())
        self.assertTrue(any(c[:2] == ["sudo", "dnf"] and "git" in c and "install" in c for c in self.calls()))
        self.assertFalse(any(c[0] == "git" for c in self.calls()))

    def test_dry_run_does_not_query_download_or_change_repositories(self):
        before = self.snapshot()
        result = self.packages(dry_run=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([], self.calls())
        self.assertEqual([], list(self.dest.iterdir()))
        self.assertEqual(before, self.snapshot())

    def test_full_default_install_dry_run_has_no_mutations_or_network(self):
        self.mock("stow", "sys.exit(0 if '--simulate' in sys.argv else 97)")
        before = self.snapshot()
        result = self.run_cli("install", "--dry-run")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(before, self.snapshot())
        self.assertIn("Would download/verify pinned Bitwarden", result.stderr)
        self.assertIn("PLAN ONLY", result.stdout)
        self.assertNotIn("dotfiles-opencode.repo", result.stderr)
        self.assertFalse(any(c[0] in ("sudo", "curl", "wget", "dnf", "pacman", "paru") for c in self.calls()))

    def test_repository_conflict_or_dangling_symlink_refuses_before_sudo(self):
        target = self.dest / "dotfiles-brave.repo"
        for symlink in (False, True):
            if symlink:
                target.symlink_to(self.base / "missing")
            else:
                target.write_text("unmanaged repository")
            self.log.unlink(missing_ok=True)
            self.assert_failed(self.packages(), "Repository")
            self.assertFalse(any(c[0] == "sudo" for c in self.calls()))
            target.unlink()

    def test_repeated_repository_setup_does_not_overwrite_matching_files(self):
        for _ in range(2):
            result = self.packages()
            self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(1, len([c for c in self.calls() if c[:2] == ["sudo", "cp"]]))

    def test_sources_are_selection_scoped_and_system76_is_not_a_wildcard(self):
        result = self.library('MODULES=(brave ghostty system76); selected_repositories; printf "%s\\n" "${REPOSITORIES[@]}"\n')
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(["brave", "ghostty", "system76"], result.stdout.splitlines())
        for path in (self.repo / "repos").glob("*.repo"):
            text = path.read_text()
            self.assertIn("gpgcheck=1", text)
            self.assertIn("includepkgs=", text)
            self.assertIn("skip_if_unavailable=0", text)
            self.assertNotIn("includepkgs=system76*", text)

    def test_manual_applications_are_reported_not_claimed_installed(self):
        self.mock("stow", "sys.exit(0)")
        result = self.run_cli("link", "--groups", "hardware", "--modules", "sparrow")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("applications were NOT installed", result.stdout)
        self.assertIn("sparrow:", result.stdout)

    def test_native_nix_requires_the_official_fedora_packages(self):
        result = self.library("require_native_nix_repository\n")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(3, len(self.calls()))
        self.assertTrue(all("--repo=fedora" in c and "--repo=updates" in c for c in self.calls()))
        self.env["TEST_MISSING"] = "nix-daemon"
        self.assert_failed(self.library("require_native_nix_repository\n"), "nix-daemon is unavailable")
