"""Piped bootstrap fixtures: source and confirmation input stay separate."""

import subprocess
import unittest

import test_dotfiles


class BootstrapPipe(unittest.TestCase):
    setUp = test_dotfiles.Fixture.setUp
    mock = test_dotfiles.Fixture.mock
    calls = test_dotfiles.Fixture.calls
    snapshot = test_dotfiles.Fixture.snapshot
    assert_failed = test_dotfiles.Fixture.assert_failed

    def run_pipe(self, *args, tail=''):
        return subprocess.run(
            [test_dotfiles.BASH, '-s', '--', *args],
            input=(self.repo / 'install.sh').read_text() + tail,
            env=self.env, cwd=self.repo, text=True, capture_output=True, timeout=20,
        )

    def clone_fixture(self):
        self.mock('git', '''from pathlib import Path
if 'clone' in sys.argv:
    setup = Path(sys.argv[-1]) / 'bin/setup'
    setup.parent.mkdir(parents=True)
    setup.write_text('set -euo pipefail\\nIFS= read -r answer\\nprintf "confirmation=%s\\\\n" "$answer"\\nprintf "argument=%s\\\\n" "$@"\\n')
elif 'check-ref-format' not in sys.argv:
    sys.exit(97)
''')

    def test_piped_install_dispatch_reads_terminal_not_script_and_preserves_args(self):
        self.clone_fixture()
        self.terminal.write_text('approved fixture response\n')
        result = self.run_pipe('--groups', 'core', '--modules', 'fixture-tool',
                               tail="printf 'source-input-restored\\n'\n")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn('confirmation=approved fixture response', result.stdout)
        self.assertIn('argument=--groups\nargument=core\nargument=--modules\nargument=fixture-tool', result.stdout)
        self.assertIn('source-input-restored', result.stdout)

    def test_git_prerequisite_confirmation_also_uses_terminal(self):
        self.clone_fixture()
        template = self.base / 'git-to-install'
        (self.path / 'git').rename(template)
        self.env['TEST_GIT_TEMPLATE'] = str(template)
        self.terminal.write_text('git approved\nsetup approved\n')
        self.mock('sudo', '''from pathlib import Path
import shutil
answer = b''
while not answer.endswith(b'\\n'):
    chunk = os.read(0, 1)
    if not chunk: sys.exit(43)
    answer += chunk
if answer.strip() != b'git approved': sys.exit(43)
path = Path(os.environ['PATH']) / 'git'
shutil.copyfile(os.environ['TEST_GIT_TEMPLATE'], path)
path.chmod(0o755)
''')
        result = self.run_pipe('--groups', 'core')
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn('confirmation=setup approved', result.stdout)

    def test_missing_terminal_refuses_before_git_or_package_changes(self):
        self.terminal.unlink()
        self.assert_failed(self.run_pipe(), 'requires a terminal')
        self.assertFalse(any(c[0] in ('git', 'sudo', 'curl', 'wget') for c in self.calls()))
        self.assertEqual({}, self.snapshot())

    def test_piped_help_and_preview_need_no_terminal_and_do_not_mutate(self):
        self.terminal.unlink()
        self.clone_fixture()
        for args in (('--help',), ('--dry-run', '--groups', 'core')):
            self.log.unlink(missing_ok=True)
            result = self.run_pipe(*args)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual({}, self.snapshot())
            self.assertFalse(any(c[0] == 'sudo' or 'clone' in c for c in self.calls()))
