"""Offline VM driver checks: no Lima, SSH, installer, or host credentials."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import shlex
from types import SimpleNamespace
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "vm_driver", Path(__file__).parent / "vm/run-bootstrap.py")
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


def metadata():
    return {
        "name": driver.INSTANCE, "dir": str(driver.VM_DIR), "vmType": "qemu",
        "arch": "x86_64", "status": "Running", "sshLocalPort": 60022,
        "sshAddress": "127.0.0.1", "sshConfigFile": str(driver.SSH_CONFIG),
        "config": {
            "vmType": "qemu", "arch": "x86_64", "plain": True, "mounts": [],
            "ssh": {"localPort": 60022, "loadDotSSHPubKeys": False, "forwardAgent": False},
        },
    }


class VMDriver(unittest.TestCase):
    def test_safe_metadata_and_lima_omitted_empty_mounts(self):
        row = metadata()
        driver.validate_metadata(json.dumps(row))
        del row["config"]["mounts"]
        driver.validate_metadata(json.dumps(row))

    def test_metadata_fails_closed(self):
        changes = (
            ("name", "personal"), ("dir", "/Users/alex/.lima/dotfiles-arch"),
            ("vmType", "vz"), ("arch", "aarch64"), ("status", "Stopped"),
            ("sshLocalPort", 22), ("sshAddress", "example.com"),
            ("sshConfigFile", "/Users/alex/.ssh/config"), ("errors", ["broken"]),
            ("config", None),
        )
        for key, value in changes:
            with self.subTest(key=key):
                row = metadata()
                row[key] = value
                with self.assertRaises(driver.Refused):
                    driver.validate_metadata(json.dumps(row))
        for key, value in (("plain", False), ("mounts", [{"location": "~"}]),
                           ("mounts", None), ("arch", "aarch64"), ("vmType", "vz")):
            row = metadata()
            row["config"][key] = value
            with self.assertRaises(driver.Refused):
                driver.validate_metadata(json.dumps(row))
        for key in ("loadDotSSHPubKeys", "forwardAgent", "localPort"):
            for missing in (False, True):
                row = metadata()
                if missing:
                    del row["config"]["ssh"][key]
                else:
                    row["config"]["ssh"][key] = True
                with self.assertRaises(driver.Refused):
                    driver.validate_metadata(json.dumps(row))
        for text in ("", "[]", json.dumps(metadata()) + "\n" + json.dumps(metadata())):
            with self.assertRaises(driver.Refused):
                driver.validate_metadata(text)

    def test_prompt_all_byte_boundaries_and_ansi(self):
        for prompt in driver.PROMPTS:
            data = ("packages...\r\n\x1b[1m" + prompt + "\x1b[0m ").encode()
            for split in range(len(data) + 1):
                with self.subTest(prompt=prompt, split=split):
                    parser = driver.PromptParser()
                    answers = parser.feed(data[:split]) + parser.feed(data[split:])
                    self.assertEqual([b"y\n"], answers)
                    self.assertEqual([], parser.feed(b"\r\ny\r\nDownloading...\r\n"))

    def test_bytewise_prompts_once_each(self):
        parser = driver.PromptParser()
        answers = []
        for byte in ("\x1b]0;pacman\x07" + "\n".join(driver.PROMPTS)).encode():
            answers.extend(parser.feed(bytes([byte])))
        self.assertEqual([b"y\n", b"y\n"], answers)
        with self.assertRaises(driver.Refused):
            parser.feed(("\n" + driver.PROMPTS[0]).encode())

    def test_unexpected_questions_never_approved(self):
        for question in (":: Import PGP key? [Y/n]", ":: Remove package? [y/N]",
                         "Proceed with download? [Y/n]", "[sudo] password for user:",
                         "Packages to cleanBuild?", "Choose a provider:",
                         "Continue (yes/no):", "Confirm action:",
                         driver.PROMPTS[0] + " unexpected suffix"):
            parser = driver.PromptParser()
            with self.subTest(question=question), self.assertRaises(driver.Refused):
                parser.feed(question.encode())
            self.assertEqual(set(), parser.approved)

    def test_no_preapproval_or_package_output_suppression(self):
        parser = driver.PromptParser()
        self.assertEqual([], parser.feed(b"Downloading packages...\r\n(1/2) upgrading git [#####] 100%\r\n"))
        self.assertEqual(set(), parser.approved)

    def test_real_pty_with_dummy_child_preserves_output_and_status(self):
        script = (
            "import sys; "
            "print('dummy package output', flush=True); "
            f"print({driver.PROMPTS[0]!r}, end=' ', flush=True); "
            "assert input() == 'y'; "
            f"print({driver.PROMPTS[1]!r}, end=' ', flush=True); "
            "assert input() == 'y'; "
            "print('dummy finished', flush=True); sys.exit(43)"
        )
        output = io.BytesIO()
        parser = driver.PromptParser()
        with patch.object(driver.sys, "stdout", SimpleNamespace(buffer=output)):
            status = driver.run_pty([driver.sys.executable, "-B", "-c", script],
                                    driver.environment(), parser)
        self.assertEqual(43, status)
        self.assertEqual(set(driver.PROMPTS), parser.approved)
        self.assertIn(b"dummy package output", output.getvalue())
        self.assertIn(b"dummy finished", output.getvalue())

    def test_expected_conflict_requires_real_exit_one_and_specific_message(self):
        parser = driver.PromptParser()
        data = b"dotfiles: Conflict: /home/test/.bashrc (back it up and remove it yourself before linking)\r\n"
        for byte in data:
            parser.feed(bytes([byte]))
        self.assertTrue(parser.conflict_seen)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(0, driver.result_status(1, parser, True))
            for status in (0, 2, 255):
                self.assertNotEqual(0, driver.result_status(status, parser, True))
            self.assertEqual(1, driver.result_status(1, driver.PromptParser(), True))
            self.assertEqual(43, driver.result_status(43, parser, False))
            self.assertEqual(130, driver.result_status(-2, parser, False))

    def test_ssh_is_only_execution_path_and_remote_quoting(self):
        with patch.object(driver, "SSH_CONFIG", Path("/test home/ssh.config")):
            command = driver.ssh_command()
        self.assertEqual("ssh", command[0])
        self.assertEqual("/test home/ssh.config", command[command.index("-F") + 1])
        self.assertEqual("lima-dotfiles-arch", command[-2])
        remote = shlex.split(command[-1])
        self.assertEqual(["bash", "--noprofile", "--norc", "-c"], remote[:-1])
        self.assertIn(driver.BOOTSTRAP_SHA, remote[-1])
        self.assertIn('exec bash --noprofile --norc "$HOME/install-dotfiles.sh"', remote[-1])
        self.assertIn("--ref rewrite/arch-bash --groups core", remote[-1])
        for option in ("ControlMaster=no", "ControlPath=none", "ForwardAgent=no",
                       "IdentityAgent=none", "BatchMode=yes", "PermitLocalCommand=no"):
            self.assertIn(option, command)

    def test_unsafe_home_is_rejected_before_any_subprocess(self):
        with patch.dict(driver.os.environ, {"LIMA_HOME": "/Users/alex/.lima"}), \
                patch.object(driver.subprocess, "run") as run, \
                patch.object(driver.sys, "argv", ["run-bootstrap.py"]), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(1, driver.main())
        run.assert_not_called()

    def test_environment_is_allowlisted(self):
        with patch.dict(driver.os.environ, {"PATH": "/usr/bin", "HOME": "/Users/alex",
                                           "SSH_AUTH_SOCK": "/unused", "BASH_ENV": "/unused"}, clear=True):
            env = driver.environment()
        self.assertEqual({"PATH", "HOME", "LIMA_HOME", "LC_ALL", "TERM"}, set(env))
        self.assertEqual(str(driver.VM_HOME), env["LIMA_HOME"])


if __name__ == "__main__":
    unittest.main()
