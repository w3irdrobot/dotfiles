"""Read-only DMI selection and Plasma guidance; not hardware verification."""

import subprocess
import unittest

import test_dotfiles


class Hardware(unittest.TestCase):
    setUp = test_dotfiles.Fixture.setUp
    calls = test_dotfiles.Fixture.calls
    snapshot = test_dotfiles.Fixture.snapshot
    run_cli = test_dotfiles.Fixture.run_cli
    mock = test_dotfiles.Fixture.mock

    def dmi(self, vendor, model="lemp14"):
        directory = self.base / "dmi"
        directory.mkdir(exist_ok=True)
        (directory / "sys_vendor").write_text(vendor)
        (directory / "product_name").write_text(model)

    def helper(self, groups="core,desktop", modules="", tail=""):
        script = '''set -euo pipefail
ROOT=$1
source "$ROOT/lib/dotfiles.sh"
GROUPS_CSV=$2 MODULES_CSV=$3 DRY_RUN=1 DOCKER_GROUP=0
validate_groups
validate_module_selectors
load_modules
printf 'MODULES: %s\\n' "${MODULES[*]}"
printf 'PACKAGES: %s\\n' "${PACKAGES[*]}"
'''
        return subprocess.run(
            [test_dotfiles.BASH, "-c", script + tail, "hardware-test",
             str(self.repo), groups, modules], env=self.env, cwd=self.repo,
            text=True, capture_output=True, timeout=20)

    def test_system76_variants_select_support_and_plasma(self):
        for vendor in ("System76\n", " SYSTEM76 \n", "System76, Inc.\n"):
            with self.subTest(vendor=vendor):
                self.dmi(vendor)
                result = self.helper()
                self.assertEqual(0, result.returncode, result.stderr)
                for package in ("system76-driver", "system76-firmware",
                                "system76-power", "firmware-manager",
                                "xdg-desktop-portal-kde", "wl-clipboard"):
                    self.assertIn(package, result.stdout)
                self.assertIn("lemp14", result.stderr)
                self.assertNotIn("dkms", result.stdout)

    def test_missing_other_and_similar_vendors_skip_support_even_hardware_group(self):
        for vendor in (None, "LENOVO", "NotSystem76", "System76 impostor"):
            with self.subTest(vendor=vendor):
                if vendor is not None:
                    self.dmi(vendor)
                result = self.helper(groups="core,hardware")
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertNotIn("system76-driver", result.stdout)
                self.assertNotIn("system76-power", result.stdout)

    def test_explicit_selection_cannot_bypass_detection(self):
        result = self.helper(modules="system76")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("requires confirmed System76", result.stderr)

    def test_other_group_does_not_implicitly_select_hardware(self):
        self.dmi("System76")
        result = self.helper(groups="desktop")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertNotIn("system76-power", result.stdout)
        explicit = self.helper(groups="desktop", modules="system76")
        self.assertEqual(0, explicit.returncode, explicit.stderr)
        self.assertIn("system76-power", explicit.stdout)

    def test_unreadable_vendor_skips_support(self):
        self.dmi("System76")
        vendor = self.base / "dmi/sys_vendor"
        vendor.chmod(0)
        self.addCleanup(vendor.chmod, 0o600)
        result = self.helper()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertNotIn("system76-power", result.stdout)
        self.assertIn("DMI vendor unavailable", result.stderr)

    def test_model_control_characters_not_logged(self):
        self.dmi("System76", "lemp14\x1b[31m")
        result = self.helper()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertNotIn("\x1b", result.stderr)
        self.assertIn("model: unknown", result.stderr)

    def test_repeated_selection_and_followups_have_no_mutations(self):
        self.dmi("System76")
        before = self.snapshot()
        for _ in range(2):
            result = self.helper(tail='system76_next_steps\n')
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("Resolve backend conflicts manually", result.stdout)
            self.assertIn("PowerDevil", result.stdout)
            self.assertEqual(before, self.snapshot())
        self.assertFalse(any(call[0] in ("sudo", "systemctl", "pacman", "paru")
                             for call in self.calls()))

    def test_session_reporting_accepts_wayland_x11_and_tty(self):
        for session, expected in (("wayland", "Desktop session: Wayland"),
                                  ("x11", "Select Plasma (Wayland)"),
                                  ("tty", "unknown/TTY")):
            with self.subTest(session=session):
                self.env["XDG_SESSION_TYPE"] = session
                result = self.helper(tail='report_desktop_session\n')
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn(expected, result.stderr)

    def test_system76_cli_dry_run_plans_packages_without_provisioning(self):
        self.dmi("System76")
        self.os_release.write_text('ID=fedora\nVERSION_ID=44\n')
        (self.path / "paru").unlink()
        self.mock("pacman", "sys.exit(0 if '-Si' in sys.argv else 1)")
        self.mock("stow", "sys.exit(0)")
        self.env["XDG_SESSION_TYPE"] = "wayland"
        before = self.snapshot()
        result = self.run_cli("install", "--groups", "hardware", "--modules",
                              "plasma", "--dry-run")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("system76-driver", result.stderr)
        self.assertIn("Desktop session: Wayland", result.stderr)
        self.assertIn("PLAN ONLY", result.stdout)
        self.assertNotIn("Next steps:", result.stdout)
        self.assertEqual(before, self.snapshot())
        self.assertFalse(any(call[0] in ("sudo", "systemctl", "paru", "curl", "wget")
                             for call in self.calls()))
        self.assertTrue(all(call[1] in ("-Si", "-Qqo", "-Qq")
                            for call in self.calls() if call[0] == "pacman"))


if __name__ == "__main__":
    unittest.main()
