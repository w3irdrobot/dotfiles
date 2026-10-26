"""Secrets dispatch uses fixture-only helpers, never real keys or archives."""

import subprocess
import unittest

import test_dotfiles


class SecretsCLI(unittest.TestCase):
    setUp = test_dotfiles.Fixture.setUp
    mock = test_dotfiles.Fixture.mock
    calls = test_dotfiles.Fixture.calls
    snapshot = test_dotfiles.Fixture.snapshot
    run_cli = test_dotfiles.Fixture.run_cli
    assert_failed = test_dotfiles.Fixture.assert_failed

    def stub(self, action, status=0):
        helper = self.repo / "stow/gnupg/.local/bin" / f"secrets_{action}"
        helper.write_text(
            '#!/usr/bin/env bash\n'
            'set -euo pipefail\n'
            'private_fixture_value=FAKE_SECRETS_TRACE_SENTINEL\n'
            f'printf "repo-{action}|%s|%s|%s\\n" "$#" "$PWD" "$DEBUG"\n'
            'case $- in *x*|*v*) exit 98 ;; esac\n'
            f'exit {status}\n'
        )
        return helper

    def test_help_and_previews_never_dispatch_helpers_or_query_the_host(self):
        for action in ("export", "import"):
            self.stub(action, status=97)
        for args in (("secrets", "--help"), ("secrets", "-h"),
                     ("secrets", "export", "--help"), ("secrets", "import", "--help"),
                     ("secrets", "export", "--dry-run"), ("secrets", "import", "--dry-run")):
            with self.subTest(args=args):
                before = self.snapshot()
                result = self.run_cli(*args)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertNotIn("repo-export", result.stdout)
                self.assertNotIn("repo-import", result.stdout)
                self.assertEqual([], self.calls())
                self.assertEqual(before, self.snapshot())

    def test_invalid_actions_options_and_positionals_stop_before_dispatch(self):
        for action in ("export", "import"):
            self.stub(action, status=97)
        for args in (("secrets",), ("secrets", "delete"), ("secrets", "../export"),
                     ("secrets", "export", "--groups", "core"),
                     ("secrets", "import", "--modules", "gnupg"),
                     ("secrets", "export", "--docker-group"),
                     ("secrets", "import", "FAKE_PASSPHRASE"),
                     ("secrets", "export", "--help", "--unknown"),
                     ("secrets", "--help", "import")):
            with self.subTest(args=args):
                before = self.snapshot()
                result = self.run_cli(*args)
                self.assert_failed(result)
                self.assertNotIn("FAKE_PASSPHRASE", result.stdout + result.stderr)
                self.assertNotIn("repo-export", result.stdout)
                self.assertNotIn("repo-import", result.stdout)
                self.assertEqual([], self.calls())
                self.assertEqual(before, self.snapshot())

    def test_dispatch_uses_checkout_helpers_not_path_and_preserves_status(self):
        for action, status in (("export", 0), ("import", 43)):
            with self.subTest(action=action):
                self.stub(action, status=status)
                self.mock(f"secrets_{action}", "sys.exit(97)")
                before = self.snapshot()
                result = self.run_cli("secrets", action)
                self.assertEqual(status, result.returncode, result.stderr)
                self.assertEqual(f"repo-{action}|0|{self.repo.resolve()}|0\n", result.stdout)
                self.assertEqual([], self.calls())
                self.assertEqual(before, self.snapshot())

    def test_secrets_dispatch_does_not_apply_fedora_provisioning_checks(self):
        self.os_release.write_text("ID=not-fedora\n")
        self.mock("uname", "sys.exit(97)")
        self.stub("export")
        result = self.run_cli("secrets", "export")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([], self.calls())

    def test_dispatch_preserves_external_working_directory(self):
        self.stub("import")
        directory = self.base / "private migration directory"
        directory.mkdir()
        result = subprocess.run(
            [test_dotfiles.BASH, str(self.repo / "bin/dotfiles"), "secrets", "import"],
            cwd=directory, env=self.env, text=True, capture_output=True, timeout=20,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(f"repo-import|0|{directory.resolve()}|0\n", result.stdout)

    def test_missing_or_symlinked_helper_is_refused_without_path_fallback(self):
        helper = self.stub("export")
        helper.unlink()
        self.mock("secrets_export", "sys.exit(97)")
        self.assert_failed(self.run_cli("secrets", "export"), "Missing repository secrets helper")
        target = self.base / "unmanaged-helper"
        target.write_text('#!/usr/bin/env bash\nexit 97\n')
        helper.symlink_to(target)
        self.assert_failed(self.run_cli("secrets", "export"), "unexpected symlink")
        self.assertEqual([], self.calls())

    def test_debug_and_inherited_trace_options_do_not_reach_helpers(self):
        self.stub("export")
        self.env.update(DEBUG="1", SHELLOPTS="braceexpand:hashall:interactive-comments:xtrace:verbose")
        result = self.run_cli("secrets", "export")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertNotIn("FAKE_SECRETS_TRACE_SENTINEL", result.stdout + result.stderr)
        self.assertEqual(f"repo-export|0|{self.repo.resolve()}|0\n", result.stdout)

    def test_top_level_help_advertises_secrets_commands(self):
        result = self.run_cli("--help")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("dotfiles secrets export|import", result.stdout)
