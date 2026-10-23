"""Offline reviewed-AUR driver tests; no VM, package, or SSH execution."""
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

spec = importlib.util.spec_from_file_location("vm_vscodium", Path(__file__).parent / "vm/run-vscodium.py")
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


def ready():
    state = driver.ReviewedParser()
    state.feed((driver.MARKER + "\nRepo (2) nspr-4.38-1 nss-3.120-1\n"
                "Pkgbuilds (1) vscodium-bin-1.110.0-1\n").encode())
    return state


class VSCodiumDriver(unittest.TestCase):
    def test_only_two_fixed_audited_snapshots_and_brave_pins(self):
        self.assertEqual({"vscodium", "brave"}, set(driver.SNAPSHOTS))
        snapshot = driver.snapshot_config("brave")
        self.assertEqual("8ede66185c519130ac3bfb423be40acbec7f8c12", snapshot["commit"])
        self.assertEqual("f5e4ad59b48b0965fe285fb762a2e554115e210486a953eeec997ef785a84c6c", snapshot["recipe"])
        self.assertEqual("8a08822ca82528b30c6f553988ec7214e6999ef362f6eff148d386f0053f903c", snapshot["archive"])
        self.assertEqual("1:1.97.57-1", snapshot["version"])
        self.assertEqual({"alsa-lib", "gtk3", "libxss", "nss", "noto-fonts"}, snapshot["deps"])
        self.assertEqual(driver.MARKER, driver.reviewed_marker())
        self.assertEqual(driver.remote_script(), driver.remote_script("vscodium"))
        for invalid in ("brave-bin", "spotify", "brave;id", "$(id)", "brave\n", "", None, []):
            with self.subTest(invalid=invalid):
                with self.assertRaises(driver.argparse.ArgumentTypeError):
                    driver.remote_script(invalid)
                with self.assertRaises(driver.argparse.ArgumentTypeError):
                    driver.ReviewedParser(invalid)

    def test_brave_requires_brave_marker_and_exact_version_not_vscodium(self):
        for marker, plan in ((driver.MARKER, "brave-bin-1:1.97.57-1"),
                             (driver.reviewed_marker("brave"), "vscodium-bin-1.110.0-1"),
                             (driver.reviewed_marker("brave"), "brave-bin-1:1.97.58-1"),
                             (driver.reviewed_marker("brave"), "brave-bin-1.97.57-1")):
            state = driver.ReviewedParser("brave")
            with self.assertRaises(driver.bootstrap.Refused):
                state.feed((marker + "\nPkgbuilds (1) " + plan + "\n" + driver.PROMPTS[1]).encode())
            self.assertEqual([0, 0, 0], state.counts)
        state = driver.ReviewedParser()
        with self.assertRaises(driver.bootstrap.Refused):
            state.feed((driver.MARKER + "\nPkgbuilds (1) brave-bin-1:1.97.57-1\n").encode())

    def test_brave_plan_only_no_new_dependencies_all_prompt_boundaries(self):
        for index, prompt in enumerate(driver.PROMPTS):
            data = ("\x1b[1m" + prompt + "\x1b[0m ").encode()
            for split in range(len(data) + 1):
                state = driver.ReviewedParser("brave")
                state.feed((state.marker + "\nPkgbuilds (1) brave-bin-1:1.97.57-1\n").encode())
                if index == 2:
                    state.feed(b"Packages (1) brave-bin-1:1.97.57-1\n")
                self.assertEqual([b"y\n"], state.feed(data[:split]) + state.feed(data[split:]))
                self.assertEqual(1, state.counts[index])
                self.assertEqual([], state.feed(b"\r\ny\r\n"))

    def test_brave_allowlisted_native_dependencies_caps_and_unknown_prompts(self):
        state = driver.ReviewedParser("brave")
        native = " ".join(name + "-1.0-1" for name in sorted(driver.snapshot_config("brave")["deps"]))
        state.feed((state.marker + f"\nRepo (5) {native}\nPkgbuilds (1) brave-bin-1:1.97.57-1\n").encode())
        self.assertEqual([b"y\n"], state.feed((driver.PROMPTS[1] + " \n").encode()))
        for packages in ((5, native), (1, "brave-bin-1:1.97.57-1")):
            state.feed((f"Packages ({packages[0]}) {packages[1]}\n").encode())
            self.assertEqual([b"y\n"], state.feed((driver.PROMPTS[2] + " \n").encode()))
        state.feed(b"Packages (1) brave-bin-1:1.97.57-1\n")
        with self.assertRaises(driver.bootstrap.Refused):
            state.feed((driver.PROMPTS[2] + " ").encode())
        for text in ("Repo (1) unknown-1.0-1\n", "Aur (1) brave-bin-1:1.97.57-1\n",
                     "Packages (1) paru-2.1.0-1\n", ":: Enter a selection:", ":: Import PGP key? [Y/n]"):
            state = driver.ReviewedParser("brave")
            state.feed((state.marker + "\nPkgbuilds (1) brave-bin-1:1.97.57-1\n").encode())
            with self.assertRaises(driver.bootstrap.Refused):
                state.feed(text.encode())
            self.assertEqual([0, 0, 0], state.counts)

    def test_approval_flags_are_exclusive_and_no_arbitrary_package_cli(self):
        for args in (["--approve-reviewed-brave", "--approve-reviewed-vscodium"],
                     ["--package", "brave"], ["--approve-reviewed-brave=false"],
                     ["--approve-reviewed-spotify"]):
            with patch.object(driver.sys, "argv", ["run-vscodium.py", *args]), \
                    patch.object(driver.subprocess, "run") as run, \
                    contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                driver.main()
            self.assertEqual(2, caught.exception.code)
            run.assert_not_called()

    def test_both_cli_approvals_select_matching_script_parser_and_preserve_status(self):
        base = driver.bootstrap
        row = {"name": base.INSTANCE, "dir": str(base.VM_DIR), "vmType": "qemu", "arch": "x86_64",
               "status": "Running", "sshLocalPort": 60022, "sshAddress": "127.0.0.1",
               "sshConfigFile": str(base.SSH_CONFIG), "config": {"plain": True, "vmType": "qemu",
               "arch": "x86_64", "ssh": {"localPort": 60022, "loadDotSSHPubKeys": False, "forwardAgent": False}}}
        for name in ("vscodium", "brave"):
            def fake_pty(command, env, parser):
                self.assertEqual(base.ssh_command()[:-1], command[:-1])
                self.assertEqual(driver.remote_script(name), shlex.split(command[-1])[-1])
                self.assertEqual(driver.reviewed_marker(name), parser.marker)
                parser.feed((parser.marker + "\n").encode())
                return 43
            with patch.object(driver.sys, "argv", ["run-vscodium.py", "--approve-reviewed-" + name]), \
                    patch.dict(driver.os.environ, {"LIMA_HOME": str(base.VM_HOME)}), \
                    patch.object(Path, "resolve", autospec=True, side_effect=lambda path: path), \
                    patch.object(driver.subprocess, "run", return_value=SimpleNamespace(stdout=json.dumps(row))), \
                    patch.object(base, "run_pty", side_effect=fake_pty), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(43, driver.main())

    def test_brave_guest_script_checks_all_pins_and_local_path_shell_syntax(self):
        script = driver.remote_script("brave")
        snapshot = driver.snapshot_config("brave")
        for text in (snapshot["commit"], snapshot["recipe"], snapshot["archive"],
                     "for component in aur-review brave-bin", "https://aur.archlinux.org/brave-bin.git",
                     "--untracked-files=all --ignored=matching", "'^filter\\.'", "[ ! -L",
                     "pacman -Qqo /usr/bin/paru", "PARU_CONF=/dev/null", "PARU_PAGER=/usr/bin/cat",
                     "exec /usr/bin/paru --build --install --needed --color never --", driver.reviewed_marker("brave")):
            self.assertIn(text, script)
        for text in ("vscodium-bin", "--pager", "--skipreview", "--noconfirm", "git pull", "eval "):
            self.assertNotIn(text, script)
        self.assertLess(script.index("sha256sum"), script.index("exec /usr/bin/paru"))
        checked = subprocess.run([shutil.which("bash"), "--noprofile", "--norc", "-n"], input=script,
                                 text=True, capture_output=True, env=driver.bootstrap.environment(), timeout=5)
        self.assertEqual(0, checked.returncode, checked.stderr)

    def test_explicit_approval_required_before_any_subprocess(self):
        with patch.object(driver.sys, "argv", ["run-vscodium.py"]), \
                patch.object(driver.subprocess, "run") as run, \
                contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            driver.main()
        self.assertEqual(2, caught.exception.code)
        run.assert_not_called()

    def test_wrong_home_fails_before_any_subprocess(self):
        with patch.dict(driver.os.environ, {"LIMA_HOME": "/unsafe"}), \
                patch.object(driver.sys, "argv", ["run-vscodium.py", "--approve-reviewed-vscodium"]), \
                patch.object(driver.subprocess, "run") as run, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(1, driver.main())
        run.assert_not_called()

    def test_unverified_or_missing_pkgbuild_plan_never_approved(self):
        for prefix in ("", driver.MARKER + "\n", driver.MARKER + "\nRepo (1) nss-3.120-1\n"):
            state = driver.ReviewedParser()
            state.feed(prefix.encode())
            with self.assertRaises(driver.bootstrap.Refused):
                state.feed(driver.PROMPTS[1].encode())
            self.assertEqual([0, 0, 0], state.counts)

    def test_paru_prompts_once_each_and_local_build_without_review_prompt(self):
        for review in (False, True):
            state = ready()
            if review:
                self.assertEqual([b"y\n"], state.feed((driver.PROMPTS[0] + "\n").encode()))
            self.assertEqual([b"y\n"], state.feed(driver.PROMPTS[1].encode()))
            with self.assertRaises(driver.bootstrap.Refused):
                state.feed(("\n" + driver.PROMPTS[1]).encode())
            self.assertEqual([int(review), 1, 0], state.counts)

    def test_review_repeat_or_after_installation_refused(self):
        for prior in (driver.PROMPTS[0], driver.PROMPTS[1]):
            state = ready()
            state.feed((prior + "\n").encode())
            with self.assertRaises(driver.bootstrap.Refused):
                state.feed(driver.PROMPTS[0].encode())

    def test_pacman_two_confirmations_with_fresh_allowlisted_plans(self):
        state = ready()
        for packages in ("nss-3.120-1 nspr-4.38-1", "vscodium-bin-1.110.0-1"):
            state.feed((f"Packages ({len(packages.split())}) {packages}\n").encode())
            self.assertEqual([b"y\n"], state.feed((driver.PROMPTS[2] + " ").encode()))
            state.feed(b"\ny\n")
        state.feed(b"Packages (1) vscodium-bin-1.110.0-1\n")
        with self.assertRaises(driver.bootstrap.Refused):
            state.feed((driver.PROMPTS[2] + " ").encode())
        self.assertEqual(2, state.counts[2])

    def test_pacman_requires_new_package_plan_each_time(self):
        state = ready()
        with self.assertRaises(driver.bootstrap.Refused):
            state.feed((driver.PROMPTS[2] + " ").encode())
        state = ready()
        state.feed(b"Packages (1) nss-3.120-1\n")
        state.feed((driver.PROMPTS[2] + " \n").encode())
        with self.assertRaises(driver.bootstrap.Refused):
            state.feed((driver.PROMPTS[2] + " ").encode())

    def test_colon_suffix_disambiguates_paru_from_pacman(self):
        state = ready()
        self.assertEqual([], state.feed(driver.PROMPTS[2].encode()))
        self.assertEqual([b"y\n"], state.feed(b": "))
        self.assertEqual([0, 1, 0], state.counts)
        state = ready()
        state.feed(b"Packages (1) nss-3.120-1\n")
        self.assertEqual([], state.feed(driver.PROMPTS[2].encode()))
        self.assertEqual([b"y\n"], state.feed(b" "))
        self.assertEqual([0, 0, 1], state.counts)

    def test_exact_seven_native_dependencies_accepted(self):
        state = driver.ReviewedParser()
        packages = " ".join(name + "-1.0-1" for name in sorted(driver.DEPS))
        state.feed((driver.MARKER + f"\nRepo (7) {packages}\nPkgbuilds (1) vscodium-bin-1.0-1\n").encode())
        self.assertEqual([b"y\n"], state.feed(driver.PROMPTS[1].encode()))

    def test_unapproved_targets_make_dependencies_and_aur_refused(self):
        for text in ("Repo (1) unexpected-1.0-1", "Aur (1) vscodium-bin-1.110.0-1",
                     "Repo Make (1) rust-1.0-1", "Pkgbuilds Make (1) tool-1.0-1",
                     "Pkgbuilds (1) codium-1.0-1", "Pkgbuilds (2) vscodium-bin-1.0-1 extra-1.0-1",
                     "Packages (1) paru-2.1.0-1", "Packages (1) vscodium-bin-debug-1.0-1",
                     "Repo (2) nss-1.0-1 nss-1.0-1"):
            state = ready()
            with self.subTest(text=text), self.assertRaises(driver.bootstrap.Refused):
                state.feed((text + "\n").encode())

    def test_incomplete_wrapped_plan_cannot_approve_until_finished(self):
        state = driver.ReviewedParser()
        state.feed((driver.MARKER + "\nRepo (2) nspr-4.38-1\n").encode())
        with self.assertRaises(driver.bootstrap.Refused):
            state.feed(driver.PROMPTS[1].encode())
        state = driver.ReviewedParser()
        state.feed((driver.MARKER + "\nRepo (2) nspr-4.38-1\n        nss-3.120-1\n"
                    "Pkgbuilds (1) vscodium-bin-1.110.0-1\n").encode())
        self.assertEqual([b"y\n"], state.feed(driver.PROMPTS[1].encode()))

    def test_all_prompt_byte_boundaries_and_ansi(self):
        for index, prompt in enumerate(driver.PROMPTS):
            data = ("\x1b[1m" + prompt + "\x1b[0m ").encode()
            for split in range(len(data) + 1):
                with self.subTest(prompt=prompt, split=split):
                    state = ready()
                    if index == 2:
                        state.feed(b"Packages (1) vscodium-bin-1.110.0-1\n")
                    answers = state.feed(data[:split]) + state.feed(data[split:])
                    self.assertEqual([b"y\n"], answers)
                    self.assertEqual([], state.feed(b"\ny\n"))
                    self.assertEqual(1, state.counts[index])

    def test_plan_and_prompt_shared_chunks_all_boundaries(self):
        data = (driver.MARKER + "\nRepo (1) nss-3.120-1\nPkgbuilds (1) vscodium-bin-1.110.0-1\n" +
                driver.PROMPTS[1] + " \ny\nPackages (1) vscodium-bin-1.110.0-1\n" +
                driver.PROMPTS[2] + " \ny\n").encode()
        for split in range(len(data) + 1):
            state = driver.ReviewedParser()
            self.assertEqual([b"y\n", b"y\n"], state.feed(data[:split]) + state.feed(data[split:]))
            self.assertEqual([0, 1, 1], state.counts)

    def test_ordinary_build_output_all_byte_boundaries(self):
        for text in ("==> Entering fakeroot environment...\n", "==> Skipping source retrieval...\n",
                     "==> Downloading https://example.invalid/file?query=1\n", "# Build thing? [y/N]\n"):
            data = text.encode()
            for split in range(len(data) + 1):
                state = ready()
                self.assertEqual([], state.feed(data[:split]) + state.feed(data[split:]))

    def test_unexpected_prompts_refused_all_boundaries(self):
        for prompt in (":: Import PGP key? [Y/n]", ":: Replace package? [Y/n]",
                       ":: Enter a selection:", "==> Diffs to show?", "[sudo] password for guest:"):
            data = prompt.encode()
            for split in range(len(data) + 1):
                state = ready()
                with self.assertRaises(driver.bootstrap.Refused):
                    state.feed(data[:split])
                    state.feed(data[split:])
                self.assertEqual([0, 0, 0], state.counts)

    def test_unbounded_output_refused(self):
        with self.assertRaises(driver.bootstrap.Refused):
            ready().feed(b"\x1b]" + b"x" * 131072)

    def test_guest_script_pins_local_build_pager_and_safety_syntax(self):
        script = driver.remote_script()
        for text in (driver.COMMIT, driver.RECIPE, driver.ARCHIVE, "https://aur.archlinux.org/vscodium-bin.git",
                     "--untracked-files=all --ignored=matching", "sha256sum -- PKGBUILD", "'^filter\\.'",
                     "pacman -Qqo /usr/bin/paru", "paru v2.1.0", "PARU_CONF=/dev/null",
                     "PARU_PAGER=/usr/bin/cat", "--build --install --needed", '-- "$root"'):
            self.assertIn(text, script)
        # This pinned Paru release cannot parse a value for its --pager option.
        for text in ("--pager", "--skipreview", "--noconfirm", "paru -S", "git pull", "git checkout", "eval "):
            self.assertNotIn(text, script)
        self.assertLess(script.index("sha256sum"), script.index("exec /usr/bin/paru"))
        remote = "bash --noprofile --norc -c " + shlex.quote(script)
        self.assertEqual(script, shlex.split(remote)[-1])
        bash = shutil.which("bash")
        self.assertIsNotNone(bash)
        checked = subprocess.run([bash, "--noprofile", "--norc", "-n"], input=script, text=True,
                                 capture_output=True, env=driver.bootstrap.environment(), timeout=5)
        self.assertEqual(0, checked.returncode, checked.stderr)


if __name__ == "__main__":
    unittest.main()
