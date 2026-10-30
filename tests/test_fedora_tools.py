"""Custom Fedora tool setup uses the shared platform contract."""

import subprocess
import shutil
import unittest

import test_dotfiles


class FedoraTools(unittest.TestCase):
    mock = test_dotfiles.Fixture.mock
    calls = test_dotfiles.Fixture.calls
    assert_failed = test_dotfiles.Fixture.assert_failed

    def setUp(self):
        test_dotfiles.Fixture.setUp(self)
        self.mock("bat", "sys.exit(0 if sys.argv[1:3] == ['cache', '--build'] else 97)")
        self.env['TEST_CODIUM_STATE'] = str(self.base / 'codium-state.json')
        self.mock("codium", '''from pathlib import Path
import zipfile
path=Path(os.environ['TEST_CODIUM_STATE'])
state=json.loads(path.read_text()) if path.exists() else {'extensions': [], 'theme': ''}
action=sys.argv[1]
if action == '--list-extensions':
    print('\\n'.join(state['extensions']))
elif action == '--locate-extension':
    print(state['theme'])
elif action == '--install-extension':
    if os.environ.get('TEST_THEME_INSTALL_FAIL') and sys.argv[-1].endswith('.vsix'): sys.exit(43)
    if sys.argv[-1].endswith('.vsix'):
        destination=Path(os.environ['HOME'])/'.vscode-oss/extensions/w3irdrobot.kestrel-theme-0.0.1'
        with zipfile.ZipFile(sys.argv[-1]) as archive:
            for name in ('package.json','themes/kestrel-color-theme.json'):
                target=destination/name; target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(archive.read('extension/'+name))
        manifest=json.loads((destination/'package.json').read_text())
        manifest['__metadata']={'installedTimestamp':12345}
        (destination/'package.json').write_text(json.dumps(manifest))
        if not os.environ.get('TEST_THEME_UNREGISTERED'):
            state['extensions'].append('w3irdrobot.kestrel-theme')
        state['theme']=str(destination)
    else:
        state['extensions'].append(sys.argv[-1])
    path.write_text(json.dumps(state))
else: sys.exit(97)
''')

    def run_module(self, name):
        return subprocess.run(
            [test_dotfiles.BASH, str(self.repo / "modules" / f"{name}.sh")],
            cwd=self.repo, env=self.env, text=True, capture_output=True, timeout=20,
        )

    def test_bat_theme_build_accepts_fedora_44(self):
        result = self.run_module("bat")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(any(c[0] == "bat" and "--source" in c for c in self.calls()))

    def test_ghostty_sets_only_plasma_terminal_keys(self):
        result = self.run_module("ghostty")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([
            ["kwriteconfig6", "--file", "kdeglobals", "--group", "General",
             "--key", "TerminalApplication", "ghostty"],
            ["kwriteconfig6", "--file", "kdeglobals", "--group", "General",
             "--key", "TerminalService", "com.mitchellh.ghostty.desktop"],
            ["kwriteconfig6", "--file", "kglobalshortcutsrc", "--group", "services",
             "--group", "org.kde.konsole.desktop", "--key", "_launch", "none"],
            ["kwriteconfig6", "--file", "kglobalshortcutsrc", "--group", "services",
             "--group", "com.mitchellh.ghostty.desktop", "--key", "_launch", "Ctrl+Alt+T"],
        ], [c for c in self.calls() if c[0] == "kwriteconfig6"])
        self.assertFalse(any(c[0] == "gdbus" for c in self.calls()))

    @unittest.skipUnless(shutil.which("kwriteconfig6"), "KConfig writer not installed")
    def test_ghostty_preserves_desktop_settings_and_is_idempotent(self):
        (self.path / "kwriteconfig6").unlink()
        (self.path / "kwriteconfig6").symlink_to(shutil.which("kwriteconfig6"))
        config = self.home / ".config/kdeglobals"
        config.parent.mkdir(parents=True)
        config.write_text("[General]\nColorScheme=Kestrel\nTerminalApplication=konsole\n"
                          "\n[KDE]\nSingleClick=false\n")
        shortcuts = config.with_name("kglobalshortcutsrc")
        shortcuts.write_text("[kwin]\nOverview=Meta+W,Meta+W,Overview\n")
        result = self.run_module("ghostty")
        self.assertEqual(0, result.returncode, result.stderr)
        first = config.read_text()
        first_shortcuts = shortcuts.read_text()
        for entry in ("Overview=Meta+W,Meta+W,Overview",
                      "[services][org.kde.konsole.desktop]\n_launch=none",
                      "[services][com.mitchellh.ghostty.desktop]\n_launch=Ctrl+Alt+T"):
            self.assertIn(entry, first_shortcuts)
        for entry in ("ColorScheme=Kestrel", "SingleClick=false",
                      "TerminalApplication=ghostty",
                      "TerminalService=com.mitchellh.ghostty.desktop"):
            self.assertIn(entry, first)
        result = self.run_module("ghostty")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(first, config.read_text())
        self.assertEqual(first_shortcuts, shortcuts.read_text())

    def test_ghostty_updates_running_plasma_shortcut(self):
        self.env["DBUS_SESSION_BUS_ADDRESS"] = "fixture-session"
        self.mock("gdbus", '''
method = sys.argv[sys.argv.index('--method') + 1]
if method.endswith('NameHasOwner'): print('(true,)')
elif method.endswith('doRegister'): print('()')
elif method.endswith('setShortcut'):
    if sys.argv[-2] == '[201326676]': print('([201326676],)')
    else: print('(@ai [],)')
else: sys.exit(97)
''')
        result = self.run_module("ghostty")
        self.assertEqual(0, result.returncode, result.stderr)
        calls = [c for c in self.calls() if c[0] == "gdbus"]
        self.assertEqual(5, len(calls))
        self.assertIn("org.kde.konsole.desktop", calls[-2][-3])
        self.assertEqual(['[]', '6'], calls[-2][-2:])
        self.assertIn("com.mitchellh.ghostty.desktop", calls[-1][-3])
        self.assertEqual(['[201326676]', '6'], calls[-1][-2:])

    def test_ghostty_reports_live_shortcut_conflicts(self):
        self.env["DBUS_SESSION_BUS_ADDRESS"] = "fixture-session"
        self.mock("gdbus", "print('(true,)' if 'org.freedesktop.DBus.NameHasOwner' in sys.argv else '(@ai [],)')")
        self.assert_failed(self.run_module("ghostty"), "Could not assign Ctrl+Alt+T")

    def test_ghostty_missing_writer_fails_without_changes(self):
        (self.path / "kwriteconfig6").unlink()
        self.assert_failed(self.run_module("ghostty"), "Install the kf6-kconfig package first")

    def test_ghostty_rejects_arguments(self):
        result = subprocess.run(
            [test_dotfiles.BASH, str(self.repo / "modules/ghostty.sh"), "--unknown"],
            env=self.env, text=True, capture_output=True, timeout=20,
        )
        self.assert_failed(result, "takes no arguments")
        self.assertFalse(any(c[0] == "kwriteconfig6" for c in self.calls()))

    def test_vscodium_extension_setup_accepts_fedora_44(self):
        result = self.run_module("vscodium")
        self.assertEqual(0, result.returncode, result.stderr)
        installed = [c for c in self.calls() if c[0] == "codium" and "--install-extension" in c]
        manifest = self.repo / "stow/vscodium/.config/VSCodium/extensions.txt"
        self.assertEqual(len(manifest.read_text().splitlines()) + 1, len(installed))
        self.assertEqual(1, sum(c[-1].endswith('.vsix') for c in installed))

    def test_old_distro_or_wrong_fedora_release_stops_before_tool_execution(self):
        for text in ("ID=arch\n", "ID=manjaro\n", "ID=fedora\nVERSION_ID=43\n"):
            for module in ("bat", "vscodium", "ghostty"):
                with self.subTest(text=text, module=module):
                    self.log.unlink(missing_ok=True)
                    self.os_release.write_text(text)
                    self.assert_failed(self.run_module(module), "Only Fedora KDE Plasma Desktop 44")
                    self.assertFalse(any(c[0] in ("bat", "codium", "kwriteconfig6", "sudo") for c in self.calls()))
