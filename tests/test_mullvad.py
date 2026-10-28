"""Exit-node selection with fake Tailscale, picker, and HTTP; no network changes."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "stow/tailscale/.local/bin/tailscale-exit-node"
MOCK = r'''#!/usr/bin/python3
import json, os, pathlib, sys
base = pathlib.Path(os.environ["FIXTURE"])
name = pathlib.Path(sys.argv[0]).name
with (base / "calls").open("a") as f:
    f.write(json.dumps([name, *sys.argv[1:]]) + "\n")
if name == "tailscale":
    if sys.argv[1] == "set":
        if os.environ.get("SET_FAIL"):
            sys.exit(1)
        (base / "selected").write_text(sys.argv[2].split("=", 1)[1] + ".")
    else:
        status = json.loads((base / "status").read_text())
        if (base / "selected").exists() and not os.environ.get("WAIT_FAIL"):
            selected = (base / "selected").read_text()
            for peer in status["Peer"].values():
                peer["ExitNode"] = peer["DNSName"] == selected
                if peer["ExitNode"]:
                    status["ExitNodeStatus"] = {"ID": peer["ID"], "Online": True}
        print(json.dumps(status))
elif name == "fzf":
    lines = sys.stdin.read().splitlines()
    (base / "menu").write_text("\n".join(lines))
    if os.environ.get("CANCEL"):
        sys.exit(130)
    print(lines[int(os.environ.get("PICK", "1"))])
elif name == "curl":
    if os.environ.get("IP_FAIL"):
        sys.exit(7)
    print(json.dumps({"ip": "203.0.113.5", "city": "Boston", "country": "US"}))
'''


def peer(name, city="Boston", country="US", current=False, online=True):
    return {"ID": name, "DNSName": name + ".", "ExitNodeOption": True,
            "Online": online, "ExitNode": current,
            "Location": {"CountryCode": country, "City": city}}


class Mullvad(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mullvad-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        for name in ("tailscale", "fzf", "curl", "sleep"):
            path = self.base / name
            path.write_text(MOCK)
            path.chmod(0o755)
        self.env = os.environ | {"PATH": f"{self.base}:/usr/bin:/bin",
                                 "FIXTURE": str(self.base), "DEBUG": "0"}
        self.peers = [peer("us-bos-wg-001.mullvad.ts.net", current=True),
                      peer("us-lax-wg-001.mullvad.ts.net", city="Los Angeles"),
                      peer("ca-tor-wg-001.mullvad.ts.net", country="CA"),
                      peer("us-private.example.net"),
                      peer("us-offline.mullvad.ts.net", online=False)]

    def run_cli(self, *args, **env):
        (self.base / "status").write_text(json.dumps({
            "BackendState": "Running", "Peer": {str(i): p for i, p in enumerate(self.peers)}}))
        return subprocess.run(["bash", str(SCRIPT), *args], env=self.env | env,
                              capture_output=True, text=True, timeout=10)

    def calls(self, command):
        path = self.base / "calls"
        return [call for line in (path.read_text().splitlines() if path.exists() else [])
                if (call := json.loads(line))[0] == command]

    def test_manual_selection_filters_and_preserves_lan(self):
        result = self.run_cli(PICK="2")
        self.assertEqual(0, result.returncode, result.stderr)
        menu = (self.base / "menu").read_text().splitlines()
        self.assertTrue(menu[0].startswith("Random\t"))
        self.assertEqual(3, len(menu))
        self.assertIn("current", menu[1])
        self.assertEqual([["tailscale", "set", "--exit-node=us-lax-wg-001.mullvad.ts.net",
                           "--exit-node-allow-lan-access=true"]],
                         [c for c in self.calls("tailscale") if c[1] == "set"])
        self.assertEqual("203.0.113.5", json.loads(result.stdout)["ip"])
        self.assertIn("--noproxy", self.calls("curl")[0])

    def test_random_avoids_current(self):
        result = self.run_cli(PICK="0")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("us-lax-wg-001.mullvad.ts.net.", (self.base / "selected").read_text())

    def test_random_with_only_current_node(self):
        self.peers = self.peers[:1]
        result = self.run_cli(PICK="0")
        self.assertEqual(0, result.returncode, result.stderr)

    def test_cancel_changes_nothing(self):
        self.assertEqual(0, self.run_cli(CANCEL="1").returncode)
        self.assertFalse((self.base / "selected").exists())
        self.assertEqual([], self.calls("curl"))

    def test_no_nodes_changes_nothing(self):
        self.peers = []
        result = self.run_cli()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("No online US", result.stderr)
        self.assertEqual([], self.calls("fzf"))

    def test_failed_set_does_not_report_ip(self):
        self.assertNotEqual(0, self.run_cli(SET_FAIL="1").returncode)
        self.assertEqual([], self.calls("curl"))

    def test_timeout_does_not_report_ip_or_restart(self):
        result = self.run_cli(WAIT_FAIL="1")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("Timed out", result.stderr)
        self.assertEqual([], self.calls("curl"))
        self.assertTrue(all(c[1] in ("status", "set") for c in self.calls("tailscale")))

    def test_lookup_failure_is_explicit(self):
        result = self.run_cli(IP_FAIL="1")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("lookup failed", result.stderr)
        self.assertEqual(5, len(self.calls("curl")))

    def test_help_and_invalid_arguments_do_not_touch_network(self):
        self.assertEqual(0, self.run_cli("--help").returncode)
        self.assertEqual(2, self.run_cli("unexpected").returncode)
        self.assertEqual([], self.calls("tailscale"))
