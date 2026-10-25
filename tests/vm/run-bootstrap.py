#!/usr/bin/env python3
"""Rehearse the published bootstrap ONLY in the approved disposable Lima guest.

Run with python3 -B tests/vm/run-bootstrap.py --expect-conflict. No stdin is
forwarded. There is deliberately no transaction timeout: idle runs warn instead
of interrupting pacman. Only the two initial official pacman questions get y.
"""

import argparse
import errno
import json
import os
from pathlib import Path
import pty
import re
import select
import shlex
import signal
import subprocess
import sys
import time


VM_HOME = Path("/Users/alex/.lima-dotfiles-test")
INSTANCE = "dotfiles-arch"
VM_DIR = VM_HOME / INSTANCE
SSH_CONFIG = VM_DIR / "ssh.config"
BOOTSTRAP_SHA = "7c7e26825f3020aeb16b22dcc6120078bdeaeb9db14189319c5ad4f518f8c720"
PROMPTS = (
    ":: Proceed with download? [Y/n]",
    ":: Proceed with installation? [Y/n]",
)
# CSI and OSC sequences, including sequences split between reads.
ANSI = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\))")
CONFLICT = re.compile(r"dotfiles: Conflict: /[^\r\n]+/\.bashrc \(back it up and remove it yourself before linking\)")
QUESTION = re.compile(
    r"[\[(][^\])]*(?:y/n|yes/no)[^\])]*[\])]"
    r"|\[[^\]]*/[^\]]*\]"
    r"|(?:password|passphrase|enter|select|choose|confirm|continue|proceed)[^\n]*:\s*$",
    re.I,
)


class Refused(RuntimeError):
    pass


def validate_metadata(text):
    """Lima 2.2.1 list --json emits one object per line, not a JSON array."""
    rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    if len(rows) != 1 or not isinstance(rows[0], dict):
        raise Refused("Expected exactly one Lima instance record")
    row = rows[0]
    expected = {
        "name": INSTANCE, "dir": str(VM_DIR), "vmType": "qemu",
        "arch": "x86_64", "status": "Running", "sshLocalPort": 60022,
        "sshAddress": "127.0.0.1", "sshConfigFile": str(SSH_CONFIG),
    }
    for key, value in expected.items():
        if row.get(key) != value:
            raise Refused(f"Unsafe Lima metadata: {key}")
    if row.get("errors"):
        raise Refused("Lima reports instance errors")
    config = row.get("config")
    if not isinstance(config, dict):
        raise Refused("Missing resolved Lima configuration")
    if config.get("plain") is not True or config.get("vmType") != "qemu" or config.get("arch") != "x86_64":
        raise Refused("Unsafe resolved VM type/architecture/plain mode")
    # Lima omits empty slices in JSON; a missing mounts field means no mounts.
    if config.get("mounts", []) != []:
        raise Refused("Host mounts are forbidden")
    ssh = config.get("ssh", {})
    if (ssh.get("localPort") != 60022 or ssh.get("loadDotSSHPubKeys") is not False
            or ssh.get("forwardAgent") is not False):
        raise Refused("Unsafe resolved SSH configuration")


class PromptParser:
    """Consume complete lines and approved prompts; never pre-feed answers."""

    def __init__(self):
        self.pending = b""
        self.approved = set()
        self.conflict_seen = False

    def feed(self, chunk):
        self.pending += chunk
        # Keep incomplete escape sequences in the raw pending buffer.
        text = ANSI.sub("", self.pending.decode("utf-8", errors="replace"))
        if "\x1b" in text:
            return []
        self.pending = b""
        lines = text.replace("\r", "\n").split("\n")
        answers = []
        for index, line in enumerate(lines):
            self.conflict_seen |= bool(CONFLICT.search(line))
            stripped = line.strip()
            if stripped in PROMPTS:
                if stripped in self.approved:
                    raise Refused("Repeated pacman question; refusing additional approval")
                self.approved.add(stripped)
                answers.append(b"y\n")
                continue
            # Fail closed on questions/choice menus and password/input prompts.
            if "?" in line or QUESTION.search(line):
                # An allowed prompt can arrive in fragments; wait for its suffix.
                if index == len(lines) - 1 and any(p.startswith(stripped) for p in PROMPTS):
                    self.pending = line.encode()
                    continue
                raise Refused("Unexpected interactive question; no answer sent")
            if index == len(lines) - 1:
                self.pending = line.encode()
        if len(self.pending) > 65536:
            raise Refused("Unbounded unterminated output; refusing to guess")
        return answers


def ssh_command():
    # Hash verification and execution both happen inside the guest, never locally.
    script = (
        'set -eu; export LC_ALL=C; '
        'actual=$(sha256sum -- "$HOME/install-dotfiles.sh"); '
        f'[ "${{actual%% *}}" = {shlex.quote(BOOTSTRAP_SHA)} ] || '
        '{ printf "Guest bootstrap checksum mismatch; refusing execution.\\n" >&2; exit 65; }; '
        'printf "Guest bootstrap checksum verified.\\n"; '
        'exec bash --noprofile --norc "$HOME/install-dotfiles.sh" '
        '--ref master --groups core'
    )
    options = (
        "ControlMaster=no", "ControlPath=none", "ControlPersist=no",
        "ForwardAgent=no", "IdentityAgent=none", "ForwardX11=no",
        "ClearAllForwardings=yes", "BatchMode=yes", "PermitLocalCommand=no",
        "ProxyCommand=none", "ProxyJump=none", "HostName=127.0.0.1", "Port=60022",
    )
    command = ["ssh", "-tt", "-F", str(SSH_CONFIG)]
    for option in options:
        command.extend(("-o", option))
    return command + ["lima-dotfiles-arch", "bash --noprofile --norc -c " + shlex.quote(script)]


def environment():
    # Do not pass host credentials, SSH_AUTH_SOCK, or shell startup overrides.
    env = {key: os.environ[key] for key in ("PATH", "HOME", "TMPDIR") if key in os.environ}
    env.update(LIMA_HOME=str(VM_HOME), LC_ALL="C", TERM="dumb")
    return env


def run_pty(command, env, parser):
    master, slave = pty.openpty()
    child = None
    old_handler = signal.getsignal(signal.SIGINT)

    def warn_interrupt(signum, frame):
        print("\nDriver: not interrupting a possible package transaction; inspect the guest separately.", file=sys.stderr)

    try:
        signal.signal(signal.SIGINT, warn_interrupt)
        child = subprocess.Popen(command, stdin=slave, stdout=slave, stderr=slave,
                                 env=env, start_new_session=True)
        os.close(slave)
        slave = None
        last_output = time.monotonic()
        while True:
            ready, _, _ = select.select([master], [], [], 30)
            if not ready:
                if time.monotonic() - last_output >= 300:
                    print("Driver: idle for five minutes; no forced timeout (pacman may be active).", file=sys.stderr)
                    last_output = time.monotonic()
                continue
            try:
                chunk = os.read(master, 65536)
            except OSError as error:
                if error.errno != errno.EIO:
                    raise
                break
            if not chunk:
                break
            last_output = time.monotonic()
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()
            for answer in parser.feed(chunk):
                os.write(master, answer)
        return child.wait()
    finally:
        signal.signal(signal.SIGINT, old_handler)
        if child is not None and child.poll() is None:
            print("Driver: closing only this SSH child; inspect guest transaction state before retrying.", file=sys.stderr)
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        os.close(master)
        if slave is not None:
            os.close(slave)


def result_status(status, parser, expect_conflict):
    print(f"\nDriver: SSH/bootstrap exit status {status}.", file=sys.stderr)
    if expect_conflict:
        if status == 1 and parser.conflict_seen:
            print("PASS: expected .bashrc conflict stopped installation (not an installation success).", file=sys.stderr)
            return 0
        print("FAIL: expected exit 1 and explicit unmanaged .bashrc conflict.", file=sys.stderr)
        return status if status > 0 else 1
    return status if status >= 0 else 128 - status


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--expect-conflict", action="store_true")
    args = cli.parse_args()
    try:
        configured_home = os.environ.get("LIMA_HOME", str(VM_HOME))
        if configured_home != str(VM_HOME) or VM_HOME.resolve() != VM_HOME:
            raise Refused("Only the exact isolated test LIMA_HOME is allowed (no symlink)")
        if VM_DIR.resolve() != VM_DIR or SSH_CONFIG.resolve() != SSH_CONFIG:
            raise Refused("Test instance and generated SSH config must not redirect through symlinks")
        env = environment()
        metadata = subprocess.run(["limactl", "list", "--json", INSTANCE], env=env,
                                  capture_output=True, text=True, check=True, timeout=30)
        validate_metadata(metadata.stdout)
        print("Driver: isolated Running QEMU x86_64 guest verified; expect an unmanaged .bashrc stop.", flush=True)
        parser = PromptParser()
        status = run_pty(ssh_command(), env, parser)
        return result_status(status, parser, args.expect_conflict)
    except (Refused, OSError, ValueError, subprocess.SubprocessError) as error:
        # Do not dump metadata, environment, SSH config, or captured subprocess output.
        print(f"Driver refused/failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
