"""Exercise real module selection without platform checks or provisioning."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DefaultHarness(unittest.TestCase):
    def selected(self, explicit=""):
        with tempfile.TemporaryDirectory(prefix="harness-selection-") as home:
            result = subprocess.run(
                [shutil.which("bash"), "--noprofile", "--norc", "-c", """
set -euo pipefail
ROOT=$1
source "$ROOT/lib/dotfiles.sh"
GROUPS_CSV=ai
MODULES_CSV=$2
validate_groups
validate_module_selectors
load_modules
printf '%s\\n' "${MODULES[@]}"
""", "harness-selection", str(ROOT), explicit],
                env={"PATH": os.environ["PATH"], "HOME": home, "LC_ALL": "C"},
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(list(Path(home).iterdir()), [])
            return set(result.stdout.splitlines())

    def test_default_ai_uses_opencode_not_claude(self):
        self.assertEqual(self.selected(), {"opencode", "nono"})

    def test_claude_remains_explicitly_opt_in(self):
        self.assertEqual(self.selected("claude-code"), {"opencode", "nono", "claude-code"})
