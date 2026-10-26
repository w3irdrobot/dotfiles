"""Synthetic desktop installers; never run real apps, RPMs, GPG stores or Flatpak."""

import hashlib
import importlib.util
import json
import subprocess
import unittest
from unittest.mock import patch

import test_bitwarden
import test_dotfiles


class Discord(unittest.TestCase):
    mock = test_dotfiles.Fixture.mock
    calls = test_dotfiles.Fixture.calls
    transactions = test_bitwarden.Bitwarden.transactions
    assert_failed = test_dotfiles.Fixture.assert_failed

    def setUp(self):
        test_bitwarden.Bitwarden.setUp(self)
        self.pin_path = self.repo / 'modules/discord-release.json'
        pin = json.loads(self.pin_path.read_text())
        pin['sha256'] = hashlib.sha256(self.payload.read_bytes()).hexdigest()
        self.pin_path.write_text(json.dumps(pin))
        self.env['TEST_VERSION'] = pin['version']
        self.binary = self.base / 'usr/bin/discord'
        self.target = self.home / f".cache/dotfiles/discord/{pin['version']}/discord-{pin['version']}.rpm"
        rpm = self.path / 'rpm'
        rpm.write_text(rpm.read_text().replace('bitwarden', 'discord'))

    def library(self, body='install_packages', dry_run=False):
        return subprocess.run(
            [test_dotfiles.BASH, '-c', 'set -euo pipefail; ROOT=$1; DRY_RUN=$2; source "$ROOT/lib/dotfiles.sh"\nMODULES=(discord); PACKAGES=(python3 curl)\n' + body,
             'discord-fixture', str(self.repo), str(int(dry_run))],
            env=self.env, cwd=self.base, text=True, capture_output=True, timeout=20,
        )

    def test_verified_rpm_precedes_upgrade_and_is_installed_without_launching(self):
        result = self.library()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn(str(self.target), self.transactions()[-1])
        self.assertEqual(2, len([c for c in self.calls() if c[0] == 'rpm' and '-qp' in c]))
        self.assertLess(next(i for i,c in enumerate(self.calls()) if '-qp' in c), self.calls().index(self.transactions()[0]))
        self.assertFalse(any(c[0] == 'discord' or '--nogpgcheck' in c for c in self.calls()))

    def test_bad_hash_header_or_query_error_refuses_transactions(self):
        self.env['TEST_HEADER'] = 'other|1.0.166|1|x86_64'
        self.assert_failed(self.library(), 'identity')
        self.assertEqual([], self.transactions())
        self.env['TEST_HEADER'] = 'discord|1.0.166|1|x86_64'
        self.env['TEST_RPM_ERROR'] = '1'
        self.assert_failed(self.library(), 'Could not query')
        self.assertEqual([], self.transactions())
        del self.env['TEST_RPM_ERROR']
        pin = json.loads(self.pin_path.read_text()); pin['sha256'] = '0' * 64
        self.pin_path.write_text(json.dumps(pin))
        self.assert_failed(self.library(), 'checksum mismatch')
        self.assertEqual([], self.transactions())

    def test_equal_and_newer_rpms_are_kept(self):
        self.binary.parent.mkdir(parents=True)
        self.binary.write_text('must not execute')
        self.binary.chmod(0o755)
        for version in ('1.0.166', '1.0.170'):
            self.env['TEST_INSTALLED'] = version
            self.log.unlink(missing_ok=True)
            result = self.library()
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertFalse(any(c[0] == 'curl' for c in self.calls()))
            self.assertNotIn(str(self.target), self.transactions()[-1])

    def test_cache_conflict_and_download_failure_do_not_install(self):
        self.env['TEST_DOWNLOAD_FAIL'] = '1'
        self.assertEqual(43, self.library().returncode)
        self.assertEqual([], list(self.target.parent.glob('.download.*')))
        del self.env['TEST_DOWNLOAD_FAIL']
        self.target.symlink_to(self.payload)
        self.assert_failed(self.library(), 'Conflicting Discord RPM cache')
        self.assertEqual([], self.transactions())

    def test_preview_never_downloads_or_transacts_and_notice_errors_are_optional(self):
        result = self.library(dry_run=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse(any(c[0] in ('curl','sudo','sha256sum') for c in self.calls()))
        (self.repo / 'scripts/check-updates.py').write_text('raise SystemExit(42)\n')
        result = self.library('check_discord_release_notice')
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('status unknown', result.stderr)


class Signal(unittest.TestCase):
    mock = test_dotfiles.Fixture.mock
    calls = test_dotfiles.Fixture.calls
    snapshot = test_dotfiles.Fixture.snapshot
    assert_failed = test_dotfiles.Fixture.assert_failed

    def setUp(self):
        test_dotfiles.Fixture.setUp(self)
        self.payload = self.base / 'appimage'
        self.payload.write_bytes(b'synthetic appimage; never execute')
        self.key = self.base / 'public-key'
        self.key.write_bytes(b'synthetic public signing key')
        pin_path = self.repo / 'modules/signal-release.json'
        pin = json.loads(pin_path.read_text())
        pin.update(sha256=hashlib.sha256(self.payload.read_bytes()).hexdigest(), key_sha256=hashlib.sha256(self.key.read_bytes()).hexdigest())
        pin_path.write_text(json.dumps(pin))
        self.directory = self.home / '.local/share/dotfiles/signal'
        self.cache = self.home / f'.cache/dotfiles/signal/{pin["version"]}'
        self.env.update(TEST_PAYLOAD=str(self.payload), TEST_KEY=str(self.key), TEST_FINGERPRINT=pin['fingerprint'])
        self.mock('curl', '''import shutil
from pathlib import Path
if os.environ.get('TEST_DOWNLOAD_FAIL'): sys.exit(43)
target = Path(sys.argv[sys.argv.index('--output')+1])
if target.name == 'key.asc': shutil.copyfile(os.environ['TEST_KEY'], target)
elif target.name.endswith('.gpg'): target.write_bytes(b'synthetic detached signature')
else: shutil.copyfile(os.environ['TEST_PAYLOAD'], target)
''')
        self.mock('sha256sum', '''import hashlib
for line in sys.stdin:
    digest, path = line.strip().split('  ', 1)
    with open(path, 'rb') as source: actual = hashlib.sha256(source.read()).hexdigest()
    if digest != actual: sys.exit(1)
''')
        self.mock('gpg', '''from pathlib import Path
Path(sys.argv[sys.argv.index('--output')+1]).write_bytes(b'synthetic keyring')
''')
        self.mock('gpgv', '''if os.environ.get('TEST_SIGNATURE_FAIL'): sys.exit(2)
fingerprint = os.environ.get('TEST_SIGNER', os.environ['TEST_FINGERPRINT'])
print('[GNUPG:] VALIDSIG ' + fingerprint + ' 2026-10-20 1792517760 0 4 0 1 8 00 ' + fingerprint)
''')

    def library(self, body='prepare_signal_appimage; install_signal_appimage', dry_run=False):
        return subprocess.run(
            [test_dotfiles.BASH, '-c', 'set -euo pipefail; ROOT=$1; DRY_RUN=$2; source "$ROOT/lib/dotfiles.sh"\n' + body,
             'signal-fixture', str(self.repo), str(int(dry_run))],
            cwd=self.base, env=self.env, text=True, capture_output=True, timeout=20,
        )

    def test_checks_both_hashes_and_signature_before_publishing_without_running(self):
        result = self.library()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(self.payload.read_bytes(), (self.directory/'Signal.AppImage').read_bytes())
        self.assertTrue((self.directory/'Signal.AppImage').stat().st_mode & 0o100)
        self.assertEqual(2, len([c for c in self.calls() if c[0] == 'gpgv']))
        self.assertFalse(any('gnupg' in ' '.join(c) or c[0] in ('signal-desktop','sudo') for c in self.calls()))
        self.assertTrue(all('--homedir' in c for c in self.calls() if c[0] in ('gpg','gpgv')))

    def test_bad_signature_or_unexpected_signer_never_publishes(self):
        for key in ('TEST_SIGNATURE_FAIL','TEST_SIGNER'):
            self.env[key] = 'bad'
            self.assert_failed(self.library(), 'signature')
            self.assertFalse(self.directory.exists())
            self.assertFalse(self.cache.exists())
            self.env.pop(key)

    def test_bad_app_or_key_hash_never_calls_gpg_or_publishes(self):
        for target in (self.payload, self.key):
            original = target.read_bytes()
            target.write_bytes(b'changed bytes')
            self.assert_failed(self.library(), 'checksum mismatch')
            self.assertFalse(self.directory.exists())
            self.assertFalse(any(c[0] in ('gpg','gpgv') for c in self.calls()))
            target.write_bytes(original)

    def test_repeat_preserves_signal_self_updates_without_downloading_or_running(self):
        self.assertEqual(0, self.library().returncode)
        app = self.directory/'Signal.AppImage'
        app.write_bytes(b'self-updated application')
        self.log.unlink()
        result = self.library()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('Signal owns its updates', result.stderr)
        self.assertEqual(b'self-updated application', app.read_bytes())
        self.assertEqual([], self.calls())

    def test_unmanaged_partial_or_symlinked_install_is_not_adopted(self):
        self.directory.mkdir(parents=True)
        self.assert_failed(self.library(), 'Unmanaged/partial')
        self.assertEqual([], self.calls())
        self.directory.rmdir()
        self.directory.symlink_to(self.base)
        self.assert_failed(self.library(), 'Conflicting Signal parent')

    def test_download_failure_cleans_staging_and_preview_is_side_effect_free(self):
        before = self.snapshot()
        self.assertEqual(0, self.library(dry_run=True).returncode)
        self.assertEqual(before, self.snapshot())
        self.assertEqual([], self.calls())
        self.env['TEST_DOWNLOAD_FAIL'] = '1'
        self.assertEqual(43, self.library().returncode)
        self.assertEqual([], list(self.cache.parent.glob('.download.*')))
        self.assertFalse(self.directory.exists())

    def test_cache_corruption_stops_install_and_existing_path_app_is_not_replaced(self):
        self.assertEqual(0, self.library('prepare_signal_appimage').returncode)
        (self.cache/'Signal.AppImage').write_bytes(b'corrupt')
        self.assert_failed(self.library('install_signal_appimage'), 'checksum mismatch')
        self.assertFalse(self.directory.exists())
        self.mock('signal-desktop', 'sys.exit(97)')
        self.assert_failed(self.library('preflight_signal'), 'Conflicting Signal executable')
        self.assertFalse(any(c[0] == 'signal-desktop' for c in self.calls()))

    def test_signature_verification_precedes_the_protected_dnf_transactions(self):
        self.mock('sudo', '''args=sys.argv[1:]
if args[0] != 'dnf': sys.exit(97)
if 'repoquery' in args:
    for name in args[args.index('--queryformat')+2:]: print(name)
''')
        result = self.library('MODULES=(signal); PACKAGES=(); install_packages')
        self.assertEqual(0, result.returncode, result.stderr)
        calls = self.calls()
        verified = next(i for i, call in enumerate(calls) if call[0] == 'gpgv')
        upgraded = next(i for i, call in enumerate(calls) if call[:2] == ['sudo', 'dnf'] and 'upgrade' in call)
        self.assertLess(verified, upgraded)
        self.log.unlink()
        self.env['TEST_SIGNATURE_FAIL'] = '1'
        self.assert_failed(self.library('MODULES=(signal); PACKAGES=(); install_packages'), 'signature')
        self.assertFalse(any(c[:2] == ['sudo', 'dnf'] and ('upgrade' in c or 'install' in c) for c in self.calls()))

    def test_invalid_pin_or_key_rotation_refuses_before_downloading(self):
        path = self.repo / 'modules/signal-release.json'
        original = json.loads(path.read_text())
        for key, value in (('version', '8.32.0; command'), ('sha256', 'missing'), ('fingerprint', '0'*40)):
            path.write_text(json.dumps(original | {key: value}))
            self.assert_failed(self.library(), 'Could not validate initial Signal')
            self.assertEqual([], self.calls())


class Flatpaks(unittest.TestCase):
    mock = test_dotfiles.Fixture.mock
    calls = test_dotfiles.Fixture.calls
    assert_failed = test_dotfiles.Fixture.assert_failed

    def setUp(self):
        test_dotfiles.Fixture.setUp(self)
        self.state = self.base/'flatpaks.json'
        self.state.write_text(json.dumps({'remote': False, 'apps': {}}))
        self.env['TEST_FLATPAKS'] = str(self.state)
        self.mock('flatpak', '''from pathlib import Path
path=Path(os.environ['TEST_FLATPAKS']); state=json.loads(path.read_text()); action=sys.argv[1]
if '--user' not in sys.argv or '--system' in sys.argv or '-y' in sys.argv: sys.exit(97)
if os.environ.get('TEST_FLATPAK_FAIL') == action: sys.exit(43)
if action == 'remotes':
    if state['remote']: print('flathub\\t' + state.get('url','https://dl.flathub.org/repo/') + '\\t' + state.get('options',''))
elif action == 'remote-add': state['remote']=True
elif action == 'list': print('\\n'.join(state['apps']))
elif action == 'install': state['apps'][sys.argv[-1]]='flathub'
elif action == 'info': print(state['apps'][sys.argv[-1]])
elif action == 'update': pass
else: sys.exit(97)
path.write_text(json.dumps(state)) if action in ('remote-add','install') else None
''')

    def library(self, body='preflight_flatpaks; setup_flatpaks', modules='telegram gearlever', dry_run=False):
        return subprocess.run(
            [test_dotfiles.BASH,'-c','set -euo pipefail; ROOT=$1; DRY_RUN=$2; source "$ROOT/lib/dotfiles.sh"\nMODULES=(' + modules + ')\n' + body,
             'flatpak-fixture',str(self.repo),str(int(dry_run))],cwd=self.base,env=self.env,text=True,capture_output=True,timeout=20,
        )

    def test_installs_only_selected_user_apps_and_repeat_does_not_reinstall(self):
        result=self.library()
        self.assertEqual(0,result.returncode,result.stderr)
        self.assertEqual({'org.telegram.desktop':'flathub','it.mijorus.gearlever':'flathub'},json.loads(self.state.read_text())['apps'])
        self.log.unlink()
        self.assertEqual(0,self.library().returncode)
        self.assertFalse(any(c[1] in ('install','remote-add') for c in self.calls()))
        self.assertTrue(all('--user' in c and '--system' not in c for c in self.calls()))

    def test_unselected_modules_do_not_configure_flathub(self):
        self.assertEqual(0,self.library(modules='core').returncode)
        self.assertEqual([],self.calls())

    def test_remote_conflicts_and_unsigned_or_disabled_options_refuse_before_changes(self):
        for updates in ({'url':'https://example.invalid/repo/'},{'options':'no-gpg-verify'},{'options':'disabled'}):
            self.state.write_text(json.dumps({'remote':True,'apps':{}}|updates))
            self.log.unlink(missing_ok=True)
            self.assert_failed(self.library(),'remote')
            self.assertTrue(all(c[1]=='remotes' for c in self.calls()))

    def test_existing_app_from_another_remote_is_not_reinstalled_or_adopted(self):
        self.state.write_text(json.dumps({'remote':True,'apps':{'org.telegram.desktop':'other'}}))
        self.assert_failed(self.library(),'different remote')
        self.assertFalse(any(c[1] in ('install','remote-add') for c in self.calls()))

    def test_failures_propagate_and_dry_run_never_invokes_flatpak(self):
        self.assertEqual(0,self.library('preflight_flatpaks; setup_flatpaks; update_user_flatpaks',dry_run=True).returncode)
        self.assertEqual([],self.calls())
        for action in ('remotes','list','remote-add','install'):
            self.env['TEST_FLATPAK_FAIL']=action
            self.assert_failed(self.library())
        self.env['TEST_FLATPAK_FAIL']='update'
        self.assertEqual(43,self.library('update_user_flatpaks').returncode)

    def test_updates_all_user_apps_without_system_changes_or_sudo(self):
        self.assertEqual(0,self.library('update_user_flatpaks').returncode)
        self.assertEqual([['flatpak','update','--user']],self.calls())


class DesktopReleasePins(unittest.TestCase):
    def setUp(self):
        path=test_dotfiles.ROOT/'scripts/discord_release.py'
        spec=importlib.util.spec_from_file_location('discord_review',path)
        self.check=importlib.util.module_from_spec(spec); spec.loader.exec_module(self.check)

    def test_only_versioned_stable_vendor_rpm_urls_are_allowed(self):
        self.assertEqual('1.0.166',self.check.load_pin()['version'])
        for url in ('https://example.invalid/discord.rpm','https://stable.dl2.discordapp.net/apps/linux/1.0.166/discord-1.0.165.rpm','https://canary.dl2.discordapp.net/apps/linux/1.0.166/discord-1.0.166.rpm'):
            self.assertIsNone(self.check.URL.fullmatch(url))

    def test_update_notice_compares_bootstrap_version_and_never_downloads_payload(self):
        import contextlib,io
        with patch.object(self.check,'published_version',return_value='1.0.167'),patch.object(self.check.shutil,'which',return_value=None),contextlib.redirect_stdout(io.StringIO()) as output:
            self.check.check_updates()
        self.assertIn('New Discord RPM',output.getvalue())
        self.assertIn('client separately',output.getvalue())
