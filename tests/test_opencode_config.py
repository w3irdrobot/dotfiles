"""Check the portable tracked config, without reading the operator's live files."""

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "stow/opencode/.config/opencode"


class OpenCodeConfig(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((CONFIG_DIR / "opencode.jsonc").read_text())

    def test_current_server_set_and_github_credential_reference(self):
        servers = self.config["mcp"]["servers"]
        self.assertEqual(set(servers), {"exa", "github", "proxmox"})
        self.assertEqual(servers["github"]["headers"]["Authorization"],
                         "Bearer {env:GITHUB_TOKEN}")

    def test_proxmox_is_opt_in_and_uses_private_environment_values(self):
        server = self.config["mcp"]["servers"]["proxmox"]
        self.assertTrue(server["disabled"])
        self.assertEqual(server["type"], "local")
        self.assertEqual(server["environment"], {
            "PROXMOX_HOST": "{env:PROXMOX_HOST}",
            "PROXMOX_PORT": "443",
            "PROXMOX_USER": "{env:PROXMOX_USER}",
            "PROXMOX_TOKEN_NAME": "{env:PROXMOX_TOKEN_NAME}",
            "PROXMOX_TOKEN_VALUE": "{env:PROXMOX_API_KEY}",
            "PROXMOX_VERIFY_SSL": "1",
        })
        command = server["command"]
        self.assertEqual(command[:4], ["docker", "run", "-i", "--rm"])
        self.assertEqual(command[-3:], ["--network", "host", "proxmox-mcp:1.4.4"])
        forwarded = {command[index + 1] for index, value in enumerate(command) if value == "-e"}
        self.assertTrue(set(server["environment"]) <= forwarded)
        self.assertTrue({"PROXMOX_READ_ONLY", "PROXMOX_DISABLE_RAW_API"} <= forwarded)

    def test_uncensored_model_is_preserved(self):
        model = self.config["providers"]["maple-local"]["models"][
            "deepseek-v4-1-flash-1017-uncensored"
        ]
        self.assertEqual(model["name"], "DeepSeek V4.1 Flash Uncensored")

    def test_runtime_and_package_owned_files_are_not_vendored(self):
        for name in ("service.json", "plugins/nono-sandbox.ts", "skills/nono-sandbox"):
            self.assertFalse((CONFIG_DIR / name).exists(), name)


if __name__ == "__main__":
    unittest.main()
