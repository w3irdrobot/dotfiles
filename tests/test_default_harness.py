"""Exercise real module selection without platform checks or provisioning."""

import os
from pathlib import Path
import runpy
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DefaultHarness(unittest.TestCase):
    def selected(self, explicit="", groups="ai", expected_error=None):
        with tempfile.TemporaryDirectory(prefix="harness-selection-") as home:
            result = subprocess.run(
                [shutil.which("bash"), "--noprofile", "--norc", "-c", """
set -euo pipefail
ROOT=$1
source "$ROOT/lib/dotfiles.sh"
GROUPS_CSV=$3
MODULES_CSV=$2
validate_groups
validate_module_selectors
load_modules
printf '%s\\n' "${MODULES[@]}"
printf 'package:%s\\n' "${PACKAGES[@]}"
printf 'stow:%s\\n' "${STOW_PACKAGES[@]}"
""", "harness-selection", str(ROOT), explicit, groups],
                env={"PATH": os.environ["PATH"], "HOME": home, "LC_ALL": "C"},
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(list(Path(home).iterdir()), [])
            if expected_error is not None:
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected_error, result.stderr)
                self.assertEqual(result.stdout, "")
                return set()
            self.assertEqual(result.returncode, 0, result.stderr)
            return set(result.stdout.splitlines())

    def test_default_ai_uses_opencode_not_claude(self):
        selected = self.selected()
        modules = {name for name in selected if ":" not in name}
        self.assertEqual(modules, {"opencode", "nono"})

    def test_removed_modules_reject_explicit_selectors(self):
        for module in ("claude-code", "spotify"):
            with self.subTest(module=module):
                self.selected(module, expected_error=f"Unknown module selector: {module}")

    def test_removed_integrations_have_no_source_targets(self):
        for module in ("claude-code", "spotify"):
            with self.subTest(module=module):
                self.assertFalse((ROOT / "modules" / f"{module}.conf").exists())
                self.assertFalse((ROOT / "modules" / f"{module}.sh").exists())
                self.assertFalse((ROOT / "stow" / module).exists())

    def test_no_group_selects_removed_integration_targets(self):
        selected = self.selected(groups="core,ai,desktop,cloud,bitcoin,hardware")
        for module in ("claude-code", "spotify"):
            with self.subTest(module=module):
                self.assertNotIn(module, selected)
                self.assertNotIn(f"package:{module}", selected)
                self.assertNotIn(f"stow:{module}", selected)

    def test_package_metadata_excludes_removed_integrations(self):
        metadata = runpy.run_path(str(ROOT / "scripts/check-packages.py"))["metadata"]
        packages = metadata()
        self.assertTrue(packages)
        self.assertTrue(packages.isdisjoint({"claude-code", "spotify"}))
