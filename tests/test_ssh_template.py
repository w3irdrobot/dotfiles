"""Only generic SSH defaults belong in Git; host migration uses synthetic data."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SshTemplate(unittest.TestCase):
    def test_template_contains_only_the_local_include_and_generic_defaults(self):
        config = ROOT / 'stow/ssh/.ssh/config'
        directives = [line.strip() for line in config.read_text().splitlines()
                      if line.strip() and not line.lstrip().startswith('#')]
        self.assertEqual([
            'Include ~/.ssh/config.local',
            'Host *',
            'AddKeysToAgent yes',
            'IdentitiesOnly yes',
        ], directives)
        self.assertEqual(['config'], sorted(p.name for p in config.parent.iterdir()))

    def test_generic_template_does_not_export_stale_hosts_without_local_fragment(self):
        source = (ROOT / 'stow/gnupg/.local/bin/secrets_export').read_text()
        self.assertTrue(source.endswith('main "$@"\n'))
        definitions = source.removesuffix('main "$@"\n')
        with tempfile.TemporaryDirectory(prefix='ssh-template-') as directory:
            home = Path(directory)
            (home / '.ssh').mkdir()
            shutil.copyfile(ROOT / 'stow/ssh/.ssh/config', home / '.ssh/config')
            result = subprocess.run(
                [shutil.which('bash'), '--noprofile', '--norc'],
                input=definitions + '\nlist_ssh_config_hosts\n',
                cwd=home, env=os.environ | {'HOME': str(home)},
                capture_output=True, text=True, timeout=10,
            )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual('', result.stdout)
