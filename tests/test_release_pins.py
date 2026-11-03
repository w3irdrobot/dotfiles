"""Release maintenance never installs or executes downloaded artifacts."""

import base64
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pins = load('release_pins', 'update-release-pins.py')
native = load('native_release', 'native-release.py')


def archive(data=b'binary', kind=tarfile.REGTYPE):
    result = io.BytesIO()
    with tarfile.open(fileobj=result, mode='w:gz') as tar:
        entry = tarfile.TarInfo('package/bin/opencode')
        entry.type = kind
        entry.size = len(data) if kind == tarfile.REGTYPE else 0
        tar.addfile(entry, io.BytesIO(data))
    return result.getvalue()


class ReleasePins(unittest.TestCase):
    def test_cli_dry_run_without_network_or_writes(self):
        result = subprocess.run(['bash', str(ROOT / 'bin/dotfiles'), 'update-release-pins', '--dry-run'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('PLAN ONLY', result.stdout)
        self.assertIn('opencode, nono, bitwarden, discord, signal', result.stdout)

    def test_invalid_tools_and_redundant_all_selector_fail(self):
        for args in (['--tool', 'unknown'], ['--all'], ['all']):
            result = subprocess.run(['bash', str(ROOT / 'bin/dotfiles'), 'update-release-pins', *args],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)

    def test_archive_rejects_symlink(self):
        with self.assertRaises(ValueError):
            pins.member(archive(kind=tarfile.SYMTYPE), 'package/bin/opencode')

    def test_integrity_failure(self):
        info = {'version': '2.1.5', 'dist': {'tarball': 'https://registry.npmjs.org/a', 'integrity': 'sha512-invalid'}}
        with patch.object(pins, 'metadata', return_value=info), patch.object(pins, 'download', return_value=archive()):
            with self.assertRaisesRegex(ValueError, 'integrity'):
                pins.native('opencode')

    def test_opencode_prepares_exact_sources_without_executing(self):
        data = archive()
        current = next(line.split('=')[1] for line in (ROOT / 'modules/opencode.sh').read_text().splitlines()
                       if line.startswith('readonly OPENCODE_VERSION='))
        major, minor, release = pins.version(current)
        following = f'{major}.{minor}.{release + 1}'
        info = {'version': following, 'dist': {'tarball': 'https://registry.npmjs.org/a',
                'integrity': 'sha512-' + base64.b64encode(hashlib.sha512(data).digest()).decode()}}
        with patch.object(pins, 'metadata', return_value=info), patch.object(pins, 'download', return_value=data), \
                patch.object(pins.subprocess, 'run', side_effect=AssertionError('must not execute')):
            old, new, files, digest, _ = pins.native('opencode')
        self.assertEqual((old, new), (current, following))
        self.assertEqual(digest, pins.sha256(b'binary'))
        self.assertIn(f'OPENCODE_VERSION={following}', files[ROOT / 'modules/opencode.sh'])
        self.assertIn(f'/opencode/{following}/opencode', files[ROOT / 'install.sh'])
        self.assertEqual((ROOT / 'modules/opencode.sh').read_text().count(f'OPENCODE_VERSION={current}'), 1)

    def test_existing_version_digest_changes_fail(self):
        with patch.object(pins, 'native', return_value=('2.1.4', '2.1.4', {}, '0' * 64, None)):
            with self.assertRaisesRegex(ValueError, 'digest changed'):
                pins.prepare('opencode')

    def test_same_opencode_release_does_not_add_previous_release_record(self):
        # A freshly updated pin has its predecessor in the guards, not itself.
        # Rerunning against identical upstream bytes must be an exact no-op.
        data = archive()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'modules').mkdir()
            (root / 'lib').mkdir()
            url = 'https://registry.npmjs.org/opencode.tgz'
            binary_hash = pins.sha256(b'binary')
            (root / 'modules/opencode.sh').write_text(
                f'readonly OPENCODE_VERSION=2.2.5\nreadonly OPENCODE_URL={url}\n'
                f'readonly OPENCODE_ARCHIVE_SHA256={pins.sha256(data)}\n'
                f'readonly OPENCODE_BINARY_SHA256={binary_hash}\n')
            guard = ('managed=$HOME/.local/share/dotfiles/opencode/2.2.5/opencode\n'
                     '\t# Previous verified OpenCode releases (maintained by update-release-pins).\n'
                     '\t2.1.4) digest=previous ;;\n')
            for relative in ('install.sh', 'lib/dotfiles.sh'):
                (root / relative).write_text(guard)
            (root / 'README.md').write_text('/opencode/2.2.5/opencode\n')
            (root / 'modules/native-release-history.json').write_text(json.dumps({'opencode': {'2.2.5': binary_hash}}))
            info = {'version': '2.2.5', 'dist': {'tarball': url,
                    'integrity': 'sha512-' + base64.b64encode(hashlib.sha512(data).digest()).decode()}}
            with patch.object(pins, 'ROOT', root), patch.object(pins, 'metadata', return_value=info), \
                    patch.object(pins, 'download', return_value=data):
                for _ in range(2):
                    old, new, files, _, _ = pins.native('opencode')
                    self.assertEqual(('2.2.5', '2.2.5'), (old, new))
                    self.assertTrue(all(path.read_text() == content for path, content in files.items()))
                    pins.prepare('opencode')

    def test_same_opencode_release_with_changed_artifact_still_fails(self):
        path = ROOT / 'modules/opencode.sh'
        with patch.object(pins, 'native', return_value=(
                '2.2.5', '2.2.5', {path: path.read_text() + '# changed checksum\n'}, '0' * 64, None)):
            with self.assertRaisesRegex(ValueError, 'upstream changed'):
                pins.prepare('opencode')

    def test_downgrades_fail(self):
        with patch.object(pins, 'native', return_value=('2.1.4', '2.1.3', {}, '0' * 64, None)):
            with self.assertRaisesRegex(ValueError, 'downgrade'):
                pins.prepare('opencode')

    def test_failed_second_tool_leaves_first_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'pin'
            path.write_text('original')
            with patch.object(sys, 'argv', ['pins', '--tool', 'opencode', '--tool', 'signal']), \
                    patch.object(pins.subprocess, 'check_output', side_effect=['', 'git@github.com:w3irdrobot/dotfiles.git\n']), \
                    patch.object(pins, 'prepare', side_effect=[{path: 'new'}, ValueError('bad signature')]):
                with self.assertRaisesRegex(ValueError, 'bad signature'):
                    pins.main()
            self.assertEqual(path.read_text(), 'original')

    def test_dirty_checkout_fails_before_network(self):
        with patch.object(sys, 'argv', ['pins']), \
                patch.object(pins.subprocess, 'check_output', return_value=' M file'), \
                patch.object(pins, 'prepare') as prepare:
            with self.assertRaisesRegex(ValueError, 'clean'):
                pins.main()
            prepare.assert_not_called()

    def test_missing_github_digest_fails_closed(self):
        release = {'draft': False, 'prerelease': False, 'assets': [{'name': 'test'}]}
        with self.assertRaisesRegex(ValueError, 'digest'):
            pins.checked_asset(release, 'test')

    def test_signal_key_rotation_fails_before_gpg(self):
        old = {'key_sha256': '0' * 64}
        with patch.object(pins, 'metadata', return_value={'draft': False, 'prerelease': False, 'tag_name': 'v8.33.0'}), \
                patch.object(pins, 'download', return_value=b'download'), \
                patch.object(pins.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'key changed'):
                pins.signal_pin(old)
            run.assert_not_called()

    def test_signal_signature_must_match_expected_identity(self):
        old = {'key_sha256': pins.sha256(b'download'), 'fingerprint': 'EXPECTED'}
        with patch.object(pins, 'metadata', return_value={'draft': False, 'prerelease': False, 'tag_name': 'v8.33.0'}), \
                patch.object(pins, 'download', return_value=b'download'), \
                patch.object(pins.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, b'[GNUPG:] VALIDSIG OTHER 123')):
            with self.assertRaisesRegex(ValueError, 'identity'):
                pins.signal_pin(old)

    def test_signal_binary_gpg_status_preserves_signature_verification(self):
        old = {'key_sha256': pins.sha256(b'download'), 'fingerprint': 'EXPECTED'}
        with patch.object(pins, 'metadata', return_value={'draft': False, 'prerelease': False, 'tag_name': 'v8.33.0'}), \
                patch.object(pins, 'download', return_value=b'download'), \
                patch.object(pins.subprocess, 'run', return_value=subprocess.CompletedProcess(
                    [], 0, b'[GNUPG:] NOTATION_DATA \xb3\xff\n[GNUPG:] VALIDSIG EXPECTED 123\n', b'\xffdiagnostic')) as run:
            result = pins.signal_pin(old)
            self.assertEqual('8.33.0', result['version'])
            self.assertEqual(pins.sha256(b'download'), result['sha256'])
            self.assertNotIn('text', run.call_args.kwargs)

    def test_signal_failed_gpg_verification_is_not_accepted(self):
        old = {'key_sha256': pins.sha256(b'download'), 'fingerprint': 'EXPECTED'}
        with patch.object(pins, 'metadata', return_value={'draft': False, 'prerelease': False, 'tag_name': 'v8.33.0'}), \
                patch.object(pins, 'download', return_value=b'download'), \
                patch.object(pins.subprocess, 'run', side_effect=[subprocess.CompletedProcess([], 0),
                    subprocess.CalledProcessError(1, ['gpg'], output=b'[GNUPG:] VALIDSIG EXPECTED 123')]):
            with self.assertRaises(subprocess.CalledProcessError):
                pins.signal_pin(old)

    def test_writes_only_pins_after_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'pin'
            path.write_text('original')
            with patch.object(sys, 'argv', ['pins', '--tool', 'signal']), \
                    patch.object(pins.subprocess, 'check_output', side_effect=['', 'git@github.com:w3irdrobot/dotfiles.git\n', '']), \
                    patch.object(pins, 'prepare', return_value={path: 'updated'}), \
                    patch.object(pins, 'commit_changes') as commit:
                pins.main()
            self.assertEqual(path.read_text(), 'updated')
            commit.assert_called_once_with([path])

    def test_unchanged_pins_do_not_attempt_commit(self):
        with patch.object(pins.subprocess, 'run') as run:
            pins.commit_changes([])
        run.assert_not_called()

    def test_commit_failure_preserves_refreshed_pins(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'pin'
            path.write_text('original')
            with patch.object(sys, 'argv', ['pins', '--tool', 'signal']), \
                    patch.object(pins.subprocess, 'check_output', side_effect=['', 'git@github.com:w3irdrobot/dotfiles.git\n', '']), \
                    patch.object(pins, 'prepare', return_value={path: 'updated'}), \
                    patch.object(pins, 'ROOT', Path(directory)), \
                    patch.object(pins.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, ['git', 'commit'])):
                with self.assertRaisesRegex(ValueError, 'Changes are preserved'):
                    pins.main()
            self.assertEqual(path.read_text(), 'updated')

    def test_commit_includes_only_generated_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*args):
                return subprocess.run(['git', '-C', directory, *args], check=True, capture_output=True, text=True)
            git('init', '-b', 'master')
            # Test-local identity/signing settings only; never change the real checkout.
            git('config', 'user.name', 'Fixture')
            git('config', 'user.email', 'fixture@example.invalid')
            git('config', 'commit.gpgsign', 'false')
            git('config', 'core.hooksPath', str(root / 'no-hooks'))
            pin, other = root / 'pin', root / 'other'
            pin.write_text('old')
            other.write_text('old')
            git('add', '--', 'pin', 'other')
            git('commit', '-m', 'fixture')
            pin.write_text('new')
            other.write_text('unrelated')
            git('add', '--', 'other')
            with patch.object(pins, 'ROOT', root):
                pins.commit_changes([pin])
            self.assertEqual('pin', git('diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD').stdout.strip())
            self.assertEqual('other', git('diff', '--cached', '--name-only').stdout.strip())


class ManagedBinary(unittest.TestCase):
    def test_known_binary_only_and_modified_binary_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            binary = home / '.local/share/dotfiles/opencode/2.1.4/opencode'
            binary.parent.mkdir(parents=True)
            binary.write_bytes(b'test')
            binary.chmod(0o755)
            link = home / '.local/bin/opencode'
            link.parent.mkdir(parents=True)
            link.symlink_to(binary)
            # Mock metadata only; filesystem checks use a disposable home.
            with patch.object(native.json, 'loads', side_effect=lambda text: {'opencode': {'2.1.4': pins.sha256(b'test')}}):
                native.verify('opencode', link, home)
                binary.write_bytes(b'modified')
                with self.assertRaisesRegex(ValueError, 'modified'):
                    native.verify('opencode', link, home)
            binary.unlink()
            with self.assertRaisesRegex(ValueError, 'Missing'):
                native.verify('opencode', link, home)


if __name__ == '__main__':
    unittest.main()
