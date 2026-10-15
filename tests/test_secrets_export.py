"""Synthetic SSH round trips; no real keys, encryption, or removable media."""

import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")


class SecretsExport(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="secrets-export-tests-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home = self.base / "home"
        self.ssh = self.home / ".ssh"
        self.ssh.mkdir(parents=True)
        shutil.copyfile(ROOT / "stow/ssh/.ssh/config", self.ssh / "config")
        self.original = (self.ssh / "config").read_bytes()
        self.fragment = self.ssh / "config.local"
        self.fragment.write_text(
            '  hOsT fixture.example fixture-alias\n'
            '    IdentityFile "~/.ssh/id_fixture one"\n'
            '    IdentityFile ~/.ssh/id_fixture_two\n'
            'Match all\n  IdentityFile ~/.ssh/not-in-host\n'
        )
        self.definitions = {}
        for name in ("secrets_import", "secrets_export"):
            text = (ROOT / "stow/gnupg/.local/bin" / name).read_text()
            self.assertTrue(text.endswith('main "$@"\n'))
            self.definitions[name] = text.removesuffix('main "$@"\n')

    def run_bash(self, body, before=""):
        return subprocess.run(
            [BASH, "--noprofile", "--norc"],
            input=before + self.definitions["secrets_export"] + body,
            cwd=self.base,
            env={"HOME": str(self.home), "PATH": os.environ["PATH"],
                 "TMPDIR": str(self.base)},
            capture_output=True, text=True, timeout=10,
        )

    def test_local_aliases_and_all_explicit_identities_are_exportable(self):
        result = self.run_bash('''
list_ssh_config_hosts
extract_ssh_config_host fixture-alias
get_identity_file_for_host fixture.example
''')
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("fixture.example\n", result.stdout)
        self.assertIn("fixture-alias\n", result.stdout)
        self.assertIn("Host fixture-alias\n", result.stdout)
        self.assertIn(str(self.ssh / "id_fixture one"), result.stdout)
        self.assertIn(str(self.ssh / "id_fixture_two"), result.stdout)
        self.assertNotIn("not-in-host", result.stdout)
        self.assertEqual(self.original, (self.ssh / "config").read_bytes())

    def test_no_concrete_hosts_is_successful_empty_selection(self):
        self.fragment.unlink()
        (self.ssh / "config").write_text("Host *\n  User fixture\n")
        result = self.run_bash("list_ssh_config_hosts\n")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("", result.stdout)

    def test_unknown_or_nested_includes_refuse_incomplete_backup(self):
        for path in (self.ssh / "config", self.fragment):
            with self.subTest(path=path):
                original = path.read_text()
                path.write_text(original + "Include unexpected.conf\n")
                result = self.run_bash("list_ssh_config_hosts\n")
                self.assertNotEqual(0, result.returncode)
                self.assertIn("Unsupported SSH Include", result.stderr)
                path.write_text(original)

    def test_import_then_export_archive_contains_local_host_and_keys(self):
        self.fragment.unlink()
        source = self.base / "import-config"
        source.write_text("Host restored.example\n  IdentityFile ~/.ssh/id_restored\n")
        key = self.ssh / "id_restored"
        key.write_text("SYNTHETIC PRIVATE KEY FIXTURE\n")
        key.with_suffix(".pub").write_text("SYNTHETIC PUBLIC KEY FIXTURE\n")
        before = self.definitions["secrets_import"] + f'''
ln() {{ {shlex.quote(sys.executable)} -c 'import os,sys; os.link(sys.argv[-2], sys.argv[-1])' "$@"; }}
import_ssh_config {shlex.quote(str(source))}
'''
        result = self.run_bash('''
check_deps() { :; }
list_removable_media() { :; }
fzf() { printf '%s\n' restored.example; }
# Capture a plaintext tar fixture instead of invoking GPG or any real keys.
gpg() {
    if [[ $1 == --list-secret-keys ]]; then return 0; fi
    [[ $1 == --symmetric ]] || return 99
    cat > "${@: -1}"
}
main
''', before=before)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        archives = list(self.base.glob("secrets-*.tar.gz.gpg"))
        self.assertEqual(1, len(archives))
        with tarfile.open(archives[0]) as archive:
            config = archive.extractfile("./ssh_config").read().decode()
            self.assertIn("Host restored.example", config)
            self.assertIn("IdentityFile ~/.ssh/id_restored", config)
            self.assertIn("AddKeysToAgent yes", config)
            self.assertNotIn("Include ~/.ssh/config.local", config)
            self.assertEqual(key.read_bytes(), archive.extractfile("./id_restored").read())
            self.assertEqual(key.with_suffix(".pub").read_bytes(),
                             archive.extractfile("./id_restored.pub").read())
        self.assertEqual(self.original, (self.ssh / "config").read_bytes())


if __name__ == "__main__":
    unittest.main()
