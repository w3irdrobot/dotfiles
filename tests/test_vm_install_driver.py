"""Offline install-driver checks; no SSH, Lima, recipes, or host credentials."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import shlex
import shutil
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "vm_install", Path(__file__).parent / "vm/run-install.py")
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)
COMMIT = "a" * 40
RECIPE = "b" * 64


def parser():
    return driver.InstallParser(COMMIT, RECIPE)


def ready(state, phase):
    phases = (driver.DOWNLOAD_PHASE, driver.INSTALL_PHASE, driver.HELPER_PHASE)
    start = phases.index(state.phase) + 1 if state.phase in phases else 0
    state.feed((state.marker + "\n" + "\n".join(phases[start:phases.index(phase) + 1]) + "\n").encode())


def native_finished(state):
    ready(state, driver.DOWNLOAD_PHASE)
    state.feed((driver.bootstrap.PROMPTS[0] + "\n").encode())
    state.feed((driver.INSTALL_PHASE + "\n" + driver.bootstrap.PROMPTS[1] + "\n").encode())


class InstallDriver(unittest.TestCase):
    def test_pins_required_before_subprocess(self):
        for args in ([], ["--commit", COMMIT], ["--recipe-sha256", RECIPE],
                     ["--commit", "master", "--recipe-sha256", RECIPE],
                     ["--commit", COMMIT, "--recipe-sha256", RECIPE[:-1]]):
            with self.subTest(args=args), patch.object(driver.sys, "argv", ["run-install.py", *args]), \
                    patch.object(driver.subprocess, "run") as run, \
                    contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                driver.main()
            self.assertEqual(2, caught.exception.code)
            run.assert_not_called()

    def test_pin_validation_and_normalization(self):
        self.assertEqual(COMMIT, driver.pin(COMMIT.upper(), 40))
        for value in ("a" * 39, "a" * 41, "g" * 40, ";" + "a" * 39, "a" * 39 + "\n"):
            with self.assertRaises(driver.argparse.ArgumentTypeError):
                driver.remote_script(value, RECIPE)

    def test_hash_marker_required_for_approval(self):
        state = parser()
        with self.assertRaises(driver.bootstrap.Refused):
            state.feed(driver.bootstrap.PROMPTS[0].encode())
        self.assertEqual(0, state.downloads)

    def test_wrong_hash_marker_not_verified(self):
        state = parser()
        state.feed((driver.verified_marker(COMMIT, "c" * 64) + "\n").encode())
        self.assertFalse(state.verified)

    def test_native_approvals_once_each(self):
        state = parser()
        ready(state, driver.DOWNLOAD_PHASE)
        self.assertEqual([b"y\n"], state.feed(driver.bootstrap.PROMPTS[0].encode()))
        state.feed(("\ny\n" + driver.INSTALL_PHASE + "\n").encode())
        self.assertEqual([b"y\n"], state.feed(driver.bootstrap.PROMPTS[1].encode()))
        self.assertEqual((1, 1), (state.downloads, state.installs))
        self.assertTrue(state.native_install_approved)
        self.assertFalse(state.paru_install_approved)
        with self.assertRaises(driver.bootstrap.Refused):
            state.feed(("\n" + driver.bootstrap.PROMPTS[1]).encode())

    def test_local_paru_and_resulting_install_once(self):
        state = parser()
        native_finished(state)
        state.feed((driver.HELPER_PHASE + "\n").encode())
        self.assertEqual([b"y\n"], state.feed(driver.PARU_PROMPT.encode()))
        self.assertEqual([b"y\n"], state.feed(("\n" + driver.bootstrap.PROMPTS[1]).encode()))
        self.assertEqual(2, state.installs)
        self.assertTrue(state.native_install_approved)
        self.assertTrue(state.paru_install_approved)
        with self.assertRaises(driver.bootstrap.Refused):
            state.feed(("\n" + driver.bootstrap.PROMPTS[1]).encode())

    def test_noop_native_transactions_allow_pinned_paru(self):
        for download, install in ((False, False), (True, False), (False, True)):
            with self.subTest(download=download, install=install):
                state = parser()
                ready(state, driver.DOWNLOAD_PHASE)
                if download:
                    self.assertEqual([b"y\n"], state.feed((driver.bootstrap.PROMPTS[0] + "\n").encode()))
                state.feed((driver.INSTALL_PHASE + "\n").encode())
                if install:
                    self.assertEqual([b"y\n"], state.feed((driver.bootstrap.PROMPTS[1] + "\n").encode()))
                state.feed((driver.HELPER_PHASE + "\n").encode())
                self.assertEqual([b"y\n"], state.feed(driver.PARU_PROMPT.encode()))
                self.assertEqual([b"y\n"], state.feed(("\n" + driver.bootstrap.PROMPTS[1]).encode()))
                self.assertEqual(int(download), state.downloads)
                self.assertEqual(install, state.native_install_approved)
                self.assertTrue(state.paru_install_approved)
                self.assertEqual(1 + int(install), state.installs)
                with self.assertRaises(driver.bootstrap.Refused):
                    state.feed(("\n" + driver.bootstrap.PROMPTS[1]).encode())

    def test_missing_full_upgrade_phase_refuses_helper_and_review(self):
        state = parser()
        ready(state, driver.DOWNLOAD_PHASE)
        with self.assertRaises(driver.bootstrap.Refused):
            state.feed((driver.HELPER_PHASE + "\n").encode())
        self.assertEqual(driver.DOWNLOAD_PHASE, state.phase)
        with self.assertRaises(driver.bootstrap.Refused):
            state.feed(driver.PARU_PROMPT.encode())
        self.assertFalse(state.paru_approved)

    def test_unverified_repeated_and_out_of_order_phases_refused(self):
        cases = (
            (False, (), driver.DOWNLOAD_PHASE),
            (True, (), driver.INSTALL_PHASE),
            (True, (), driver.HELPER_PHASE),
            (True, (driver.DOWNLOAD_PHASE,), driver.DOWNLOAD_PHASE),
            (True, (driver.DOWNLOAD_PHASE,), driver.AUR_PHASE),
            (True, (driver.DOWNLOAD_PHASE, driver.INSTALL_PHASE), driver.INSTALL_PHASE),
            (True, (driver.DOWNLOAD_PHASE, driver.INSTALL_PHASE), driver.DOWNLOAD_PHASE),
            (True, (driver.DOWNLOAD_PHASE, driver.INSTALL_PHASE, driver.HELPER_PHASE), driver.HELPER_PHASE),
        )
        for verified, prior, next_phase in cases:
            with self.subTest(verified=verified, prior=prior, next_phase=next_phase):
                state = parser()
                if verified:
                    state.feed((state.marker + "\n").encode())
                for phase in prior:
                    state.feed((phase + "\n").encode())
                with self.assertRaises(driver.bootstrap.Refused):
                    state.feed((next_phase + "\n").encode())
                self.assertEqual((0, 0, False), (state.downloads, state.installs, state.paru_approved))

    def test_phase_markers_wait_for_newline_without_duplicate_transitions(self):
        for phase in (driver.DOWNLOAD_PHASE, driver.INSTALL_PHASE, driver.HELPER_PHASE):
            data = phase.encode()
            for split in range(len(data) + 1):
                with self.subTest(phase=phase, split=split):
                    state = parser()
                    if phase == driver.DOWNLOAD_PHASE:
                        state.feed((state.marker + "\n").encode())
                    else:
                        previous = driver.DOWNLOAD_PHASE if phase == driver.INSTALL_PHASE else driver.INSTALL_PHASE
                        ready(state, previous)
                    previous = state.phase
                    self.assertEqual([], state.feed(data[:split]))
                    self.assertEqual([], state.feed(data[split:]))
                    self.assertEqual(previous, state.phase)
                    self.assertEqual([], state.feed(b"\r\n"))
                    self.assertEqual(phase, state.phase)

    def test_repeated_download_confirmation_refused(self):
        state = parser()
        ready(state, driver.DOWNLOAD_PHASE)
        state.feed((driver.bootstrap.PROMPTS[0] + "\n").encode())
        with self.assertRaises(driver.bootstrap.Refused):
            state.feed(driver.bootstrap.PROMPTS[0].encode())
        self.assertEqual(1, state.downloads)

    def test_duplicate_local_paru_approval_refused(self):
        state = parser()
        native_finished(state)
        state.feed((driver.HELPER_PHASE + "\n" + driver.PARU_PROMPT + "\n").encode())
        with self.assertRaises(driver.bootstrap.Refused):
            state.feed(driver.PARU_PROMPT.encode())

    def test_all_prompt_byte_boundaries_with_ansi(self):
        for prompt, phase in ((driver.bootstrap.PROMPTS[0], driver.DOWNLOAD_PHASE),
                              (driver.bootstrap.PROMPTS[1], driver.INSTALL_PHASE),
                              (driver.PARU_PROMPT, driver.HELPER_PHASE)):
            data = ("\x1b[1m" + prompt + "\x1b[0m ").encode()
            for split in range(len(data) + 1):
                with self.subTest(prompt=prompt, split=split):
                    state = parser()
                    if prompt == driver.PARU_PROMPT:
                        native_finished(state)
                    ready(state, phase)
                    self.assertEqual([b"y\n"], state.feed(data[:split]) + state.feed(data[split:]))

    def test_pinned_prompt_wrong_phase_or_not_exact_refused(self):
        for prompt in (driver.PARU_PROMPT, driver.PARU_PROMPT.replace("unchanged", "updated")):
            state = parser()
            ready(state, driver.INSTALL_PHASE)
            with self.assertRaises(driver.bootstrap.Refused):
                state.feed(prompt.encode())
            self.assertFalse(state.paru_approved)

    def test_ordinary_output_questions_do_not_interrupt_transactions(self):
        state = parser()
        for text in ("Downloading https://example.invalid/pkg?mirror=1\n",
                     "==> Retrieving https://example.invalid/source?archive=1\n",
                     "==> Downloading https://example.invalid/source?\n",
                     "(42/42) package description: got a question?\n",
                     "# PKGBUILD comment: what happens next?\n",
                     "# Build something? [y/N]\n",
                     "pkgdesc='Question? [Y/n]'\n",
                     "warning: package description includes [thing/path]\n"):
            self.assertEqual([], state.feed(text.encode()))

    def test_normal_build_output_all_byte_boundaries(self):
        for text in ("==> Entering fakeroot environment...\n",
                     "==> Skipping source retrieval...\n",
                     "==> Downloading https://example.invalid/source?archive=1\n",
                     "==> Skipping https://example.invalid/source?mirror=1\n",
                     "==> Entering https://example.invalid/source?build=1\n",
                     "==> Retrieving https://example.invalid/source?\n"):
            data = ("\x1b[1m" + text.rstrip("\n") + "\x1b[0m\r\n").encode()
            for split in range(len(data) + 1):
                with self.subTest(text=text, split=split):
                    state = parser()
                    self.assertEqual([], state.feed(data[:split]))
                    self.assertEqual([], state.feed(data[split:]))
                    self.assertEqual(b"", state.pending)
                    self.assertEqual((0, 0, False), (state.downloads, state.installs, state.paru_approved))

    def test_incomplete_generic_prefixes_wait_for_completion(self):
        for prefix in ("==> Enter", ":: Select", "==> Skip"):
            state = parser()
            self.assertEqual([], state.feed(prefix.encode()))
            self.assertEqual(prefix.encode(), state.pending)
            with self.assertRaises(driver.bootstrap.Refused):
                state.feed(b"\n")
            state = parser()
            self.assertIsNone(state.line(prefix, complete=False))
            with self.assertRaises(driver.bootstrap.Refused):
                state.line(prefix)

    def test_real_questions_all_byte_boundaries(self):
        for text in (":: Replace old with new? [Y/n]", ":: Import PGP key? [Y/n]",
                     ":: Enter a selection (default=all):", "==> Packages to cleanBuild?",
                     "==> Diffs to show?", ":: Proceed to review? [Y/n]",
                     "[sudo] password for guest:", "Choose a provider:",
                     "==> Enter\n", ":: Select a provider\n",
                     "==> [N]one [A]ll [Ab]ort [I]nstalled [No]tInstalled\n"):
            data = text.encode()
            for split in range(len(data) + 1):
                with self.subTest(text=text, split=split):
                    state = parser()
                    with self.assertRaises(driver.bootstrap.Refused):
                        state.feed(data[:split])
                        state.feed(data[split:])
                    self.assertEqual((0, 0, False), (state.downloads, state.installs, state.paru_approved))

    def test_unterminated_choice_menu_waits_without_answering(self):
        state = parser()
        menu = b"==> [N]one [A]ll [Ab]ort [I]nstalled [No]tInstalled"
        self.assertEqual([], state.feed(menu))
        self.assertEqual(menu, state.pending)
        with self.assertRaises(driver.bootstrap.Refused):
            state.feed(b"\n==> ")

    def test_shared_chunks_consume_approvals_without_duplicates(self):
        state = parser()
        data = (state.marker + "\n" + driver.DOWNLOAD_PHASE + "\n" +
                driver.bootstrap.PROMPTS[0] + "\ny\n==> Entering fakeroot environment...\n" +
                driver.INSTALL_PHASE + "\n" + driver.bootstrap.PROMPTS[1] + "\ny\n" +
                driver.HELPER_PHASE + "\n" + driver.PARU_PROMPT + "\ny\n" +
                driver.bootstrap.PROMPTS[1] + "\ny\n==> Skipping source retrieval...\n").encode()
        for split in range(len(data) + 1):
            with self.subTest(split=split):
                state = parser()
                answers = state.feed(data[:split]) + state.feed(data[split:])
                self.assertEqual([b"y\n"] * 4, answers)
                self.assertEqual((1, 2, True), (state.downloads, state.installs, state.paru_approved))
                self.assertEqual([], state.feed(b""))

    def test_unapproved_interactive_questions_and_menus(self):
        for prompt in (":: Replace old with new? [Y/n]", ":: Import PGP key? [Y/n]",
                       ":: Enter a selection (default=all):", "==> Packages to cleanBuild?",
                       "==> Diffs to show?", ":: Proceed to review? [Y/n]",
                       "==> [N]one [A]ll [Ab]ort [I]nstalled [No]tInstalled\n",
                       "[sudo] password for guest:", "Choose a provider:"):
            state = parser()
            with self.subTest(prompt=prompt), self.assertRaises(driver.bootstrap.Refused):
                state.feed(prompt.encode())
            self.assertEqual((0, 0, False), (state.downloads, state.installs, state.paru_approved))

    def test_aur_phase_locks_all_approvals_even_exact_native_prompt(self):
        for prompt in (*driver.bootstrap.PROMPTS, driver.PARU_PROMPT, ":: Proceed to review? [Y/n]"):
            state = parser()
            native_finished(state)
            state.feed((driver.HELPER_PHASE + "\n" + driver.AUR_PHASE + "\n").encode())
            with self.assertRaises(driver.bootstrap.Refused):
                state.feed(prompt.encode())
            self.assertTrue(state.stopped_at_review)

    def test_output_bound_including_incomplete_ansi(self):
        state = parser()
        with self.assertRaises(driver.bootstrap.Refused):
            state.feed(b"\x1b]" + b"x" * 131072)

    def test_ssh_wrapper_and_guest_guards(self):
        command = driver.ssh_command(COMMIT, RECIPE)
        self.assertEqual(driver.bootstrap.ssh_command()[:-1], command[:-1])
        remote = shlex.split(command[-1])
        self.assertEqual(["bash", "--noprofile", "--norc", "-c"], remote[:-1])
        script = remote[-1]
        for phrase in (COMMIT, RECIPE, "--untracked-files=all --ignored=matching",
                       "[ ! -L", "realpath -e", "rev-parse --verify HEAD", "--error-unmatch",
                       "core.fsmonitor=false", "sha256sum -- modules/paru-recipe/PKGBUILD",
                       "exec bash --noprofile --norc bin/dotfiles install --groups core"):
            self.assertIn(phrase, script)
        self.assertLess(script.index("sha256sum"), script.index("exec bash"))
        self.assertNotIn("git reset", script)
        self.assertNotIn("git clean", script)
        bash = shutil.which("bash")
        self.assertIsNotNone(bash)
        checked = subprocess.run([bash, "--noprofile", "--norc", "-n"], input=script,
                                 text=True, capture_output=True, timeout=5,
                                 env=driver.bootstrap.environment())
        self.assertEqual(0, checked.returncode, checked.stderr)

    def test_invalid_home_no_subprocess(self):
        with patch.dict(driver.os.environ, {"LIMA_HOME": "/unsafe"}), \
                patch.object(driver.sys, "argv", ["run-install.py", "--commit", COMMIT, "--recipe-sha256", RECIPE]), \
                patch.object(driver.subprocess, "run") as run, \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(1, driver.main())
        run.assert_not_called()

    def test_main_fake_metadata_shared_runner_and_status(self):
        base = driver.bootstrap
        row = {"name": base.INSTANCE, "dir": str(base.VM_DIR), "vmType": "qemu",
               "arch": "x86_64", "status": "Running", "sshLocalPort": 60022,
               "sshAddress": "127.0.0.1", "sshConfigFile": str(base.SSH_CONFIG),
               "config": {"plain": True, "vmType": "qemu", "arch": "x86_64",
                          "ssh": {"localPort": 60022, "loadDotSSHPubKeys": False, "forwardAgent": False}}}
        for status, verified, expected in ((43, True, 43), (-2, True, 130), (0, False, 1)):
            def fake_runner(command, env, state):
                if verified:
                    state.feed((state.marker + "\n").encode())
                return status
            with patch.dict(driver.os.environ, {"LIMA_HOME": str(base.VM_HOME)}), \
                    patch.object(driver.sys, "argv", ["run-install.py", "--commit", COMMIT, "--recipe-sha256", RECIPE]), \
                    patch.object(Path, "resolve", autospec=True, side_effect=lambda path: path), \
                    patch.object(driver.subprocess, "run", return_value=SimpleNamespace(stdout=json.dumps(row))) as run, \
                    patch.object(base, "run_pty", side_effect=fake_runner), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(expected, driver.main())
            self.assertEqual(["limactl", "list", "--json", base.INSTANCE], run.call_args.args[0])

    def test_shared_pty_dummy_child_output_and_exit_status(self):
        state = parser()
        script = (
            "import signal,sys; signal.alarm(5); "
            f"print({state.marker!r}, flush=True); print({driver.DOWNLOAD_PHASE!r}, flush=True); "
            "print('Downloading https://example.invalid/pkg?mirror=1', flush=True); "
            f"print({driver.bootstrap.PROMPTS[0]!r}, end=' ', flush=True); "
            "assert input() == 'y'; "
            f"print({driver.INSTALL_PHASE!r}, flush=True); "
            f"print({driver.bootstrap.PROMPTS[1]!r}, end=' ', flush=True); "
            "assert input() == 'y'; print('dummy complete', flush=True); sys.exit(43)"
        )
        output = io.BytesIO()
        with patch.object(driver.bootstrap.sys, "stdout", SimpleNamespace(buffer=output)):
            status = driver.bootstrap.run_pty([driver.sys.executable, "-B", "-c", script],
                                              driver.bootstrap.environment(), state)
        self.assertEqual(43, status)
        self.assertIn(b"pkg?mirror=1", output.getvalue())
        self.assertIn(b"dummy complete", output.getvalue())

    def test_shared_pty_closes_only_dummy_child_at_aur_review(self):
        state = parser()
        ready(state, driver.HELPER_PHASE)
        script = ("import signal,sys; signal.alarm(5); "
                  f"print({driver.AUR_PHASE!r}, flush=True); "
                  "print(':: Proceed to review? [Y/n]', end=' ', flush=True); input()")
        output = io.BytesIO()
        with patch.object(driver.bootstrap.sys, "stdout", SimpleNamespace(buffer=output)), \
                contextlib.redirect_stderr(io.StringIO()), self.assertRaises(driver.bootstrap.Refused):
            driver.bootstrap.run_pty([driver.sys.executable, "-B", "-c", script],
                                     driver.bootstrap.environment(), state)
        self.assertTrue(state.stopped_at_review)
        self.assertEqual(0, state.installs)


if __name__ == "__main__":
    unittest.main()
