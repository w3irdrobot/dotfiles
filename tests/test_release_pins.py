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
        info = {'version': '2.1.5', 'dist': {'tarball': 'https://registry.npmjs.org/a',
                'integrity': 'sha512-' + base64.b64encode(hashlib.sha512(data).digest()).decode()}}
        with patch.object(pins, 'metadata', return_value=info), patch.object(pins, 'download', return_value=data), \
                patch.object(pins.subprocess, 'run', side_effect=AssertionError('must not execute')):
            old, new, files, digest, _ = pins.native('opencode')
        self.assertEqual((old, new), ('2.1.4', '2.1.5'))
        self.assertEqual(digest, pins.sha256(b'binary'))
        self.assertIn('OPENCODE_VERSION=2.1.5', files[ROOT / 'modules/opencode.sh'])
        self.assertIn('/opencode/2.1.5/opencode', files[ROOT / 'install.sh'])
        self.assertEqual((ROOT / 'modules/opencode.sh').read_text().count('OPENCODE_VERSION=2.1.4'), 1)

    def test_existing_version_digest_changes_fail(self):
        with patch.object(pins, 'native', return_value=('2.1.4', '2.1.4', {}, '0' * 64, None)):
            with self.assertRaisesRegex(ValueError, 'digest changed'):
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
                patch.object(pins.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '[GNUPG:] VALIDSIG OTHER 123')):
            with self.assertRaisesRegex(ValueError, 'identity'):
                pins.signal_pin(old)

    def test_writes_only_pins_after_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'pin'
            path.write_text('original')
            with patch.object(sys, 'argv', ['pins', '--tool', 'signal']), \
                    patch.object(pins.subprocess, 'check_output', side_effect=['', 'git@github.com:w3irdrobot/dotfiles.git\n', '']), \
                    patch.object(pins, 'prepare', return_value={path: 'updated'}):
                pins.main()
            self.assertEqual(path.read_text(), 'updated')


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
