"""USB picker regression fixtures: mocked discovery/fzf, real jq, no devices/keys."""

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")


@unittest.skipUnless(BASH and shutil.which("jq"), "bash and jq required")
class USBSelection(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="usb-selection-tests-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.definitions = {}
        for name in ("secrets_import", "secrets_export"):
            text = (ROOT / "stow/gnupg/.local/bin" / name).read_text()
            self.assertTrue(text.endswith('main "$@"\n'))
            self.definitions[name] = text.removesuffix('main "$@"\n')

    def run_bash(self, name, devices, body, fzf="cat", status=0, raw=None):
        fixture = self.base / "lsblk.json"
        fixture.write_text(json.dumps({"blockdevices": devices}) if raw is None else raw)
        stubs = f'''
uname() {{ printf 'Linux\\n'; }}
lsblk() {{ cat {shlex.quote(str(fixture))}; return {status}; }}
fzf() {{ {fzf}; }}
gpg() {{ return 99; }}
diskutil() {{ return 99; }}
'''
        return subprocess.run(
            [BASH, "--noprofile", "--norc"],
            input=self.definitions[name] + stubs + body,
            cwd=self.base,
            env={"HOME": str(self.base), "PATH": os.environ["PATH"],
                 "TMPDIR": str(self.base)},
            text=True, capture_output=True, timeout=10,
        )

    def device(self, path="/media/fixture", **kwargs):
        return {"mountpoint": path, "label": "Fixture", "size": "8G",
                "rm": True, **kwargs}

    def test_exact_paths_survive_labels_delimiters_quotes_and_shell_text(self):
        paths = ["/media/Backup (2026) - chosen", '/run/media/alex/drive "quoted"',
                 "/media/$(touch injected) `touch injected` \\ trailing "]
        for name in self.definitions:
            for path in paths:
                with self.subTest(name=name, path=path):
                    result = self.run_bash(name, [self.device(
                        path, label='evil - label (8G) "quote"\t\n\x1b[31m')], '''
records=$(list_removable_media) || exit 10
select_removable_media "$records" 'Select: '
''', fzf="tee picker.rows")
                    self.assertEqual(0, result.returncode, result.stderr)
                    self.assertEqual(path + "\n", result.stdout)
                    rows = (self.base / "picker.rows").read_text()
                    self.assertEqual(1, len(rows.splitlines()))
                    self.assertNotIn("\x1b", rows)
                    self.assertEqual(1, rows.count("\t"))
                    self.assertIn(r"\n", rows)
                    self.assertFalse((self.base / "injected").exists())

    def test_nested_removable_and_hotplug_ancestry_and_mount_guards(self):
        devices = [
            {"rm": True, "children": [{"children": [self.device(
                "/media/nested", rm=False, hotplug=False)]}]},
            self.device("/run/media/alex/hotplug", rm=False, hotplug=True),
            self.device("/media/numeric", rm=1),
            self.device("/media/fixed", rm=False, hotplug=False),
            self.device(None), self.device("/"), self.device("/home/alex"),
            self.device("/mediafake/usb"), self.device("/run/mediafake/usb"),
        ]
        for name in self.definitions:
            with self.subTest(name=name):
                result = self.run_bash(name, devices, "list_removable_media\n")
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual(["/media/nested", "/run/media/alex/hotplug", "/media/numeric"],
                                 [json.loads(line)["mountpoint"] for line in result.stdout.splitlines()])

    def test_second_index_selects_second_original_path(self):
        for name in self.definitions:
            result = self.run_bash(name, [self.device(), self.device("/media/two - exact")], '''
records=$(list_removable_media) || exit 10
select_removable_media "$records" 'Select: '
''', fzf="sed -n '2p'")
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual("/media/two - exact\n", result.stdout)

    def test_controls_in_mountpoints_fail_instead_of_stripping_or_splitting(self):
        for name in self.definitions:
            for control in ("\n", "\t", "\r", "\x00", "\x1b", "\x7f"):
                with self.subTest(name=name, control=repr(control)):
                    result = self.run_bash(name, [self.device(), self.device("/media/a" + control + "b")],
                                           "list_removable_media\n")
                    self.assertNotEqual(0, result.returncode)
                    self.assertEqual("", result.stdout)

    def test_cancel_empty_forged_out_of_range_and_multiple_selection_fail(self):
        modes = ("cat >/dev/null; return 130", "cat >/dev/null",
                 "cat >/dev/null; printf '999\\tforged\\n'",
                 "cat >/dev/null; printf '0\\tforged\\n'",
                 "cat >/dev/null; printf '$(touch injected)\\tforged\\n'", "cat")
        for name in self.definitions:
            for mode in modes:
                with self.subTest(name=name, mode=mode):
                    result = self.run_bash(name, [self.device(), self.device("/media/two")], '''
records=$(list_removable_media) || exit 10
select_removable_media "$records" 'Select: '
''', fzf=mode)
                    self.assertNotEqual(0, result.returncode)
                    self.assertEqual("", result.stdout)
                    self.assertFalse((self.base / "injected").exists())

    def test_malformed_json_schema_and_lsblk_failure_are_not_empty_success(self):
        cases = ("{", "null", "{}", '{"blockdevices":{}}',
                 '{"blockdevices":[{"children":{}}]}',
                 '{"blockdevices":[{"mountpoint":42}]}',
                 '{"blockdevices":[]} {"blockdevices":[]}')
        for name in self.definitions:
            for raw in cases:
                with self.subTest(name=name, raw=raw):
                    result = self.run_bash(name, [], "list_removable_media\n", raw=raw)
                    self.assertNotEqual(0, result.returncode)
                    self.assertEqual("", result.stdout)
            result = self.run_bash(name, [], "list_removable_media\n", status=7)
            self.assertNotEqual(0, result.returncode)

    def test_jq_failure_is_not_masked(self):
        for name in self.definitions:
            result = self.run_bash(name, [], "jq() { return 9; }; list_removable_media\n")
            self.assertNotEqual(0, result.returncode)

    def test_discovery_failure_aborts_main_instead_of_current_directory_fallback(self):
        for name in self.definitions:
            result = self.run_bash(name, [], '''
check_deps() { :; }
list_gpg_keys() { printf 'fixture|FIXTURE\\n'; }
list_ssh_config_hosts() { :; }
list_sparrow_wallets() { :; }
main
''', status=7)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("Cannot list removable media", result.stderr)
            self.assertNotIn("current directory", result.stdout)
            self.assertNotIn("Exporting keys", result.stdout)
            self.assertNotIn("Decrypting archive", result.stdout)

    def test_empty_devices_is_successful_for_current_directory_fallback(self):
        for name in self.definitions:
            result = self.run_bash(name, [], "list_removable_media\n")
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual("", result.stdout)


if __name__ == "__main__":
    unittest.main()
