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


PROVIDER_MENU = (":: There are 5 providers available for org.freedesktop.secrets:\n"
                 ":: Repository extra\n"
                 "   1) chipass  2) gnome-keyring  3) keepassxc  4) kwallet  5) oo7\n\n")
JACK_MENU = (":: There are 2 providers available for jack:\n"
             ":: Repository extra\n   1) jack2  2) pipewire-jack\n\n")
FONT_MENU = (":: There are 11 providers available for ttf-font:\n:: Repository extra\n"
             "   1) gnu-free-fonts  2) noto-fonts  3) ttf-bitstream-vera  4) ttf-croscore\n"
             "   5) ttf-dejavu  6) ttf-droid  7) ttf-ibm-plex  8) ttf-input\n"
             "   9) ttf-input-nerd  10) ttf-liberation  11) ttf-roboto\n\n")


class InstallDriver(unittest.TestCase):
    def test_three_independent_menus_and_multidigit_font_index_all_boundaries(self):
        for menu, answer in ((FONT_MENU, b"2\n"),
                             (FONT_MENU.replace("2) noto-fonts", "2) ttf-liberation")
                                       .replace("10) ttf-liberation", "10) noto-fonts"), b"10\n")):
            data = (PROVIDER_MENU + driver.PROVIDER_PROMPT + "\r\n2\r\n" +
                    JACK_MENU + driver.PROVIDER_PROMPT + "\r\n2\r\n" + menu +
                    "\x1b[1m" + driver.PROVIDER_PROMPT + "\x1b[0m ").encode()
            for split in range(len(data) + 1):
                with self.subTest(answer=answer, split=split):
                    state = driver.InstallParser(COMMIT, RECIPE, "gnome-keyring", "pipewire-jack", "noto-fonts")
                    ready(state, driver.INSTALL_PHASE)
                    self.assertEqual([b"2\n", b"2\n", answer], state.feed(data[:split]) + state.feed(data[split:]))
                    self.assertEqual({"org.freedesktop.secrets", "jack", "ttf-font"}, state.approved_providers)
                    self.assertEqual((0, 0), (state.downloads, state.installs))
                    self.assertEqual([], state.feed(b"\r\n2\r\n"))
                    self.assertEqual([b"y\n"], state.feed(driver.bootstrap.PROMPTS[1].encode()))
                    with self.assertRaises(driver.bootstrap.Refused):
                        state.feed(("\n" + driver.bootstrap.PROMPTS[1]).encode())

    def test_font_requires_its_flag_and_does_not_approve_other_namespaces(self):
        for font, menu in ((None, FONT_MENU), ("noto-fonts", JACK_MENU),
                           ("noto-fonts", FONT_MENU.replace("ttf-font:", "pipewire-session-manager:"))):
            state = driver.InstallParser(COMMIT, RECIPE, font_provider=font)
            ready(state, driver.INSTALL_PHASE)
            with self.assertRaises(driver.bootstrap.Refused):
                state.feed((menu + driver.PROVIDER_PROMPT).encode())
            self.assertEqual(set(), state.approved_providers)

    def test_font_invalid_counts_noncontiguous_duplicate_and_missing_options_refuse(self):
        for menu in (FONT_MENU.replace("11 providers", "12 providers"),
                     FONT_MENU.replace("11 providers", "0 providers"),
                     FONT_MENU.replace("11 providers", "10 providers"),
                     FONT_MENU.replace("11) ttf-roboto", "12) ttf-roboto"),
                     FONT_MENU.replace("10) ttf-liberation", "9) ttf-liberation"),
                     FONT_MENU.replace("10) ttf-liberation", "010) ttf-liberation"),
                     FONT_MENU.replace("  10) ttf-liberation", ""),
                     FONT_MENU.replace("noto-fonts", "another-font"),
                     FONT_MENU.replace("ttf-roboto", "noto-fonts"),
                     FONT_MENU.replace("noto-fonts", "noto-fonts;id")):
            state = driver.InstallParser(COMMIT, RECIPE, font_provider="noto-fonts")
            ready(state, driver.INSTALL_PHASE)
            with self.subTest(menu=menu), self.assertRaises(driver.bootstrap.Refused):
                state.feed((menu + driver.PROVIDER_PROMPT).encode())
            self.assertEqual(set(), state.approved_providers)

    def test_font_repeat_phase_and_aur_restrictions(self):
        for phase in (None, driver.DOWNLOAD_PHASE, driver.HELPER_PHASE, driver.AUR_PHASE, driver.AUR_UPDATE_PHASE):
            state = driver.InstallParser(COMMIT, RECIPE, font_provider="noto-fonts")
            if phase in (driver.AUR_PHASE, driver.AUR_UPDATE_PHASE):
                ready(state, driver.HELPER_PHASE)
                state.feed((phase + "\n").encode())
            elif phase is not None:
                ready(state, phase)
            with self.assertRaises(driver.bootstrap.Refused):
                state.feed((FONT_MENU + driver.PROVIDER_PROMPT).encode())
        for repeated in (driver.PROVIDER_PROMPT, FONT_MENU + driver.PROVIDER_PROMPT):
            state = driver.InstallParser(COMMIT, RECIPE, font_provider="noto-fonts")
            ready(state, driver.INSTALL_PHASE)
            state.feed((FONT_MENU + driver.PROVIDER_PROMPT + "\n").encode())
            with self.assertRaises(driver.bootstrap.Refused):
                state.feed(repeated.encode())
            self.assertEqual({"ttf-font"}, state.approved_providers)

    def test_font_cli_only_accepts_explicit_noto_fonts(self):
        for value in ("", "true", "false", "2", "ttf-dejavu", "noto-fonts;id", "noto-fonts "):
            with patch.object(driver.sys, "argv", ["run-install.py", "--commit", COMMIT,
                                                   "--recipe-sha256", RECIPE, "--font-provider=" + value]), \
                    patch.object(driver.subprocess, "run") as run, \
                    contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                driver.main()
            self.assertEqual(2, caught.exception.code)
            run.assert_not_called()
        for value in (True, False, "ttf-dejavu", "noto-fonts;id"):
            with self.assertRaises(driver.argparse.ArgumentTypeError):
                driver.InstallParser(COMMIT, RECIPE, font_provider=value)
        with patch.object(driver.sys, "argv", ["run-install.py", "--commit", COMMIT,
                                               "--recipe-sha256", RECIPE, "--font-provider", "noto-fonts"]), \
                patch.object(driver, "InstallParser", wraps=driver.InstallParser) as constructor, \
                patch.dict(driver.os.environ, {"LIMA_HOME": "/unsafe"}), \
                patch.object(driver.subprocess, "run") as run, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(1, driver.main())
        constructor.assert_called_once_with(COMMIT, RECIPE, None, None, "noto-fonts")
        run.assert_not_called()

    def test_independent_provider_choices_sequential_menus_and_native_cap(self):
        for jack_menu, expected in ((JACK_MENU, b"2\n"),
                                   (JACK_MENU.replace("1) jack2  2) pipewire-jack",
                                                      "1) pipewire-jack  2) jack2"), b"1\n")):
            for jack_first in (False, True):
                with self.subTest(expected=expected, jack_first=jack_first):
                    state = driver.InstallParser(COMMIT, RECIPE, "gnome-keyring", "pipewire-jack")
                    ready(state, driver.INSTALL_PHASE)
                    menus = [(PROVIDER_MENU, b"2\n"), (jack_menu, expected)]
                    for menu, answer in reversed(menus) if jack_first else menus:
                        self.assertEqual([answer], state.feed((menu + driver.PROVIDER_PROMPT + " \ny\n").encode()))
                    self.assertEqual({"jack", "org.freedesktop.secrets"}, state.approved_providers)
                    self.assertEqual((0, 0), (state.downloads, state.installs))
                    self.assertEqual([b"y\n"], state.feed(driver.bootstrap.PROMPTS[1].encode()))
                    with self.assertRaises(driver.bootstrap.Refused):
                        state.feed(("\n" + driver.bootstrap.PROMPTS[1]).encode())
                    self.assertEqual(1, state.installs)

    def test_two_provider_menus_all_byte_boundaries(self):
        data = (PROVIDER_MENU + driver.PROVIDER_PROMPT + " \r\n2\r\n" +
                JACK_MENU.replace("\n", "\r\n") + "\x1b[1m" + driver.PROVIDER_PROMPT + "\x1b[0m ").encode()
        for split in range(len(data) + 1):
            with self.subTest(split=split):
                state = driver.InstallParser(COMMIT, RECIPE, "gnome-keyring", "pipewire-jack")
                ready(state, driver.INSTALL_PHASE)
                self.assertEqual([b"2\n", b"2\n"], state.feed(data[:split]) + state.feed(data[split:]))
                self.assertEqual([], state.feed(b"\r\n2\r\n"))
                self.assertEqual({"jack", "org.freedesktop.secrets"}, state.approved_providers)

    def test_provider_flags_do_not_authorize_each_other_or_unknown_namespace(self):
        state = driver.InstallParser(COMMIT, RECIPE, "gnome-keyring")
        ready(state, driver.INSTALL_PHASE)
        state.feed((PROVIDER_MENU + driver.PROVIDER_PROMPT + "\n").encode())
        with self.assertRaises(driver.bootstrap.Refused):
            state.feed((JACK_MENU + driver.PROVIDER_PROMPT).encode())
        for secret, jack, menu in ((None, None, JACK_MENU), (None, "pipewire-jack", PROVIDER_MENU),
                                   ("gnome-keyring", "pipewire-jack", JACK_MENU.replace("for jack:", "for pipewire-session-manager:"))):
            state = driver.InstallParser(COMMIT, RECIPE, secret, jack)
            ready(state, driver.INSTALL_PHASE)
            with self.assertRaises(driver.bootstrap.Refused):
                state.feed((menu + driver.PROVIDER_PROMPT).encode())
            self.assertEqual(set(), state.approved_providers)

    def test_jack_malformed_missing_or_duplicate_options_refuse(self):
        for menu in (JACK_MENU.replace("pipewire-jack", "gnome-keyring"),
                     JACK_MENU.replace("2) pipewire-jack", "1) pipewire-jack"),
                     JACK_MENU.replace("1) jack2", "1) pipewire-jack"),
                     JACK_MENU.replace("pipewire-jack", "pipewire-jack;id"),
                     JACK_MENU.replace("2 providers", "3 providers"),
                     JACK_MENU.replace("for jack:", "for jack;id:"),
                     JACK_MENU.replace("  2) pipewire-jack", "")):
            state = driver.InstallParser(COMMIT, RECIPE, jack_provider="pipewire-jack")
            ready(state, driver.INSTALL_PHASE)
            with self.subTest(menu=menu), self.assertRaises(driver.bootstrap.Refused):
                state.feed((menu + driver.PROVIDER_PROMPT).encode())
            self.assertEqual(set(), state.approved_providers)

    def test_jack_repeated_menu_or_prompt_refuses_even_after_other_provider(self):
        for other_menu in (False, True):
            for repeat in (driver.PROVIDER_PROMPT, JACK_MENU + driver.PROVIDER_PROMPT):
                state = driver.InstallParser(COMMIT, RECIPE, "gnome-keyring", "pipewire-jack")
                ready(state, driver.INSTALL_PHASE)
                state.feed((JACK_MENU + driver.PROVIDER_PROMPT + "\n").encode())
                if other_menu:
                    state.feed((PROVIDER_MENU + driver.PROVIDER_PROMPT + "\n").encode())
                with self.assertRaises(driver.bootstrap.Refused):
                    state.feed(repeat.encode())
                self.assertEqual(0, state.installs)

    def test_jack_requires_verified_native_install_scope(self):
        for phase in (None, driver.DOWNLOAD_PHASE, driver.HELPER_PHASE, driver.AUR_PHASE, driver.AUR_UPDATE_PHASE):
            state = driver.InstallParser(COMMIT, RECIPE, "gnome-keyring", "pipewire-jack")
            if phase in (driver.AUR_PHASE, driver.AUR_UPDATE_PHASE):
                ready(state, driver.HELPER_PHASE)
                state.feed((phase + "\n").encode())
            elif phase is not None:
                ready(state, phase)
            with self.subTest(phase=phase), self.assertRaises(driver.bootstrap.Refused):
                state.feed((JACK_MENU + driver.PROVIDER_PROMPT).encode())
            self.assertEqual(set(), state.approved_providers)

    def test_jack_cli_rejects_other_choices_and_wires_explicit_opt_in(self):
        for value in ("", "true", "false", "2", "jack2", "pipewire-session-manager", "pipewire-jack;id", "pipewire-jack "):
            with self.subTest(value=value), \
                    patch.object(driver.sys, "argv", ["run-install.py", "--commit", COMMIT,
                                                       "--recipe-sha256", RECIPE, "--jack-provider=" + value]), \
                    patch.object(driver.subprocess, "run") as run, \
                    contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                driver.main()
            self.assertEqual(2, caught.exception.code)
            run.assert_not_called()
        for value in (True, False, "jack2", "pipewire-jack;id"):
            with self.assertRaises(driver.argparse.ArgumentTypeError):
                driver.InstallParser(COMMIT, RECIPE, jack_provider=value)
        with patch.object(driver.sys, "argv", ["run-install.py", "--commit", COMMIT,
                                               "--recipe-sha256", RECIPE, "--secret-service-provider", "gnome-keyring",
                                               "--jack-provider", "pipewire-jack"]), \
                patch.object(driver, "InstallParser", wraps=driver.InstallParser) as constructor, \
                patch.dict(driver.os.environ, {"LIMA_HOME": "/unsafe"}), \
                patch.object(driver.subprocess, "run") as run, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(1, driver.main())
        constructor.assert_called_once_with(COMMIT, RECIPE, "gnome-keyring", "pipewire-jack", None)
        run.assert_not_called()

    def test_provider_default_refuses_and_opt_in_maps_displayed_index(self):
        state = parser()
        ready(state, driver.INSTALL_PHASE)
        with self.assertRaises(driver.bootstrap.Refused):
            state.feed((PROVIDER_MENU + driver.PROVIDER_PROMPT).encode())
        for menu, expected in ((PROVIDER_MENU, b"2\n"),
                               (PROVIDER_MENU.replace("2) gnome-keyring  3) keepassxc",
                                                      "2) keepassxc  3) gnome-keyring"), b"3\n")):
            state = driver.InstallParser(COMMIT, RECIPE, "gnome-keyring")
            ready(state, driver.INSTALL_PHASE)
            self.assertEqual([], state.feed(menu.encode()))
            self.assertEqual([expected], state.feed(driver.PROVIDER_PROMPT.encode()))
            self.assertTrue(state.provider_approved)
            self.assertEqual((0, 0), (state.downloads, state.installs))
            self.assertEqual([b"y\n"], state.feed(("\n" + driver.bootstrap.PROMPTS[1]).encode()))
            self.assertEqual(1, state.installs)
            with self.assertRaises(driver.bootstrap.Refused):
                state.feed(("\n" + driver.bootstrap.PROMPTS[1]).encode())

    def test_provider_menu_and_prompt_all_byte_boundaries(self):
        menus = (PROVIDER_MENU, PROVIDER_MENU.replace("  2)", "\n  2)").replace("  3)", "\n  3)"))
        for menu in menus:
            data = (menu.replace("\n", "\r\n") + "\x1b[1m" + driver.PROVIDER_PROMPT + "\x1b[0m ").encode()
            for split in range(len(data) + 1):
                with self.subTest(split=split, wrapped=menu != PROVIDER_MENU):
                    state = driver.InstallParser(COMMIT, RECIPE, "gnome-keyring")
                    ready(state, driver.INSTALL_PHASE)
                    self.assertEqual([b"2\n"], state.feed(data[:split]) + state.feed(data[split:]))
                    self.assertEqual([], state.feed(b"\r\n2\r\n"))
                    self.assertEqual(0, state.installs)

    def test_provider_missing_duplicate_malformed_or_wrong_virtual_name_refuses(self):
        menus = (PROVIDER_MENU.replace("gnome-keyring", "other-provider"),
                 PROVIDER_MENU.replace("3) keepassxc", "2) keepassxc"),
                 PROVIDER_MENU.replace("keepassxc", "gnome-keyring"),
                 PROVIDER_MENU.replace("3) keepassxc", "3) keepassxc;id"),
                 PROVIDER_MENU.replace("5) oo7", "6) oo7"),
                 PROVIDER_MENU.replace("  5) oo7", ""),
                 PROVIDER_MENU.replace("org.freedesktop.secrets", "other.virtual.provider"),
                 PROVIDER_MENU.replace("There are 5", "There are 6"),
                 PROVIDER_MENU.replace("Repository extra", "Repository untrusted"),
                 PROVIDER_MENU.replace(":: Repository extra\n", ""))
        for menu in menus:
            with self.subTest(menu=menu):
                state = driver.InstallParser(COMMIT, RECIPE, "gnome-keyring")
                ready(state, driver.INSTALL_PHASE)
                with self.assertRaises(driver.bootstrap.Refused):
                    state.feed((menu + driver.PROVIDER_PROMPT).encode())
                self.assertFalse(state.provider_approved)

    def test_provider_requires_verified_install_phase_and_menu(self):
        for phase in (None, driver.DOWNLOAD_PHASE, driver.HELPER_PHASE, driver.AUR_PHASE, driver.AUR_UPDATE_PHASE):
            state = driver.InstallParser(COMMIT, RECIPE, "gnome-keyring")
            if phase in (driver.AUR_PHASE, driver.AUR_UPDATE_PHASE):
                ready(state, driver.HELPER_PHASE)
                state.feed((phase + "\n").encode())
            elif phase is not None:
                ready(state, phase)
            with self.subTest(phase=phase), self.assertRaises(driver.bootstrap.Refused):
                state.feed((PROVIDER_MENU + driver.PROVIDER_PROMPT).encode())
            self.assertFalse(state.provider_approved)
        state = driver.InstallParser(COMMIT, RECIPE, "gnome-keyring")
        ready(state, driver.INSTALL_PHASE)
        with self.assertRaises(driver.bootstrap.Refused):
            state.feed(driver.PROVIDER_PROMPT.encode())

    def test_provider_approval_once_and_no_selection_after_native_confirmation(self):
        for repeated in (driver.PROVIDER_PROMPT, PROVIDER_MENU + driver.PROVIDER_PROMPT):
            state = driver.InstallParser(COMMIT, RECIPE, "gnome-keyring")
            ready(state, driver.INSTALL_PHASE)
            self.assertEqual([b"2\n"], state.feed((PROVIDER_MENU + driver.PROVIDER_PROMPT + "\n").encode()))
            with self.assertRaises(driver.bootstrap.Refused):
                state.feed(repeated.encode())
            self.assertEqual(0, state.installs)
        state = driver.InstallParser(COMMIT, RECIPE, "gnome-keyring")
        native_finished(state)
        with self.assertRaises(driver.bootstrap.Refused):
            state.feed(PROVIDER_MENU.encode())

    def test_provider_menu_does_not_approve_or_wait_on_other_terminal_questions(self):
        for prompt in ("Enter a number (default=2):", "Choose a provider:",
                       ":: Import PGP key? [Y/n]", driver.bootstrap.PROMPTS[1]):
            state = driver.InstallParser(COMMIT, RECIPE, "gnome-keyring")
            ready(state, driver.INSTALL_PHASE)
            state.feed(PROVIDER_MENU.encode())
            with self.subTest(prompt=prompt), self.assertRaises(driver.bootstrap.Refused):
                state.feed(prompt.encode())
            self.assertFalse(state.provider_approved)
            self.assertEqual(0, state.installs)

    def test_provider_cli_only_accepts_explicit_gnome_keyring(self):
        for value in ("", "true", "false", "2", "keepassxc", "gnome-keyring;id", "gnome-keyring "):
            with self.subTest(value=value), \
                    patch.object(driver.sys, "argv", ["run-install.py", "--commit", COMMIT,
                                                       "--recipe-sha256", RECIPE, "--secret-service-provider=" + value]), \
                    patch.object(driver.subprocess, "run") as run, \
                    contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                driver.main()
            self.assertEqual(2, caught.exception.code)
            run.assert_not_called()
        for value in (True, False, "keepassxc"):
            with self.assertRaises(driver.argparse.ArgumentTypeError):
                driver.InstallParser(COMMIT, RECIPE, value)
        # A mocked metadata failure stops before SSH while exposing parsed opt-in.
        with patch.object(driver.sys, "argv", ["run-install.py", "--commit", COMMIT,
                                               "--recipe-sha256", RECIPE, "--secret-service-provider", "gnome-keyring"]), \
                patch.object(driver, "InstallParser", wraps=driver.InstallParser) as constructor, \
                patch.dict(driver.os.environ, {"LIMA_HOME": "/unsafe"}), \
                patch.object(driver.subprocess, "run") as run, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(1, driver.main())
        constructor.assert_called_once_with(COMMIT, RECIPE, "gnome-keyring", None, None)
        run.assert_not_called()

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

    def test_exact_additive_module_allowlist_and_csv_mapping(self):
        expected = {"opencode", "nono", "bitwarden", "discord", "mullvad",
                    "signal", "telegram", "thunderbird", "wallpaper"}
        self.assertEqual(expected, driver.MODULE_ALLOWLIST)
        self.assertEqual((), driver.validate_modules(()))
        for name in sorted(expected):
            self.assertEqual((name,), driver.parse_modules(name))
        self.assertEqual(("nono", "discord"), driver.parse_modules("nono,discord"))

    def test_invalid_modules_rejected_before_any_subprocess(self):
        for value in ("", ",", "discord,", ",discord", "discord,,nono", "discord,discord",
                      "discord, nono", "discord\n", "Discord", "spotify", "brave", "claude",
                      "1password", "slack", "tor", "cloud", "docker", "--groups=desktop",
                      "discord;id", "$(id)", "discord`id`", "discord.*", "discord,spotify"):
            with self.subTest(value=value):
                with self.assertRaises(driver.argparse.ArgumentTypeError):
                    driver.parse_modules(value)
                with patch.object(driver.sys, "argv", ["run-install.py", "--commit", COMMIT,
                                                       "--recipe-sha256", RECIPE, "--modules=" + value]), \
                        patch.object(driver.subprocess, "run") as run, \
                        contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                    driver.main()
                self.assertEqual(2, caught.exception.code)
                run.assert_not_called()

    def test_remote_module_contract_and_default_core_unchanged(self):
        default = driver.remote_script(COMMIT, RECIPE)
        self.assertEqual(default, driver.remote_script(COMMIT, RECIPE, ()))
        self.assertNotIn("--modules", default)
        self.assertTrue(default.endswith("exec bash --noprofile --norc bin/dotfiles install --groups core\n"))
        for invalid in ("discord", None, ("discord", "discord"), ("discord;id",), ([],)):
            with self.subTest(invalid=invalid), self.assertRaises(driver.argparse.ArgumentTypeError):
                driver.ssh_command(COMMIT, RECIPE, invalid)

    def test_operation_mapping_default_and_modules_shell_syntax(self):
        expected = {"install": ["install", "--groups", "core"], "install-defaults": ["install"],
                    "update-system": ["update", "system", "--groups", "core"],
                    "update-all": ["update", "all", "--groups", "core"]}
        self.assertEqual(set(expected), set(driver.OPERATIONS))
        self.assertEqual(driver.remote_script(COMMIT, RECIPE),
                         driver.remote_script(COMMIT, RECIPE, operation="install"))
        for operation, scope in expected.items():
            for modules in ((), ("opencode", "nono")):
                with self.subTest(operation=operation, modules=modules):
                    if operation == "install-defaults" and modules:
                        with self.assertRaises(driver.argparse.ArgumentTypeError):
                            driver.ssh_command(COMMIT, RECIPE, modules, operation)
                        continue
                    command = driver.ssh_command(COMMIT, RECIPE, modules, operation)
                    self.assertEqual(driver.bootstrap.ssh_command()[:-1], command[:-1])
                    script = shlex.split(command[-1])[-1]
                    argv = ["exec", "bash", "--noprofile", "--norc", "bin/dotfiles", *scope] + \
                           (["--modules", ",".join(modules)] if modules else [])
                    self.assertEqual(argv, shlex.split(script.splitlines()[-1]))
                    if operation == "install-defaults":
                        self.assertNotIn("--groups", script)
                        self.assertNotIn("--modules", script)
                    for guard in ("rev-parse --verify HEAD", "--untracked-files=all --ignored=matching",
                                  "sha256sum -- modules/paru-recipe/PKGBUILD", "[ ! -L"):
                        self.assertIn(guard, script)
                    checked = subprocess.run([shutil.which("bash"), "--noprofile", "--norc", "-n"],
                                             input=script, text=True, capture_output=True,
                                             env=driver.bootstrap.environment(), timeout=5)
                    self.assertEqual(0, checked.returncode, checked.stderr)

    def test_install_defaults_cli_rejects_module_overrides_before_subprocess(self):
        with patch.object(driver.sys, "argv", ["run-install.py", "--commit", COMMIT,
                                               "--recipe-sha256", RECIPE, "--operation", "install-defaults",
                                               "--modules", "opencode"]), \
                patch.object(driver.subprocess, "run") as run, \
                contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            driver.main()
        self.assertEqual(2, caught.exception.code)
        run.assert_not_called()

    def test_invalid_operation_rejected_by_api_and_cli_before_subprocess(self):
        invalids = ("", "update", "update system", "update-all;id", "$(id)", "install\n",
                    "INSTALL", "--groups=desktop", "update-system.*", None, [], ("install",))
        for operation in invalids:
            with self.subTest(operation=operation):
                with self.assertRaises(driver.argparse.ArgumentTypeError):
                    driver.ssh_command(COMMIT, RECIPE, operation=operation)
                if not isinstance(operation, str):
                    continue
                with patch.object(driver.sys, "argv", ["run-install.py", "--commit", COMMIT,
                                                       "--recipe-sha256", RECIPE, "--operation=" + operation]), \
                        patch.object(driver.subprocess, "run") as run, \
                        contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                    driver.main()
                self.assertEqual(2, caught.exception.code)
                run.assert_not_called()

    def test_additive_command_quoting_marker_and_shell_syntax(self):
        modules = tuple(sorted(driver.MODULE_ALLOWLIST))
        command = driver.ssh_command(COMMIT, RECIPE, modules)
        self.assertEqual(driver.bootstrap.ssh_command()[:-1], command[:-1])
        remote = shlex.split(command[-1])
        self.assertEqual(["bash", "--noprofile", "--norc", "-c"], remote[:-1])
        script = remote[-1]
        argv = shlex.split(script.splitlines()[-1])
        self.assertEqual(["exec", "bash", "--noprofile", "--norc", "bin/dotfiles", "install",
                          "--groups", "core", "--modules", ",".join(modules)], argv)
        self.assertIn("VM install driver: additive modules " + ",".join(modules), script)
        self.assertLess(script.index("sha256sum"), script.index("VM install driver: additive modules"))
        checked = subprocess.run([shutil.which("bash"), "--noprofile", "--norc", "-n"], input=script,
                                 text=True, capture_output=True, env=driver.bootstrap.environment(), timeout=5)
        self.assertEqual(0, checked.returncode, checked.stderr)

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

    def test_foreign_aur_update_blocks_all_prompts_after_native_or_noop(self):
        for native in (False, True):
            for aur_packages in (False, True):
                for prompt in (*driver.bootstrap.PROMPTS, driver.PARU_PROMPT,
                               ":: Proceed to review? [Y/n]:", ":: Proceed with installation? [Y/n]:"):
                    with self.subTest(native=native, aur_packages=aur_packages, prompt=prompt):
                        state = parser()
                        if native:
                            native_finished(state)
                        ready(state, driver.HELPER_PHASE)
                        if aur_packages:
                            state.feed((driver.AUR_PHASE + "\n").encode())
                        state.feed((driver.AUR_UPDATE_PHASE + "\n").encode())
                        with self.assertRaises(driver.bootstrap.Refused):
                            state.feed(prompt.encode())
                        self.assertTrue(state.stopped_at_review)
                        self.assertEqual(int(native), state.installs)

    def test_aur_update_phase_order_and_fragment_boundaries(self):
        for phase in (None, driver.DOWNLOAD_PHASE, driver.INSTALL_PHASE, driver.AUR_UPDATE_PHASE):
            state = parser()
            if phase == driver.AUR_UPDATE_PHASE:
                ready(state, driver.HELPER_PHASE)
                state.feed((driver.AUR_UPDATE_PHASE + "\n").encode())
            elif phase is not None:
                ready(state, phase)
            with self.assertRaises(driver.bootstrap.Refused):
                state.feed((driver.AUR_UPDATE_PHASE + "\n").encode())
        data = (driver.AUR_UPDATE_PHASE + "\n").encode()
        for split in range(len(data) + 1):
            state = parser()
            ready(state, driver.HELPER_PHASE)
            self.assertEqual([], state.feed(data[:split]) + state.feed(data[split:]))
            self.assertTrue(state.aur_started)
            self.assertEqual(driver.AUR_UPDATE_PHASE, state.phase)

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
        for status, verified, expected, modules, operation in (
                (43, True, 43, (), "install"), (-2, True, 130, (), "install"),
                (0, False, 1, (), "install"), (0, True, 0, ("nono", "discord"), "install"),
                (43, True, 43, ("opencode", "nono"), "update-system"),
                (0, True, 0, ("opencode", "nono"), "update-all"),
                (0, True, 0, (), "install-defaults")):
            def fake_runner(command, env, state):
                self.assertEqual(driver.ssh_command(COMMIT, RECIPE, modules, operation), command)
                if verified:
                    state.feed((state.marker + "\n").encode())
                    if modules or operation == "install-defaults":
                        state.feed((driver.DOWNLOAD_PHASE + "\n" + driver.INSTALL_PHASE + "\n" +
                                    driver.HELPER_PHASE + "\n").encode())
                        self.assertEqual(0, state.installs)
                        state.feed((driver.AUR_PHASE + "\n").encode())
                        if operation in ("update-system", "update-all"):
                            state.feed((driver.AUR_UPDATE_PHASE + "\n").encode())
                        with self.assertRaises(driver.bootstrap.Refused):
                            state.feed(b":: Proceed to review? [Y/n]: ")
                return status
            with patch.dict(driver.os.environ, {"LIMA_HOME": str(base.VM_HOME)}), \
                    patch.object(driver.sys, "argv", ["run-install.py", "--commit", COMMIT, "--recipe-sha256", RECIPE] +
                                 (["--modules", ",".join(modules)] if modules else []) +
                                 (["--operation", operation] if operation != "install" else [])), \
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
