"""Signal menu/terminal equivalence using only a fake AppImage and fake HOME."""

import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / 'stow/signal/.local/bin/signal-desktop'
DESKTOP = ROOT / 'stow/signal/.local/share/applications/signal-desktop.desktop'


def menu_command():
    value = next(line.removeprefix('Exec=') for line in DESKTOP.read_text().splitlines() if line.startswith('Exec='))
    # Desktop-entry string escaping precedes Exec argument quoting. Unlike shlex,
    # desktop Exec quoting unescapes dollar signs without expanding variables.
    value = value.replace('\\\\', '\\').replace('\\$', '$')
    return shlex.split(value)


class SignalLauncher(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='signal-launcher-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home = self.base / 'home with spaces'
        app = self.home / '.local/share/dotfiles/signal/Signal.AppImage'
        app.parent.mkdir(parents=True)
        app.write_text(f'#!{sys.executable}\nimport json, os, sys\nwith open(os.environ["TEST_ARGS"], "w") as f: json.dump(sys.argv[1:], f)\n')
        app.chmod(0o755)
        launcher = self.home / '.local/bin/signal-desktop'
        launcher.parent.mkdir(parents=True)
        launcher.symlink_to(WRAPPER)
        self.args_file = self.base / 'args.json'
        self.env = os.environ | {'HOME': str(self.home), 'PATH': '/usr/bin:/bin', 'TEST_ARGS': str(self.args_file), 'DEBUG': '0'}

    def test_menu_launch_works_without_user_bin_on_desktop_path(self):
        command = menu_command()
        self.assertEqual('/bin/sh', command[0])
        self.assertEqual('%u', command[-1])
        result = subprocess.run(command[:-1], env=self.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(['--'], json.loads(self.args_file.read_text()))

    def test_menu_and_terminal_forward_identical_arguments_without_backend_override(self):
        uri = 'sgnl://test?text=spaces and "quotes";$(touch should-not-exist)'
        menu = menu_command()[:-1] + [uri]
        result = subprocess.run(menu, env=self.env, capture_output=True, text=True, timeout=10, cwd=self.base)
        self.assertEqual(0, result.returncode, result.stderr)
        menu_args = json.loads(self.args_file.read_text())
        terminal = ['/bin/bash', str(WRAPPER), '--', uri]
        result = subprocess.run(terminal, env=self.env, capture_output=True, text=True, timeout=10, cwd=self.base)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(['--', uri], menu_args)
        self.assertEqual(menu_args, json.loads(self.args_file.read_text()))
        self.assertFalse((self.base / 'should-not-exist').exists())
        self.assertNotIn('--password-store=', DESKTOP.read_text())
