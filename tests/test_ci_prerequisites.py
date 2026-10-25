"""Offline regression checks for CI tool parity and helper runtime metadata."""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Prerequisites(unittest.TestCase):
    def test_comparison_helpers_declare_diffutils(self):
        for module, group in (("diffutils", "core"), ("nono", "ai"), ("gnupg", "core")):
            with self.subTest(module=module):
                fields = dict(
                    line.split("=", 1)
                    for line in (ROOT / "modules" / f"{module}.conf").read_text().splitlines()
                    if line and not line.startswith("#")
                )
                self.assertEqual(group, fields["group"])
                self.assertIn("diffutils", fields["packages"].split())

    def test_fedora_fixture_runner_supplies_cmp(self):
        workflow = (ROOT / ".github/workflows/validate.yml").read_text()
        install = re.search(r"dnf install --assumeyes (.*?) &&", workflow)
        self.assertIsNotNone(install)
        self.assertIn("diffutils", install.group(1).split())

    def test_ci_formatter_is_pinned_and_verified_before_execution(self):
        workflow = (ROOT / ".github/workflows/validate.yml").read_text()
        self.assertNotRegex(workflow, r"apt-get install[^\n]*\bshfmt\b")
        self.assertIn(
            "https://github.com/mvdan/sh/releases/download/v3.14.1/"
            "shfmt_v3.14.1_linux_amd64", workflow
        )
        self.assertIn(
            "76e77641faa025814b77f153b29796b8e6fa2fca03e0c76a691608b86c7ea7bf",
            workflow,
        )
        self.assertIn('mktemp -d "$RUNNER_TEMP/shfmt.XXXXXX"', workflow)
        verification = workflow.index("sha256sum --check --strict -")
        self.assertLess(verification, workflow.index('chmod +x "$tool_dir/shfmt"'))
        self.assertLess(verification, workflow.index('"$tool_dir/shfmt" --version'))
        self.assertLess(verification, workflow.index('>> "$GITHUB_PATH"'))
