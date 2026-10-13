#!/usr/bin/env python3
"""Small, local regression checks; no installation or real secrets involved."""

import json
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LinuxSetupTests(unittest.TestCase):
    def run_wallet_import(self, source, destination):
        script = (ROOT / "dot_local/bin/executable_secrets_import").read_text()
        functions = script.rsplit('main "$@"', 1)[0]
        return subprocess.run(
            ["bash", "-s", "--", str(source), str(destination)],
            input=functions + '\nimport_sparrow_wallet "$1" "$2"\n',
            capture_output=True,
            text=True,
            check=False,
        )

    def test_wallet_restoration_preserves_existing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.write_text("dummy wallet fixture")
            destination = root / "restored wallet"
            self.assertEqual(self.run_wallet_import(source, destination).returncode, 0)
            self.assertEqual(source.read_bytes(), destination.read_bytes())
            self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o600)
            self.assertEqual(self.run_wallet_import(source, destination).returncode, 1)
            destination.write_text("different dummy wallet")
            self.assertEqual(self.run_wallet_import(source, destination).returncode, 1)
            self.assertEqual(destination.read_text(), "different dummy wallet")

    def test_wallet_restoration_does_not_follow_destination_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.write_text("dummy wallet fixture")
            outside = root / "unrelated"
            outside.write_text("unchanged")
            destination = root / "wallet-link"
            destination.symlink_to(outside)
            self.assertEqual(self.run_wallet_import(source, destination).returncode, 1)
            self.assertEqual(outside.read_text(), "unchanged")

    def test_followups_are_manual_and_match_config_credentials(self):
        script = (ROOT / "install.sh").read_text().rsplit('main "$@"', 1)[0]
        result = subprocess.run(
            ["bash", "-s"], input=script + "\nprint_followups\n",
            capture_output=True, text=True, check=True,
        )
        for name in ("EXA_API_KEY", "GITHUB_MCP_TOKEN", "MAPLE_API_KEY"):
            self.assertIn(name, result.stdout)
            self.assertIn("{env:" + name + "}", (ROOT / "dot_config/opencode/private_opencode.jsonc").read_text())
        self.assertIn("~/.config/bash/.variables", result.stdout)
        self.assertIn("secrets_import manually", result.stdout)
        self.assertIn("No VM rehearsal is required", result.stdout)

    def test_linux_bitwarden_socket_enabled_and_disabled(self):
        for enabled in (True, False):
            data = {
                "chezmoi": {"os": "linux"}, "install_bitwarden": enabled,
                "install_gcloud": False, "install_nvm": False,
            }
            result = subprocess.run(
                ["chezmoi", "execute-template", "--source", str(ROOT),
                 "--override-data", json.dumps(data), "--file", str(ROOT / "dot_variables.tmpl")],
                capture_output=True, text=True, check=True,
            )
            self.assertEqual(".var/app/com.bitwarden.desktop/data/.bitwarden-ssh-agent.sock" in result.stdout, enabled)


if __name__ == "__main__":
    unittest.main()
