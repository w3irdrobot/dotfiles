"""Exercise Bash's actual prompt expansion, not eval or a simulated parser."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")


class PromptSafety(unittest.TestCase):
    def run_prompt(self, text, helper):
        with tempfile.TemporaryDirectory(prefix="prompt-tests-") as directory:
            script = r'''
source "$1"
__prompt_dir() { printf ordinary-directory; }
__prompt_git() { printf ordinary-branch; }
__prompt_aws() { printf ordinary-aws; }
__prompt_gcloud() { printf ordinary-gcloud; }
__prompt_k8s() { printf ordinary-context; }
__prompt_attack() { printf UNEXPECTED_EXECUTION >&2; }
eval "$2() { printf '%s' \"\$TEST_TEXT\"; }"
__prompt_command
printf '%s' "${PS1@P}"
'''
            return subprocess.run(
                [BASH, "--noprofile", "--norc", "-c", script, "prompt-test",
                 str(ROOT / "shell/prompt.sh"), helper],
                env={"HOME": directory, "PATH": os.defpath, "TEST_TEXT": text},
                cwd=directory, capture_output=True, text=True, timeout=10,
            )

    def test_dynamic_text_cannot_execute_commands_or_prompt_escapes(self):
        for helper in ("__prompt_dir", "__prompt_git", "__prompt_aws",
                       "__prompt_gcloud", "__prompt_k8s"):
            for text in ("$(__prompt_attack)", "`__prompt_attack`", r"\w\u\h\n",
                         '${__prompt_attack}', 'quotes " and apostrophe \''):
                with self.subTest(helper=helper, text=text):
                    result = self.run_prompt(text, helper)
                    self.assertEqual(0, result.returncode, result.stderr)
                    self.assertEqual("", result.stderr)
                    self.assertIn(text, result.stdout)

    def test_terminal_controls_are_replaced_in_dynamic_text(self):
        result = self.run_prompt("name\x1b[2J\r\n\t\x07\x7fend", "__prompt_dir")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("name?[2J?????end", result.stdout)


if __name__ == "__main__":
    unittest.main()
