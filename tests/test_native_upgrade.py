"""Native repository upgrades are staged and V2-guarded without host operations."""

import shlex
import subprocess
import unittest

import test_dotfiles


class NativeUpgrade(unittest.TestCase):
    setUp_fixture = test_dotfiles.Fixture.setUp
    mock = test_dotfiles.Fixture.mock
    calls = test_dotfiles.Fixture.calls
    snapshot = test_dotfiles.Fixture.snapshot
    assert_failed = test_dotfiles.Fixture.assert_failed

    def setUp(self):
        self.setUp_fixture()
        self.database = self.base / "database-refreshed"
        self.installed = self.base / "packages-installed"
        self.nix_installed = self.base / "native-nix-installed"
        self.nix_setup = self.base / "native-nix-ready"
        self.env.update({
            "TEST_DATABASE_MARKER": str(self.database),
            "TEST_INSTALL_MARKER": str(self.installed),
            "TEST_CACHED_VERSION": "1.8.0-1",
            "TEST_REFRESHED_VERSION": "2.0.29-1",
            "TEST_INSTALLED_OPENCODE": "0",
            "TEST_REPOSITORY": "extra",
            "TEST_OPENCODE_AVAILABLE": "1",
            "TEST_NIX_AVAILABLE": "1",
            "TEST_NIX_UPSTREAM": "0",
            "TEST_NIX_INSTALLED_MARKER": str(self.nix_installed),
            "TEST_NIX_SETUP_MARKER": str(self.nix_setup),
            "TEST_NIX_FEATURES_ACTIVE": "1",
            "TEST_PARU_OFFICIAL": "0",
            "TEST_PARU_PATH": str(self.path / "paru"),
            "TEST_GIT_PATH": str(self.path / "git"),
            "TEST_BOOTSTRAP_GIT": "0",
        })
        self.mock("paru", """if sys.argv[1:] == ['--version']:
    print('paru v2.1.0 - libalpm v15.0.0')
else:
    sys.exit(0)""")
        self.mock("sudo", """from pathlib import Path
args = sys.argv[1:]
if args[0] != 'pacman':
    sys.exit(97)
if '-Syu' in args and '--downloadonly' in args:
    Path(os.environ['TEST_DATABASE_MARKER']).write_text('refreshed indexes and cache only')
elif '-Su' in args and not any('y' in a for a in args[1:] if a.startswith('-')):
    Path(os.environ['TEST_INSTALL_MARKER']).write_text('full upgrade committed')
    if any(a in ('nix', 'extra/nix') for a in args):
        Path(os.environ['TEST_NIX_INSTALLED_MARKER']).write_text('native package installed')
    if os.environ['TEST_BOOTSTRAP_GIT'] == '1':
        target = Path(os.environ['TEST_GIT_PATH'])
        program = '''#!/usr/bin/env bash
case $1 in
    check-ref-format) exit 0 ;;
    clone)
        destination=${@: -1}
        mkdir -p "$destination/bin"
        printf '#!/usr/bin/env bash\\nexit 0\\n' > "$destination/bin/setup"
        exit 0
        ;;
    *) exit 97 ;;
esac
'''
        target.write_text(program)
        target.chmod(0o755)
else:
    sys.exit(97)""")
        self.mock("pacman", """from pathlib import Path
args = sys.argv[1:]
if '-Qq' in args and args[-1] == 'opencode':
    sys.exit(0 if os.environ['TEST_INSTALLED_OPENCODE'] == '1' else 1)
if '-Si' not in args:
    sys.exit(97)
name = args[-1]
if name in ('opencode', 'extra/opencode'):
    if os.environ['TEST_OPENCODE_AVAILABLE'] != '1':
        sys.exit(1)
    synced = Path(os.environ['TEST_DATABASE_MARKER']).exists()
    version = os.environ['TEST_REFRESHED_VERSION' if synced else 'TEST_CACHED_VERSION']
    print('Repository      : ' + os.environ['TEST_REPOSITORY'])
    print('Name            : opencode')
    print('Version         : ' + version)
elif name == 'fixture-aur':
    sys.exit(1)
elif name == 'paru':
    sys.exit(0 if os.environ['TEST_PARU_OFFICIAL'] == '1' else 1)
elif name == 'nix' and os.environ['TEST_NIX_AVAILABLE'] != '1':
    sys.exit(1)
else:
    print('Repository      : extra')
    print('Name            : ' + name)
    print('Version         : 1.0-1')""")
        # Model only the module's public native-Nix contract. Its dedicated tests
        # exercise real package ownership, daemon state, and feature discovery.
        self.mock("nix-policy", """from pathlib import Path
action = sys.argv[1]
if action == 'preflight':
    if os.environ['TEST_NIX_UPSTREAM'] == '1':
        print('Non-pacman upstream/partial Nix installation refused', file=sys.stderr)
        sys.exit(1)
elif action == 'setup':
    if not Path(os.environ['TEST_NIX_INSTALLED_MARKER']).exists():
        print('Native Nix was not installed before setup', file=sys.stderr)
        sys.exit(1)
    if sys.argv[2:] != ['--bootstrap']:
        sys.exit(97)
    Path(os.environ['TEST_NIX_SETUP_MARKER']).write_text('daemon ready before linking')
elif action == 'validate':
    if os.environ['TEST_NIX_FEATURES_ACTIVE'] != '1':
        print('Nix client features are not active', file=sys.stderr)
        sys.exit(1)
else:
    sys.exit(97)""")
        (self.repo / "modules/nix.sh").write_text("""# shellcheck shell=bash
preflight_nix() { nix-policy preflight; }
setup_nix() { if (( ! DRY_RUN )); then nix-policy setup "$@"; fi; }
validate_nix() { nix-policy validate "$@"; }
""")

    def run_packages(self, selected=True, dry_run=False, packages=None,
                     nix_selected=False, build_helper=False, after_link=False):
        if packages is None:
            packages = ["opencode"] if selected else []
        modules = ["opencode"] if selected else ["fixture-core"]
        if nix_selected:
            modules.append("nix")
            packages = [*packages, "nix"]
        group = "ai" if selected else "core"
        script = """set -euo pipefail
ROOT=$1
DRY_RUN=$2
source "$ROOT/lib/dotfiles.sh"
"""
        script += "SELECTED_GROUPS=(" + shlex.quote(group) + ")\n"
        script += "MODULES=(" + " ".join(map(shlex.quote, modules)) + ")\n"
        script += "PACKAGES=(" + " ".join(map(shlex.quote, packages)) + ")\n"
        if build_helper:
            script += "ensure_paru() { paru-build; }\n"
        script += "install_packages\n"
        if after_link:
            script += "STOW_PACKAGES=(); link_configs 0\n"
        return subprocess.run(
            [test_dotfiles.BASH, "-c", script, "native-upgrade-fixture",
             str(self.repo), str(int(dry_run))],
            cwd=self.repo, env=self.env, text=True, capture_output=True, timeout=20,
        )

    def transactions(self):
        return [call for call in self.calls() if call[:2] == ["sudo", "pacman"]]

    def assert_staged_full_upgrade(self):
        transactions = self.transactions()
        self.assertEqual(2, len(transactions), transactions)
        staged, committed = transactions
        self.assertIn("-Syu", staged)
        self.assertIn("--downloadonly", staged)
        self.assertIn("--needed", staged)
        self.assertIn("-Su", committed)
        self.assertIn("--needed", committed)
        self.assertNotIn("--downloadonly", committed)
        self.assertFalse(any("y" in arg for arg in committed[2:] if arg.startswith("-")))
        self.assertFalse(any("-S" in call for call in transactions))
        self.assertTrue(self.database.exists())
        self.assertTrue(self.installed.exists())
        calls = self.calls()
        guard = next(i for i, call in enumerate(calls)
                     if call[0] == "pacman" and call[-1] == "extra/opencode")
        self.assertLess(calls.index(staged), guard)
        self.assertLess(guard, calls.index(committed))

    def test_cached_v1_refreshed_v2_is_accepted_after_staging(self):
        result = self.run_packages()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assert_staged_full_upgrade()
        self.assertIn("extra/opencode", self.transactions()[1])
        self.assertFalse(any(call[0] == "paru" and "-S" in call for call in self.calls()))

    def test_refreshed_v3_aborts_before_any_packages_are_installed(self):
        self.env["TEST_CACHED_VERSION"] = "2.0.29-1"
        self.env["TEST_REFRESHED_VERSION"] = "3.0.0-1"
        result = self.run_packages()
        self.assert_failed(result, "full upgrade is still pending")
        self.assertIn("no packages were installed", result.stderr)
        self.assertIn("databases/cache were refreshed", result.stderr)
        self.assertEqual(1, len(self.transactions()))
        self.assertIn("--downloadonly", self.transactions()[0])
        self.assertTrue(self.database.exists())
        self.assertFalse(self.installed.exists())
        self.assertFalse(any(call[0] == "paru" and "-S" in call for call in self.calls()))

    def test_already_installed_opencode_is_guarded_with_only_core_selected(self):
        self.env["TEST_INSTALLED_OPENCODE"] = "1"
        self.env["TEST_REFRESHED_VERSION"] = "3.0.0-1"
        result = self.run_packages(selected=False)
        self.assert_failed(result, "native Extra V2")
        self.assertFalse(self.installed.exists())
        self.assertEqual(1, len(self.transactions()))

    def test_installed_v2_target_is_included_without_ai_selection(self):
        self.env["TEST_INSTALLED_OPENCODE"] = "1"
        result = self.run_packages(selected=False)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assert_staged_full_upgrade()
        self.assertIn("extra/opencode", self.transactions()[1])

    def test_missing_or_nonextra_opencode_never_falls_back_to_aur(self):
        for setting, value in (("TEST_OPENCODE_AVAILABLE", "0"),
                               ("TEST_REPOSITORY", "unexpected")):
            with self.subTest(setting=setting):
                self.env[setting] = value
                result = self.run_packages()
                self.assert_failed(result, "no packages were installed")
                self.assertFalse(self.installed.exists())
                self.assertFalse(any(call[0] == "paru" and "-S" in call for call in self.calls()))
                self.env[setting] = "1" if setting == "TEST_OPENCODE_AVAILABLE" else "extra"

    def test_dry_run_never_syncs_downloads_installs_or_rejects_stale_cache(self):
        result = self.run_packages(dry_run=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("cached indexes only", result.stderr)
        self.assertIn("real guard", result.stderr)
        self.assertFalse(self.database.exists())
        self.assertFalse(self.installed.exists())
        self.assertEqual([], self.transactions())
        self.assertEqual({}, self.snapshot())
        self.assertTrue(all("-Si" in call for call in self.calls() if call[0] == "pacman"))

    def test_other_official_and_aur_packages_keep_dynamic_ownership(self):
        result = self.run_packages(packages=["opencode", "fixture-official", "fixture-aur", "git"])
        self.assertEqual(0, result.returncode, result.stderr)
        self.assert_staged_full_upgrade()
        committed = self.transactions()[1]
        self.assertIn("fixture-official", committed)
        self.assertEqual(1, committed.count("git"))
        self.assertNotIn("fixture-aur", committed)
        self.assertTrue(any(call[0] == "paru" and "fixture-aur" in call for call in self.calls()))

    def test_installed_package_query_failure_aborts_before_sync(self):
        self.mock("pacman", "sys.exit(42)")
        result = self.run_packages(selected=False)
        self.assert_failed(result, "package ownership")
        self.assertEqual([], self.transactions())
        self.assertFalse(self.database.exists())

    def test_native_nix_is_installed_and_bootstrapped_in_full_transaction(self):
        result = self.run_packages(nix_selected=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assert_staged_full_upgrade()
        self.assertIn("extra/nix", self.transactions()[1])
        preflight = ["nix-policy", "preflight"]
        setup = ["nix-policy", "setup", "--bootstrap"]
        calls = self.calls()
        self.assertLess(calls.index(preflight), calls.index(self.transactions()[0]))
        self.assertGreater(calls.index(setup), calls.index(self.transactions()[1]))
        self.assertTrue(self.nix_setup.exists())

    def test_upstream_or_partial_nix_stops_before_any_package_transaction(self):
        self.env["TEST_NIX_UPSTREAM"] = "1"
        result = self.run_packages(nix_selected=True)
        self.assert_failed(result, "non-pacman upstream/partial")
        self.assertEqual([], self.transactions())
        self.assertFalse(self.database.exists())

    def test_native_nix_dry_run_preflights_without_install_or_service_changes(self):
        result = self.run_packages(nix_selected=True, dry_run=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(any(call == ["nix-policy", "preflight"] for call in self.calls()))
        self.assertFalse(any(call[0] == "nix-policy" and call[1] == "setup" for call in self.calls()))
        self.assertEqual([], self.transactions())
        self.assertFalse(self.database.exists())
        self.assertFalse(self.nix_installed.exists())
        self.assertEqual({}, self.snapshot())

    def test_missing_native_nix_aborts_without_aur_or_upstream_fallback(self):
        self.env["TEST_NIX_AVAILABLE"] = "0"
        result = self.run_packages(nix_selected=True)
        self.assert_failed(result, "No AUR/upstream fallback")
        self.assertEqual(1, len(self.transactions()))
        self.assertFalse(self.installed.exists())
        self.assertFalse(any(call[0] == "paru" and "-S" in call for call in self.calls()))

    def test_aur_helper_needs_native_nix_even_without_core_selected(self):
        (self.path / "paru").unlink()
        self.mock("paru-build", """from pathlib import Path
if not Path(os.environ['TEST_NIX_SETUP_MARKER']).exists():
    print('Nix daemon was not ready before the helper build', file=sys.stderr)
    sys.exit(1)
target = Path(os.environ['TEST_PARU_PATH'])
target.write_text('#!/usr/bin/env bash\\nexit 0\\n')
target.chmod(0o755)""")
        result = self.run_packages(packages=["opencode", "fixture-aur"], build_helper=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assert_staged_full_upgrade()
        committed = self.transactions()[1]
        self.assertIn("base-devel", committed)
        self.assertIn("extra/nix", committed)
        calls = self.calls()
        self.assertLess(calls.index(["nix-policy", "preflight"]), calls.index(self.transactions()[0]))
        self.assertLess(calls.index(["nix-policy", "setup", "--bootstrap"]), calls.index(["paru-build"]))

    def test_linking_selected_nix_requires_active_client_features(self):
        self.env["TEST_NIX_FEATURES_ACTIVE"] = "0"
        result = self.run_packages(nix_selected=True, after_link=True)
        self.assert_failed(result, "client features are not active")
        self.assertTrue(self.installed.exists())
        self.assertTrue(any(call == ["nix-policy", "validate"] for call in self.calls()))

    def test_fresh_v2_guard_does_not_consult_stale_custom_module_metadata(self):
        result = self.run_packages()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assert_staged_full_upgrade()

    def test_bootstrap_git_upgrade_also_refuses_installed_opencode_v3(self):
        (self.path / "git").unlink()
        self.env["TEST_INSTALLED_OPENCODE"] = "1"
        self.env["TEST_REFRESHED_VERSION"] = "3.0.0-1"
        result = subprocess.run([test_dotfiles.BASH, str(self.repo / "install.sh")],
                                cwd=self.repo, env=self.env, text=True,
                                capture_output=True, timeout=20)
        self.assert_failed(result, "native Extra V2")
        self.assertEqual(1, len(self.transactions()))
        self.assertIn("--downloadonly", self.transactions()[0])
        self.assertFalse(self.installed.exists())

    def test_bootstrap_git_upgrade_accepts_refreshed_native_v2(self):
        (self.path / "git").unlink()
        self.env["TEST_INSTALLED_OPENCODE"] = "1"
        self.env["TEST_BOOTSTRAP_GIT"] = "1"
        result = subprocess.run([test_dotfiles.BASH, str(self.repo / "install.sh")],
                                cwd=self.repo, env=self.env, text=True,
                                capture_output=True, timeout=20)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assert_staged_full_upgrade()
        self.assertIn("extra/opencode", self.transactions()[1])

    def test_preflight_opencode_shadow_check_ignores_cached_v1_metadata(self):
        script = 'set -euo pipefail; ROOT=$1; source "$ROOT/lib/dotfiles.sh"; MODULES=(opencode); preflight_custom_modules'
        result = subprocess.run([test_dotfiles.BASH, "-c", script, "shadow-fixture", str(self.repo)],
                                cwd=self.repo, env=self.env, text=True,
                                capture_output=True, timeout=20)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse(any(call[0] == "pacman" for call in self.calls()))


if __name__ == "__main__":
    unittest.main()
