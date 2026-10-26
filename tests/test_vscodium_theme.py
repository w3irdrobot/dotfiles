"""Local VSIX build/registration fixtures; never run a real editor or npm."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

import test_dotfiles
import test_fedora_tools

SPEC = importlib.util.spec_from_file_location('build_theme', test_dotfiles.ROOT / 'scripts/build-vscodium-theme.py')
BUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)


class ThemeArchive(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kestrel-vsix-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def test_vsix_has_regular_source_payload_and_installation_manifests(self):
        output = self.base / 'kestrel.vsix'
        BUILD.build(output)
        with zipfile.ZipFile(output) as archive:
            self.assertEqual({'[Content_Types].xml', 'extension.vsixmanifest',
                              'extension/package.json', 'extension/themes/kestrel-color-theme.json'}, set(archive.namelist()))
            for name in BUILD.FILES:
                self.assertEqual((BUILD.THEME / name).read_bytes(), archive.read('extension/' + name))
            root = ET.fromstring(archive.read('extension.vsixmanifest'))
            ns = {'v': 'http://schemas.microsoft.com/developer/vsx-schema/2011'}
            identity = root.find('v:Metadata/v:Identity', ns)
            self.assertEqual('kestrel-theme', identity.get('Id'))
            self.assertEqual('w3irdrobot', identity.get('Publisher'))
            self.assertEqual('Microsoft.VisualStudio.Code', root.find('v:Installation/v:InstallationTarget', ns).get('Id'))

    def test_builds_are_deterministic_and_never_overwrite(self):
        one, two = self.base / 'one.vsix', self.base / 'two.vsix'
        BUILD.build(one)
        BUILD.build(two)
        self.assertEqual(one.read_bytes(), two.read_bytes())
        before = one.read_bytes()
        with self.assertRaises(FileExistsError):
            BUILD.build(one)
        self.assertEqual(before, one.read_bytes())

    def test_stow_no_longer_deploys_extension_payload(self):
        source = test_dotfiles.ROOT / 'stow/vscodium'
        self.assertFalse(any('.vscode-oss' in p.parts for p in source.rglob('*')))


class ThemeInstallation(unittest.TestCase):
    setUp = test_fedora_tools.FedoraTools.setUp
    mock = test_dotfiles.Fixture.mock
    calls = test_dotfiles.Fixture.calls
    assert_failed = test_dotfiles.Fixture.assert_failed
    run_module = test_fedora_tools.FedoraTools.run_module

    def test_installed_theme_is_registered_with_regular_files_and_reused_on_repeat(self):
        result = self.run_module('vscodium')
        self.assertEqual(0, result.returncode, result.stderr)
        state = json.loads(Path(self.env['TEST_CODIUM_STATE']).read_text())
        self.assertIn('w3irdrobot.kestrel-theme', state['extensions'])
        directory = Path(state['theme'])
        for name in BUILD.FILES:
            self.assertTrue((directory / name).is_file())
            self.assertFalse((directory / name).is_symlink())
        self.log.unlink()
        result = self.run_module('vscodium')
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('reusing it', result.stderr)
        self.assertFalse(any('--install-extension' in c for c in self.calls()))
        self.assertFalse(any(c[0] in ('npm', 'npx', 'sudo') or '--force' in c for c in self.calls()))

    def test_legacy_links_are_reported_before_editor_changes_and_left_untouched(self):
        directory = self.home / '.vscode-oss/extensions/w3irdrobot.kestrel-theme-0.0.1'
        directory.mkdir(parents=True)
        manifest = directory / 'package.json'
        old_source = self.repo / 'stow/vscodium/.vscode-oss/extensions/w3irdrobot.kestrel-theme-0.0.1/package.json'
        manifest.symlink_to(old_source)
        self.assert_failed(self.run_module('vscodium'), 'legacy Stow links')
        self.assertTrue(manifest.is_symlink())
        self.assertFalse(any(c[0] in ('codium', 'sudo') for c in self.calls()))

    def test_modified_registered_theme_is_not_overwritten(self):
        self.assertEqual(0, self.run_module('vscodium').returncode)
        state = json.loads(Path(self.env['TEST_CODIUM_STATE']).read_text())
        colors = Path(state['theme']) / 'themes/kestrel-color-theme.json'
        colors.write_text('{"name":"user modification"}\n')
        self.log.unlink()
        self.assert_failed(self.run_module('vscodium'), 'refusing to replace')
        self.assertEqual('{"name":"user modification"}\n', colors.read_text())
        self.assertFalse(any('--install-extension' in c for c in self.calls()))

    def test_failed_or_unregistered_vsix_install_does_not_install_marketplace_extensions(self):
        self.env['TEST_THEME_INSTALL_FAIL'] = '1'
        self.assert_failed(self.run_module('vscodium'), 'local Kestrel VSIX failed')
        self.assertFalse(any('--install-extension' in c and not c[-1].endswith('.vsix') for c in self.calls()))
        del self.env['TEST_THEME_INSTALL_FAIL']
        self.env['TEST_THEME_UNREGISTERED'] = '1'
        self.assert_failed(self.run_module('vscodium'), 'did not register')

    def test_unregistered_regular_directory_is_not_adopted(self):
        directory = self.home / '.vscode-oss/extensions/w3irdrobot.kestrel-theme-0.0.1'
        directory.mkdir(parents=True)
        (directory / 'package.json').write_text('{}')
        self.assert_failed(self.run_module('vscodium'), 'Unregistered Kestrel directory already exists')
        self.assertEqual('{}', (directory / 'package.json').read_text())
        self.assertFalse(any('--install-extension' in c for c in self.calls()))
