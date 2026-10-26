"""Custom Fedora tool setup uses the shared platform contract."""

import subprocess
import unittest

import test_dotfiles


class FedoraTools(unittest.TestCase):
    mock = test_dotfiles.Fixture.mock
    calls = test_dotfiles.Fixture.calls
    assert_failed = test_dotfiles.Fixture.assert_failed

    def setUp(self):
        test_dotfiles.Fixture.setUp(self)
        self.mock("bat", "sys.exit(0 if sys.argv[1:3] == ['cache', '--build'] else 97)")
        self.mock("codium", "sys.exit(0 if sys.argv[1] in ('--list-extensions', '--install-extension') else 97)")

    def run_module(self, name):
        return subprocess.run(
            [test_dotfiles.BASH, str(self.repo / "modules" / f"{name}.sh")],
            cwd=self.repo, env=self.env, text=True, capture_output=True, timeout=20,
        )

    def test_bat_theme_build_accepts_fedora_44(self):
        result = self.run_module("bat")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(any(c[0] == "bat" and "--source" in c for c in self.calls()))

    def test_vscodium_extension_setup_accepts_fedora_44(self):
        result = self.run_module("vscodium")
        self.assertEqual(0, result.returncode, result.stderr)
        installed = [c for c in self.calls() if c[0] == "codium" and "--install-extension" in c]
        manifest = self.repo / "stow/vscodium/.config/VSCodium/extensions.txt"
        self.assertEqual(len(manifest.read_text().splitlines()), len(installed))

    def test_old_distro_or_wrong_fedora_release_stops_before_tool_execution(self):
        for text in ("ID=arch\n", "ID=manjaro\n", "ID=fedora\nVERSION_ID=43\n"):
            for module in ("bat", "vscodium"):
                with self.subTest(text=text, module=module):
                    self.log.unlink(missing_ok=True)
                    self.os_release.write_text(text)
                    self.assert_failed(self.run_module(module), "Only Fedora KDE Plasma Desktop 44")
                    self.assertFalse(any(c[0] in ("bat", "codium", "sudo") for c in self.calls()))
