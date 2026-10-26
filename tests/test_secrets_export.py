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
        # Match all applies to the selected host too, not just the prior block.
        self.assertIn(str(self.ssh / "not-in-host"), result.stdout)
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

    def write_config(self, text):
        self.fragment.unlink(missing_ok=True)
        (self.ssh / "config").write_text(text)

    def export_fixture(self, host="fixture", before=""):
        # Only the archive bytes are mocked; main performs real selection,
        # collection, preflight, staging, and tar creation in the fixture home.
        return self.run_bash(f'''
check_deps() {{ :; }}
list_removable_media() {{ :; }}
fzf() {{ printf '%s\\n' {shlex.quote(host)}; }}
gpg() {{
    if [[ $1 == --list-secret-keys ]]; then return 0; fi
    [[ $1 == --symmetric ]] || return 99
    cat > "${{@: -1}}"
}}
main
''', before=before)

    def test_all_matching_contexts_collect_identities_in_original_order(self):
        self.write_config('''IdentityFile ~/.ssh/global
Host * !excluded
  IdentityFile ~/.ssh/wildcard
Host fixtur? alias
  User first-user
  IdentityFile ~/.ssh/pattern
Host unrelated
  IdentityFile ~/.ssh/unrelated
Host fixture
  User ignored-later-user
  IdentityFile ~/.ssh/repeated
Match all
  IdentityFile ~/.ssh/match-all
''')
        result = self.run_bash("get_identity_file_for_host fixture\n")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([str(self.ssh / name) for name in
                          ("global", "wildcard", "pattern", "repeated", "match-all")],
                         result.stdout.splitlines())
        excluded = self.run_bash("get_identity_file_for_host excluded\n")
        self.assertEqual(0, excluded.returncode, excluded.stderr)
        self.assertEqual([str(self.ssh / name) for name in ("global", "match-all")],
                         excluded.stdout.splitlines())

    def test_supported_equals_forms_are_normalized_including_local_include(self):
        (self.ssh / "config").write_text('''Include = "~/.ssh/config.local" # supported
Host=fixture
  IdentityFile=~/.ssh/direct
  IdentityFile = "~/.ssh/path with spaces" # comment
''')
        self.fragment.write_text('Host = fixture\n IdentityFile =~/.ssh/local\n')
        result = self.run_bash("list_ssh_config_hosts; get_identity_file_for_host fixture\n")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(["fixture", *(str(self.ssh / name) for name in
                                     ("local", "direct", "path with spaces"))],
                         result.stdout.splitlines())

    def test_equals_form_unknown_and_nested_includes_fail(self):
        for text in ("Include=unexpected.conf\n", "Include = unexpected.conf\n",
                     'Include="unexpected.conf"\n'):
            with self.subTest(text=text):
                self.write_config(text + "Host fixture\n IdentityFile none\n")
                result = self.export_fixture()
                self.assertNotEqual(0, result.returncode)
                self.assertIn("Unsupported SSH Include", result.stderr)
                self.assertEqual([], list(self.base.glob("secrets-*.tar.gz.gpg")))
        (self.ssh / "config").write_text("Include=~/.ssh/config.local\n")
        self.fragment.write_text("Include=unexpected.conf\n")
        result = self.export_fixture()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("Unsupported SSH Include", result.stderr)

    def test_conditional_include_is_refused_even_for_supported_fragment(self):
        self.write_config("Host other\n Include ~/.ssh/config.local\nHost fixture\n")
        result = self.export_fixture()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("Unsupported SSH Include", result.stderr)

    def test_conditional_matches_fail_without_executing_commands(self):
        for condition in ('exec "printf unsafe > match-executed"', "host fixture", "final"):
            with self.subTest(condition=condition):
                self.write_config(f"Host fixture\n IdentityFile none\nMatch {condition}\n")
                result = self.export_fixture()
                self.assertNotEqual(0, result.returncode)
                self.assertIn("Unsupported SSH", result.stderr)
                self.assertFalse((self.base / "match-executed").exists())
                self.assertEqual([], list(self.base.glob("secrets-*.tar.gz.gpg")))

    def test_missing_equals_form_or_inherited_identity_stops_before_archive(self):
        for text in ("Host fixture\n IdentityFile=~/.ssh/missing\n",
                     "Host *\n IdentityFile ~/.ssh/missing\nHost fixture\n",
                     "Host fixture\n IdentityFile none\nMatch all\n IdentityFile ~/.ssh/missing\n"):
            with self.subTest(text=text):
                self.write_config(text)
                result = self.export_fixture()
                self.assertNotEqual(0, result.returncode)
                self.assertIn("Missing selected SSH identity", result.stderr)
                self.assertEqual([], list(self.base.glob("secrets-*.tar.gz.gpg")))

    def test_basename_collisions_fail_before_staging_or_touching_existing_archive(self):
        for name in ("one", "two"):
            directory = self.ssh / name
            directory.mkdir()
            (directory / "id_fixture").write_text(f"SYNTHETIC {name} KEY\n")
        self.write_config('''Host fixture
 IdentityFile ~/.ssh/one/id_fixture
 IdentityFile ~/.ssh/two/id_fixture
''')
        archive = self.base / "secrets-2000-01-01.tar.gz.gpg"
        archive.write_text("EXISTING ARCHIVE FIXTURE\n")
        result = self.export_fixture(before="date() { printf 2000-01-01; }\n")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("basename collision", result.stderr)
        self.assertNotIn("Exporting keys", result.stdout)
        self.assertEqual("EXISTING ARCHIVE FIXTURE\n", archive.read_text())
        self.assertEqual([], list(self.base.glob("tmp.*")))

    def test_public_companion_and_reserved_archive_name_collisions_fail(self):
        first = self.ssh / "id_fixture"
        first.write_text("SYNTHETIC KEY\n")
        (self.ssh / "id_fixture.pub").write_text("SYNTHETIC PUBLIC KEY\n")
        other = self.ssh / "other"
        other.mkdir()
        for name in ("id_fixture.pub", "ssh_config", "sparrow_wallets", "gpg_FIXTURE.asc"):
            with self.subTest(name=name):
                path = other / name
                path.write_text("SYNTHETIC OTHER KEY\n")
                self.write_config(f"Host fixture\n IdentityFile {first}\n IdentityFile {path}\n")
                result = self.export_fixture()
                self.assertNotEqual(0, result.returncode)
                self.assertTrue("collision" in result.stderr or "Reserved SSH key" in result.stderr,
                                result.stderr)
                self.assertEqual([], list(self.base.glob("secrets-*.tar.gz.gpg")))

    def test_all_applicable_identities_and_blocks_survive_archive_creation(self):
        self.write_config('''IdentityFile ~/.ssh/global
Host * !excluded
 IdentityFile ~/.ssh/wildcard
Host fixture
 User first-user
 IdentityFile ~/.ssh/specific
Host other
 IdentityFile ~/.ssh/unrelated
Host fixture
 User later-user
 IdentityFile ~/.ssh/repeated
Match all
 IdentityFile ~/.ssh/match-all
''')
        names = ("global", "wildcard", "specific", "repeated", "match-all")
        for name in names:
            (self.ssh / name).write_text(f"SYNTHETIC {name} KEY\n")
        result = self.export_fixture()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        with tarfile.open(next(self.base.glob("secrets-*.tar.gz.gpg"))) as archive:
            config = archive.extractfile("./ssh_config").read().decode()
            self.assertEqual(1, config.count("Host fixture"))
            self.assertLess(config.index("  User first-user"), config.index("  User later-user"))
            self.assertNotIn("unrelated", config)
            for name in names:
                self.assertIn(f"  IdentityFile ~/.ssh/{name}", config)
                self.assertEqual((self.ssh / name).read_bytes(), archive.extractfile(f"./{name}").read())

    def test_unsupported_identity_expansions_fail_without_interpretation(self):
        for value in ("%d/.ssh/key", "${HOME}/.ssh/key", "~other/.ssh/key",
                      ".ssh/relative-key", r'"~/.ssh/key\ name"'):
            with self.subTest(value=value):
                self.write_config(f"Host fixture\n IdentityFile {value}\n")
                result = self.export_fixture()
                self.assertNotEqual(0, result.returncode)
                self.assertIn("Unsupported SSH", result.stderr)
                self.assertEqual([], list(self.base.glob("secrets-*.tar.gz.gpg")))

    def test_canonicalization_is_rejected_instead_of_guessing_host_matches(self):
        self.write_config("CanonicalizeHostname yes\nHost fixture\n IdentityFile none\n")
        result = self.export_fixture()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("canonicalization is unsupported", result.stderr)

    def test_public_identity_also_selected_directly_is_not_a_collision(self):
        key = self.ssh / "id_fixture"
        key.write_text("SYNTHETIC KEY\n")
        key.with_suffix(".pub").write_text("SYNTHETIC PUBLIC KEY\n")
        self.write_config(f"Host fixture\n IdentityFile {key}\n IdentityFile {key}.pub\n")
        result = self.export_fixture()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_agent_only_public_identity_is_exported_without_private_key(self):
        self.write_config("Host fixture\n IdentityFile ~/.ssh/id_agent\n")
        (self.ssh / "id_agent.pub").write_text(
            "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFIXTURE fixture\n")
        result = self.export_fixture()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        with tarfile.open(next(self.base.glob("secrets-*.tar.gz.gpg"))) as archive:
            names = set(archive.getnames())
            self.assertIn("./id_agent.pub", names)
            self.assertNotIn("./id_agent", names)
            config = archive.extractfile("./ssh_config").read().decode()
            self.assertIn("  IdentityFile ~/.ssh/id_agent", config)

    def test_explicit_public_identity_does_not_archive_pub_pub(self):
        self.write_config("Host fixture\n IdentityFile ~/.ssh/id_agent.pub\n")
        (self.ssh / "id_agent.pub").write_text(
            "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFIXTURE fixture\n")
        (self.ssh / "id_agent.pub.pub").write_text("not a real companion\n")
        result = self.export_fixture()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        with tarfile.open(next(self.base.glob("secrets-*.tar.gz.gpg"))) as archive:
            names = set(archive.getnames())
            self.assertIn("./id_agent.pub", names)
            self.assertNotIn("./id_agent.pub.pub", names)

    def test_case_folded_names_cannot_overwrite_on_case_insensitive_filesystems(self):
        # Separate directories make this fixture work on either filesystem type.
        for directory, name in (("one", "id_fixture"), ("two", "ID_FIXTURE")):
            (self.ssh / directory).mkdir()
            (self.ssh / directory / name).write_text("SYNTHETIC KEY\n")
        self.write_config("Host fixture\n IdentityFile ~/.ssh/one/id_fixture\n IdentityFile ~/.ssh/two/ID_FIXTURE\n")
        result = self.export_fixture()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("basename collision", result.stderr)

    @unittest.skipUnless(shutil.which("ssh"), "OpenSSH is unavailable")
    def test_flattened_supported_config_agrees_with_openssh(self):
        # These -G checks read only our explicit -F configs. No Match exec,
        # canonicalization, network connection, or real user key/config access.
        self.write_config(f'''CanonicalizeHostname no
IdentityFile "{self.ssh / 'global'}"
Host * !excluded
 IdentityFile="{self.ssh / 'wildcard'}"
Host fixtur? alias
 User first-user
 IdentityFile "{self.ssh / 'pattern'}"
Host unrelated
 IdentityFile "{self.ssh / 'unrelated'}"
Host FIXTURE
 User later-user
 IdentityFile "{self.ssh / 'uppercase-does-not-match'}"
Host fixture
 User later-user
 IdentityFile "{self.ssh / 'repeated'}"
Match all
 IdentityFile "{self.ssh / 'match-all'}"
''')
        for host in ("fixture", "excluded", "fixture.extra", "alias"):
            with self.subTest(host=host):
                result = self.run_bash(f"extract_ssh_config_host {shlex.quote(host)} | format_ssh_export\n")
                self.assertEqual(0, result.returncode, result.stderr)
                flat = self.base / "flattened-config"
                flat.write_text(result.stdout)
                outputs = []
                for config in (self.ssh / "config", flat):
                    check = subprocess.run(
                        [shutil.which("ssh"), "-G", "-F", str(config), host],
                        cwd=self.base, env={"HOME": str(self.home), "PATH": os.defpath},
                        capture_output=True, text=True, timeout=10,
                    )
                    self.assertEqual(0, check.returncode, check.stderr)
                    outputs.append([line for line in check.stdout.splitlines()
                                    if line.split(" ", 1)[0] in ("user", "identityfile", "hostname")])
                self.assertEqual(outputs[0], outputs[1])

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
            self.assertIn("  IdentityFile ~/.ssh/id_restored", config)
            self.assertIn("  AddKeysToAgent yes", config)
            self.assertNotIn("Include ~/.ssh/config.local", config)
            self.assertEqual(key.read_bytes(), archive.extractfile("./id_restored").read())
            self.assertEqual(key.with_suffix(".pub").read_bytes(),
                             archive.extractfile("./id_restored.pub").read())
        self.assertEqual(self.original, (self.ssh / "config").read_bytes())

    def test_archive_formatter_indents_and_canonicalizes_without_changing_values_or_order(self):
        raw = ('Host fixture.example\n'
               'addkeystoagent yes\nidentitiesonly yes\n'
               'user fixture\nhostname 192.0.2.10\n'
               'identityfile "~/.ssh/key with spaces.pub"\n'
               'identitiesonly yes\nfutureoption KeepThisCase\n')
        result = self.run_bash(f"printf '%s' {shlex.quote(raw)} | format_ssh_export\n")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            'Host fixture.example\n'
            '  AddKeysToAgent yes\n  IdentitiesOnly yes\n'
            '  User fixture\n  HostName 192.0.2.10\n'
            '  IdentityFile "~/.ssh/key with spaces.pub"\n'
            '  IdentitiesOnly yes\n  futureoption KeepThisCase\n', result.stdout)


if __name__ == "__main__":
    unittest.main()
