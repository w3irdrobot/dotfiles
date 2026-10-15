"""Offline tests for the metadata validation tool, not the installer parser."""

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.parse

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
    def test_arch_any_and_x86_64_match_without_aur_lookup(self):
        def response(url):
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
            self.assertNotIn("arch", query)
            name = query["name"][0]
            return {"results": [{"pkgname": name, "arch": "any" if name == "docs" else "x86_64"}]}

        with patch.object(CHECK, "get_json", side_effect=response) as fetch:
            CHECK.validate_remote({"docs", "binary"})
        self.assertEqual(2, fetch.call_count)

    def test_wrong_name_or_architecture_falls_back_to_aur(self):
        for item in ({"pkgname": "fixture-extra", "arch": "any"},
                     {"pkgname": "fixture", "arch": "aarch64"}):
            with self.subTest(item=item):
                with patch.object(CHECK, "get_json", side_effect=[
                    {"results": [item]}, {"results": [{"Name": "fixture"}]},
                ]) as fetch:
                    CHECK.validate_remote({"fixture"})
                self.assertIn("aur.archlinux.org/rpc", fetch.call_args.args[0])

    def test_missing_names_are_reported_across_all_aur_batches(self):
        names = {f"fixture-{i:02}" for i in range(51)}
        with patch.object(CHECK, "get_json", return_value={"results": []}) as fetch:
            with self.assertRaises(ValueError) as error:
                CHECK.validate_remote(names)
        self.assertEqual(53, fetch.call_count)
        self.assertEqual(
            "Packages absent from Arch (x86_64/any) and AUR: " + ", ".join(sorted(names)),
            str(error.exception),
        )

    def test_aur_rpc_error_is_not_reported_as_missing_packages(self):
        with patch.object(CHECK, "get_json", side_effect=[
            {"results": []}, {"type": "error", "error": "rate limited"},
        ]):
            with self.assertRaisesRegex(ValueError, "AUR RPC error: rate limited"):
                CHECK.validate_remote({"fixture"})
