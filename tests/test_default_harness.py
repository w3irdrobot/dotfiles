"""Exercise real module selection without platform checks or provisioning."""

import os
import json
from pathlib import Path
import runpy
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DefaultHarness(unittest.TestCase):
    def test_setup_profile_does_not_grant_the_entire_owner_namespace(self):
        profile = json.loads((ROOT / "stow/nono/.config/nono/profiles/opencode-setup.json").read_text())
        grants = profile["filesystem"]["allow"]
        self.assertIn("$HOME/projects/github.com/w3irdrobot/dotfiles", grants)
        self.assertNotIn("$HOME/projects/github.com/w3irdrobot", grants)

    def test_machine_exports_example_stays_outside_checkout(self):
        example = (ROOT / "examples/local-variables.sh").read_text()
        self.assertIn("~/.config/bash/variables.sh", example)
        self.assertIn("inherited by child processes", example)
        self.assertIn("credential injection", example)
        for name in ("EXA_API_KEY", "GITHUB_TOKEN", "MAPLE_API_KEY"):
            self.assertNotIn(f"export {name}=", example)

    def test_all_managed_ai_profiles_inherit_private_bash_denial(self):
        base = json.loads((ROOT / "stow/nono/.config/nono/profiles/opencode-base.json").read_text())
        self.assertIn("$HOME/.config/bash", base["filesystem"]["deny"])
        for name in ("dev", "setup"):
            child = json.loads((ROOT / f"stow/nono/.config/nono/profiles/opencode-{name}.json").read_text())
            self.assertEqual("opencode-base", child["extends"])

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
        self.assertEqual(modules, {"opencode", "nono", "agent-config"})

    def test_default_desktop_includes_brave(self):
        selected = self.selected(groups="desktop")
        self.assertIn("brave", selected)
        self.assertIn("package:brave-browser", selected)

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
