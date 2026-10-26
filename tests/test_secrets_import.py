"""Disposable plaintext fixtures only; operational commands are stubbed."""

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
SCRIPT = ROOT / "stow/gnupg/.local/bin/secrets_import"
BASH = shutil.which("bash")


class SecretsImport(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="secrets-import-tests-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home = self.base / "home"
        self.ssh = self.home / ".ssh"
        self.ssh.mkdir(parents=True)
        self.managed = self.base / "managed-config"
        shutil.copyfile(ROOT / "stow/ssh/.ssh/config", self.managed)
        # Test duplicate protection with a synthetic existing host, not a
        # personal host accidentally embedded in the repository template.
        with self.managed.open('a') as config:
            config.write('\nHost existing.example\n  User fixture-existing\n')
        (self.ssh / "config").symlink_to(self.managed)
        self.original = self.managed.read_bytes()
        self.fragment = self.ssh / "config.local"
        self.source = self.base / "archive-config"
        self.source.write_text(
            "Host *\n  User ignored-default\n"
            "Host fixture.example\n  HostName 192.0.2.1\n  User fixture\n"
            "Host existing.example\n  User must-not-replace\n"
        )
        # Remove only the final entrypoint call, retaining the actual definitions.
        text = SCRIPT.read_text()
        self.assertTrue(text.endswith('main "$@"\n'))
        self.definitions = text.removesuffix('main "$@"\n')
        self.env = {
            **os.environ, "HOME": str(self.home), "TMPDIR": str(self.base),
        }
        # macOS ln lacks GNU -T. Match its non-replacing publication semantics
        # with os.link; no real SSH/GPG command may run in these fixtures.
        self.stubs = f"""
gpg() {{ return 99; }}
ssh() {{ return 99; }}
ln() {{ {shlex.quote(sys.executable)} -c 'import os,sys; os.link(sys.argv[-2], sys.argv[-1])' "$@"; }}
"""

    def run_bash(self, body):
        return subprocess.run(
            [BASH], input=self.definitions + self.stubs + body,
            cwd=self.base, env=self.env, text=True, capture_output=True, timeout=10,
        )

    def call(self, function, *args, prefix=""):
        command = " ".join([function, *(shlex.quote(str(arg)) for arg in args)])
        result = self.run_bash(prefix + f"\nif {command}; then exit 0; else exit $?; fi\n")
        self.assertEqual(self.original, self.managed.read_bytes())
        return result

    def test_hosts_use_local_fragment_and_repeat_safely(self):
        first = self.call("import_ssh_config", self.source)
        self.assertEqual(0, first.returncode, first.stderr)
        self.assertEqual("1:1\n", first.stdout)
        saved = self.fragment.read_bytes()
        self.assertIn(b"Host fixture.example", saved)
        self.assertNotIn(b"ignored-default", saved)
        self.assertNotIn(b"must-not-replace", saved)
        self.assertEqual(0o600, self.fragment.stat().st_mode & 0o777)
        second = self.call("import_ssh_config", self.source)
        self.assertEqual(0, second.returncode, second.stderr)
        self.assertEqual("0:2\n", second.stdout)
        self.assertEqual(saved, self.fragment.read_bytes())
        self.assertIn(b"Include ~/.ssh/config.local\n", self.original)

    def test_missing_include_refuses_without_modifying_config(self):
        self.managed.write_text("Host fixture\n  User local\n")
        self.original = self.managed.read_bytes()
        result = self.call("import_ssh_config", self.source)
        self.assertEqual(2, result.returncode)
        self.assertFalse(self.fragment.exists())

    def test_unrelated_fragment_is_preserved(self):
        self.fragment.write_text("Host personal\n  User local\n")
        before = self.fragment.read_bytes()
        self.assertEqual(2, self.call("import_ssh_config", self.source).returncode)
        self.assertEqual(before, self.fragment.read_bytes())

    def test_fragment_symlinks_are_refused(self):
        for dangling in (False, True):
            with self.subTest(dangling=dangling):
                target = self.base / "external-fragment"
                if not dangling:
                    target.write_text("external fixture\n")
                self.fragment.symlink_to(target)
                self.assertEqual(2, self.call("import_ssh_config", self.source).returncode)
                if not dangling:
                    self.assertEqual("external fixture\n", target.read_text())
                    target.unlink()
                self.fragment.unlink()

    def test_config_chmod_and_parser_failures_are_not_success(self):
        for command in ("chmod", "awk"):
            with self.subTest(command=command):
                result = self.call("import_ssh_config", self.source,
                                   prefix=f"{command}() {{ return 43; }}")
                self.assertEqual(2, result.returncode)
                self.assertEqual("", result.stdout)
                self.assertNotIn("Host fixture.example", self.fragment.read_text())
                self.fragment.unlink()

    def test_new_keys_and_wallets_have_private_permissions(self):
        source = self.base / "dummy-content"
        source.write_text("NOT A KEY OR WALLET\n")
        for function, name, mode in (("import_ssh_key", "id_fixture", 0o600),
                                     ("import_ssh_key", "id_fixture.pub", 0o644),
                                     ("import_sparrow_wallet", "wallet.fixture", 0o600)):
            with self.subTest(function=function, name=name):
                dest = self.ssh / name
                result = self.call(function, source, dest)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual(source.read_bytes(), dest.read_bytes())
                self.assertEqual(mode, dest.stat().st_mode & 0o777)
                self.assertEqual(1, self.call(function, source, dest).returncode)
                dest.write_text("different fixture\n")
                self.assertEqual(1, self.call(function, source, dest).returncode)
                self.assertEqual("different fixture\n", dest.read_text())

    def test_copy_permission_and_install_failures_never_publish(self):
        source = self.base / "dummy-content"
        source.write_text("NOT A KEY OR WALLET\n")
        for function, command in (("import_ssh_key", "cp"),
                                  ("import_ssh_key", "chmod"),
                                  ("import_sparrow_wallet", "install")):
            with self.subTest(function=function, command=command):
                dest = self.ssh / "new-fixture"
                result = self.call(function, source, dest,
                                   prefix=f"{command}() {{ return 43; }}")
                self.assertEqual(2, result.returncode)
                self.assertNotIn("Imported:", result.stdout)
                self.assertFalse(dest.exists())
                self.assertEqual([], list(self.ssh.glob(".secrets-import.*")))

    def test_key_and_wallet_symlink_destinations_are_refused(self):
        source = self.base / "dummy-content"
        source.write_text("NOT A KEY OR WALLET\n")
        for function in ("import_ssh_key", "import_sparrow_wallet"):
            for dangling in (False, True):
                with self.subTest(function=function, dangling=dangling):
                    target = self.base / "external-fixture"
                    if not dangling:
                        target.write_text("unchanged fixture\n")
                    dest = self.ssh / "linked-fixture"
                    dest.symlink_to(target)
                    self.assertEqual(2, self.call(function, source, dest).returncode)
                    if not dangling:
                        self.assertEqual("unchanged fixture\n", target.read_text())
                        target.unlink()
                    dest.unlink()

    def test_compare_errors_fail_instead_of_skipping(self):
        source = self.base / "dummy-content"
        source.write_text("NOT A KEY OR WALLET\n")
        dest = self.ssh / "existing-fixture"
        dest.write_text("unchanged fixture\n")
        for function in ("import_ssh_key", "import_sparrow_wallet"):
            result = self.call(function, source, dest, prefix="cmp() { return 43; }")
            self.assertEqual(2, result.returncode)
            self.assertNotIn("Imported:", result.stdout)
        self.assertEqual("unchanged fixture\n", dest.read_text())

    def test_failed_publication_does_not_replace_a_new_conflict(self):
        source = self.base / "dummy-content"
        source.write_text("NOT A KEY OR WALLET\n")
        for function in ("import_ssh_key", "import_sparrow_wallet"):
            with self.subTest(function=function):
                dest = self.ssh / "new-fixture"
                prefix = f"""
ln() {{
    printf 'concurrent fixture\\n' > {shlex.quote(str(dest))}
    return 43
}}
"""
                result = self.call(function, source, dest, prefix=prefix)
                self.assertEqual(2, result.returncode)
                self.assertNotIn("Imported:", result.stdout)
                self.assertEqual("concurrent fixture\n", dest.read_text())
                dest.unlink()

    def test_symlink_parents_are_refused(self):
        source = self.base / "dummy-content"
        source.write_text("NOT A KEY OR WALLET\n")
        external = self.base / "external"
        external.mkdir()
        parent = self.ssh / "linked-directory"
        parent.symlink_to(external, target_is_directory=True)
        for function in ("import_ssh_key", "import_sparrow_wallet"):
            self.assertEqual(2, self.call(function, source, parent / "fixture").returncode)
        self.assertEqual([], list(external.iterdir()))

    def test_if_callers_count_errors_as_failures_not_imports_or_skips(self):
        source = self.base / "dummy-content"
        source.write_text("NOT A KEY OR WALLET\n")
        dest = self.ssh / "new-fixture"
        for function, command in (("import_ssh_key", "cp"),
                                  ("import_ssh_key", "chmod"),
                                  ("import_sparrow_wallet", "install")):
            with self.subTest(function=function, command=command):
                result = self.run_bash(f"""
{command}() {{ return 43; }}
imported=0 skipped=0 failed=0
if {function} {shlex.quote(str(source))} {shlex.quote(str(dest))}; then
    imported=$((imported + 1))
else
    status=$?
    if [[ $status == 1 ]]; then skipped=$((skipped + 1)); else failed=$((failed + 1)); fi
fi
printf '%s:%s:%s\\n' "$imported" "$skipped" "$failed"
""")
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual("0:0:1\n", result.stdout)
                self.assertFalse(dest.exists())

    def test_explicit_nonstandard_keys_and_legacy_keys_are_selected_not_metadata(self):
        archive = self.base / "archive"
        archive.mkdir()
        (archive / "ssh_config").write_text(
            'Host fixture\n IdentityFile "~/.ssh/github auth"\n'
            ' IdentityFile /old/machine/github_auth\n IdentityFile none\n')
        names = ("github auth", "github auth.pub", "github_auth", "github_auth.pub",
                 "id_legacy", "id_legacy.pub")
        for name in (*names, "config", "config.local", "known_hosts", "metadata.json", "gpg_FIXTURE.asc"):
            (archive / name).write_text("SYNTHETIC FIXTURE\n")
        result = self.call("list_archive_ssh_keys", archive)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual({("public" if name.endswith(".pub") else "private", name)
                          for name in names},
                         {tuple(line.split("\t")) for line in result.stdout.splitlines()})

    def test_agent_only_public_identity_is_restored_without_a_private_key(self):
        archive = self.base / "archive"
        archive.mkdir()
        (archive / "ssh_config").write_text(
            "Host fixture\n IdentityFile ~/.ssh/github_auth\n")
        (archive / "github_auth.pub").write_text(
            "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFIXTURE fixture\n")
        result = self.call("list_archive_ssh_keys", archive)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("public\tgithub_auth.pub\n", result.stdout)

    def test_missing_private_and_public_identity_refuses_before_publication(self):
        archive = self.base / "archive"
        archive.mkdir()
        (archive / "ssh_config").write_text(
            "Host fixture\n IdentityFile ~/.ssh/github_auth\n")
        (archive / "id_legacy").write_text("SYNTHETIC MUST NOT BE IMPORTED\n")
        result = self.call("list_archive_ssh_keys", archive)
        self.assertEqual(2, result.returncode)
        self.assertEqual("", result.stdout)
        self.assertIn("Missing archived SSH identity: github_auth", result.stderr)
        self.assertNotIn("SYNTHETIC", result.stderr)
        with tarfile.open(self.base / "fixture.tar.gz.gpg", "w:gz") as payload:
            for source in archive.iterdir():
                payload.add(source, arcname=source.name)
        result = self.run_bash('''
check_deps() { :; }
list_removable_media() { :; }
fzf() { cat; }
gpg() { [[ $1 == --decrypt ]] || return 99; cat -- "$2"; }
main
''')
        self.assertNotEqual(0, result.returncode)
        self.assertIn("Missing archived SSH identity: github_auth", result.stderr)
        self.assertNotIn("Imported:", result.stdout)
        self.assertEqual(["config"], [path.name for path in self.ssh.iterdir()])
        self.assertEqual([], list(self.base.glob("tmp.*")))

    def test_public_named_identity_is_restored_as_public(self):
        archive = self.base / "archive"
        archive.mkdir()
        (archive / "ssh_config").write_text(
            "Host fixture\n IdentityFile ~/.ssh/github_auth\n"
            " IdentityFile ~/.ssh/configured.pub\n IdentityFile none\n")
        for name in ("github_auth", "configured.pub"):
            (archive / name).write_text("SYNTHETIC IDENTITY FIXTURE\n")
        result = self.call("list_archive_ssh_keys", archive)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual({"private\tgithub_auth", "public\tconfigured.pub"},
                         set(result.stdout.splitlines()))

    def test_public_suffix_and_private_content_decide_roles(self):
        archive = self.base / "archive"
        archive.mkdir()
        (archive / "ssh_config").write_text(
            "Host fixture\n IdentityFile ~/.ssh/github_auth\n"
            " IdentityFile ~/.ssh/github_auth.pub\n")
        for name in ("github_auth", "github_auth.pub", "github_auth.pub.pub"):
            (archive / name).write_text("SYNTHETIC IDENTITY FIXTURE\n")
        result = self.call("list_archive_ssh_keys", archive)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual({"private\tgithub_auth", "public\tgithub_auth.pub"},
                         set(result.stdout.splitlines()))

    def test_private_content_under_public_name_stays_private(self):
        archive = self.base / "archive"
        archive.mkdir()
        (archive / "ssh_config").write_text(
            "Host fixture\n IdentityFile ~/.ssh/github_auth.pub\n")
        key = archive / "github_auth.pub"
        key.write_text("-----BEGIN OPENSSH PRIVATE KEY-----\nFIXTURE\n")
        result = self.call("list_archive_ssh_keys", archive)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("private\tgithub_auth.pub\n", result.stdout)
        dest = self.ssh / "github_auth.pub"
        self.assertEqual(0, self.call("import_ssh_key", key, dest, "private").returncode)
        self.assertEqual(0o600, dest.stat().st_mode & 0o777)

    def test_archived_key_links_and_reserved_references_are_refused(self):
        archive = self.base / "archive"
        archive.mkdir()
        config = archive / "ssh_config"
        for name in ("ssh_config", "gpg_FIXTURE.asc", "sparrow_wallets", ".."):
            with self.subTest(name=name):
                config.write_text(f"Host fixture\n IdentityFile ~/.ssh/{name}\n")
                result = self.call("list_archive_ssh_keys", archive)
                self.assertEqual(2, result.returncode)
                self.assertEqual("", result.stdout)
        config.write_text("Host fixture\n IdentityFile ~/.ssh/github_auth\n")
        (archive / "github_auth").symlink_to(self.source)
        self.assertEqual(2, self.call("list_archive_ssh_keys", archive).returncode)
        (archive / "github_auth").unlink()
        config.unlink()
        config.symlink_to(self.source)
        self.assertEqual(2, self.call("list_archive_ssh_keys", archive).returncode)

    def test_archive_key_collisions_and_line_break_names_fail_before_output(self):
        archive = self.base / "archive"
        archive.mkdir()
        malicious = archive / "id_fixture\n.."
        malicious.write_text("SYNTHETIC FIXTURE\n")
        result = self.call("list_archive_ssh_keys", archive)
        self.assertEqual(2, result.returncode)
        self.assertEqual("", result.stdout)
        malicious.unlink()
        (archive / "ssh_config").write_text(
            "Host fixture\n IdentityFile ~/.ssh/github_auth\n"
            " IdentityFile ~/.ssh/GITHUB_AUTH\n")
        lower = archive / "github_auth"
        upper = archive / "GITHUB_AUTH"
        lower.write_text("SYNTHETIC FIRST FIXTURE\n")
        if upper.exists():
            self.skipTest("case-insensitive filesystem cannot store both archive names")
        upper.write_text("SYNTHETIC SECOND FIXTURE\n")
        result = self.call("list_archive_ssh_keys", archive)
        self.assertEqual(2, result.returncode)
        self.assertEqual("", result.stdout)

    def test_arbitrary_basename_roundtrip_through_export_and_import(self):
        # Run real collection/tar/import with plaintext synthetic data and no
        # USB enumeration, encryption, GPG import, real home, or network access.
        export = (ROOT / "stow/gnupg/.local/bin/secrets_export").read_text()
        export = export.removesuffix('main "$@"\n')
        (self.ssh / "config").unlink()
        (self.ssh / "config").write_text(
            'Host fixture\n IdentityFile ~/.ssh/github_auth\n'
            ' IdentityFile "~/.ssh/arbitrary key"\n IdentityFile ~/.ssh/id_legacy\n'
            ' IdentityFile ~/.ssh/configured.pub\n')
        expected = {}
        modes = {}
        for name in ("github_auth", "arbitrary key", "id_legacy"):
            for suffix in ("", ".pub"):
                expected[name + suffix] = f"SYNTHETIC {name}{suffix} CONTENT\n".encode()
                modes[name + suffix] = 0o600 if not suffix else 0o644
                (self.ssh / (name + suffix)).write_bytes(expected[name + suffix])
        # An explicit .pub identity is public-only; the old exporter also
        # copied a meaningless ".pub.pub" companion.
        expected["configured.pub"] = b"SYNTHETIC configured.pub CONTENT\n"
        modes["configured.pub"] = 0o644
        (self.ssh / "configured.pub").write_bytes(expected["configured.pub"])
        result = subprocess.run(
            [BASH, "--noprofile", "--norc"], input=export + '''
check_deps() { :; }
list_removable_media() { :; }
fzf() { printf 'fixture\\n'; }
gpg() {
    if [[ $1 == --list-secret-keys ]]; then return 0; fi
    [[ $1 == --symmetric ]] || return 99
    cat > "${@: -1}"
}
main
''', cwd=self.base, env=self.env, text=True, capture_output=True, timeout=10)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        archive = next(self.base.glob("secrets-*.tar.gz.gpg"))
        with tarfile.open(archive) as contents:
            for name, data in expected.items():
                self.assertEqual(data, contents.extractfile("./" + name).read())
        restore = self.base / "restored"
        (restore / ".ssh").mkdir(parents=True)
        shutil.copyfile(ROOT / "stow/ssh/.ssh/config", restore / ".ssh/config")
        body = f'''
HOME={shlex.quote(str(restore))}
check_deps() {{ :; }}
list_removable_media() {{ :; }}
fzf() {{ cat; }}
gpg() {{ [[ $1 == --decrypt ]] || return 99; cat -- "$2"; }}
main
'''
        first = self.run_bash(body)
        self.assertEqual(0, first.returncode, first.stdout + first.stderr)
        for name, data in expected.items():
            dest = restore / ".ssh" / name
            self.assertEqual(data, dest.read_bytes())
            self.assertEqual(modes[name], dest.stat().st_mode & 0o777)
            self.assertNotIn(data.decode().strip(), first.stdout + first.stderr)
        self.assertFalse((restore / ".ssh/ssh_config").exists())
        conflict = restore / ".ssh/github_auth"
        conflict.write_text("EXISTING DIFFERENT FIXTURE\n")
        second = self.run_bash(body)
        self.assertEqual(0, second.returncode, second.stdout + second.stderr)
        self.assertEqual("EXISTING DIFFERENT FIXTURE\n", conflict.read_text())
        self.assertIn("7 SSH key(s) skipped", second.stdout)
        self.assertEqual([], list(self.base.glob("tmp.*")))


if __name__ == "__main__":
    unittest.main()
