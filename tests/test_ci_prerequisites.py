"""Offline regression checks for CI tool parity and helper runtime metadata."""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Prerequisites(unittest.TestCase):
    def test_both_fedora_jobs_cover_supported_releases(self):
        workflow = (ROOT / ".github/workflows/validate.yml").read_text()
        for job in ("fedora-stow", "package-existence"):
            with self.subTest(job=job):
                # Job properties are indented four spaces; stop only at another job.
                body = re.split(r"\n  [a-z][a-z-]*:", workflow.split(f"  {job}:\n", 1)[1])[0]
                self.assertIn("fedora: [44, 45]", body)
                self.assertIn("registry.fedoraproject.org/fedora:${{ matrix.fedora }}", body)

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

    def test_shfmt_is_not_a_package_or_validation_requirement(self):
        workflow = (ROOT / ".github/workflows/validate.yml").read_text()
        self.assertNotIn("shfmt", workflow)
        self.assertNotIn("shfmt", (ROOT / "scripts/check-shell.py").read_text())
        self.assertFalse((ROOT / "modules/shfmt.conf").exists())

    def test_exit_node_fixtures_have_jq_on_both_runners(self):
        workflow = (ROOT / ".github/workflows/validate.yml").read_text()
        apt = re.search(r"apt-get install --yes ([^\n]+)", workflow)
        dnf = re.search(r"dnf install --assumeyes (.*?) &&", workflow)
        self.assertIsNotNone(apt)
        self.assertIsNotNone(dnf)
        self.assertIn("jq", apt.group(1).split())
        self.assertIn("jq", dnf.group(1).split())
