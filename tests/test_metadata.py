"""Offline tests for the metadata validation tool, not the installer parser."""

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import subprocess
from types import SimpleNamespace

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check-packages.py"
SPEC = importlib.util.spec_from_file_location("check_packages", SCRIPT)
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


class Metadata(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dotfiles-metadata-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "modules").mkdir()
        self.patch = patch.object(CHECK, "ROOT", self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def write(self, text):
        (self.root / "modules/fixture.conf").write_text(text)

    def test_packages_are_deduplicated(self):
        self.write("# metadata\ngroup=core\npackages=git stow git example-bin\n")
        self.assertEqual({"git", "stow", "example-bin"}, CHECK.metadata())

    def test_shell_payload_is_rejected_as_data(self):
        self.write("group=core\npackages=$(touch marker)\n")
        with self.assertRaisesRegex(ValueError, "invalid package"):
            CHECK.metadata()

    def test_shell_statements_are_rejected(self):
        self.write("touch marker\n")
        with self.assertRaisesRegex(ValueError, "key=value"):
            CHECK.metadata()

    def test_missing_modules_fail_clearly(self):
        with self.assertRaisesRegex(ValueError, "No modules"):
            CHECK.metadata()

    def test_default_boolean_is_strict(self):
        for value in ("true", "false"):
            with self.subTest(value=value):
                self.write(f"group=desktop\npackages=fixture\ndefault={value}\n")
                self.assertEqual({"fixture"}, CHECK.metadata())
        for value in ("", "False", "0", "yes", "$(touch marker)"):
            with self.subTest(value=value):
                self.write(f"group=desktop\npackages=fixture\ndefault={value}\n")
                with self.assertRaisesRegex(ValueError, "true or false"):
                    CHECK.metadata()

    def test_duplicate_default_rejected(self):
        self.write("group=desktop\npackages=\ndefault=true\ndefault=false\n")
        with self.assertRaisesRegex(ValueError, "duplicate default"):
            CHECK.metadata()

    def test_off_modules_still_have_package_names_validated(self):
        self.write("group=desktop\ndefault=false\npackages=$(touch marker)\n")
        with self.assertRaisesRegex(ValueError, "invalid package"):
            CHECK.metadata()


class RemoteMetadata(unittest.TestCase):
    def test_queries_exact_names_without_installing(self):
        with patch.object(CHECK.shutil, "which", return_value="dnf"), patch.object(
            CHECK.subprocess, "run", return_value=SimpleNamespace(stdout="docs\nbinary\nbinary\n")
        ) as run:
            CHECK.validate_remote({"docs", "binary"})
        command = run.call_args.args[0]
        self.assertIn("repoquery", command)
        self.assertIn("--arch=x86_64,noarch", command)
        self.assertEqual('%{name}\\n', command[command.index('--queryformat') + 1])
        self.assertNotIn("install", command)
        self.assertNotIn("sudo", command)

    def test_missing_names_are_reported_without_fallback(self):
        with patch.object(CHECK.shutil, "which", return_value="dnf"), patch.object(
            CHECK.subprocess, "run", return_value=SimpleNamespace(stdout="fixture-extra\n")
        ):
            with self.assertRaisesRegex(ValueError, "Packages absent.*fixture"):
                CHECK.validate_remote({"fixture"})

    def test_dnf_errors_propagate_instead_of_looking_like_missing_packages(self):
        with patch.object(CHECK.shutil, "which", return_value="dnf"), patch.object(
            CHECK.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "dnf")
        ):
            with self.assertRaises(subprocess.CalledProcessError):
                CHECK.validate_remote({"fixture"})

    def test_missing_dnf_reports_environment_requirement(self):
        with patch.object(CHECK.shutil, "which", return_value=None):
            with self.assertRaisesRegex(ValueError, "requires Fedora 44"):
                CHECK.validate_remote({"fixture"})
