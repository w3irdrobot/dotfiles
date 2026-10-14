#!/usr/bin/env python3
"""Reviewed guest-only local VSCodium build: python3 -B tests/vm/run-vscodium.py
--approve-reviewed-vscodium. No mutable AUR sync/upgrade, stdin forwarding, or
forced transaction timeout. Reuses the isolated VM/SSH/PTY safety helpers.
"""
import argparse
import importlib.util
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

spec = importlib.util.spec_from_file_location("vm_install", Path(__file__).with_name("run-install.py"))
install = importlib.util.module_from_spec(spec)
spec.loader.exec_module(install)
bootstrap = install.bootstrap
COMMIT = "d04471d2fba90dc9fc16d52be8e6f957061b5ab3"
RECIPE = "d71cc3301f7d1445e4278b0b255336dcbc2da3c3da1070c85ade8c1784710a7f"
ARCHIVE = "61223b74f9e40834117311ec4177cb386d09b84c1aae4f9e674c96580569cef3"
DEPS = {"alsa-topology-conf", "alsa-ucm-conf", "alsa-lib", "nspr", "nss", "libnotify", "libxss"}
PROMPTS = (":: Proceed to review? [Y/n]:", ":: Proceed with installation? [Y/n]:",
           ":: Proceed with installation? [Y/n]")
MARKER = f"VM VSCodium driver: verified reviewed snapshot {COMMIT} recipe {RECIPE}"
PLAN = re.compile(r"^(Repo|Repo Make|Pkgbuilds|Pkgbuilds Make|Aur|Aur Make|Packages) \((\d+)\)\s*(.*)$")


class ReviewedParser:
    def __init__(self):
        self.pending = b""
        self.verified = False
        self.counts = [0, 0, 0]
        self.pkgbuild_seen = False
        self.plan = None
        self.remaining = 0
        self.packages = set()
        self.pacman_plan = False

    def line(self, text, complete):
        stripped = text.strip()
        if complete and stripped == MARKER:
            self.verified = True
        match = PLAN.fullmatch(stripped) if complete else None
        if match:
            if not self.verified or self.remaining:
                raise bootstrap.Refused("Unverified/incomplete package plan")
            self.plan, count, text = match.groups()
            self.remaining, self.packages = int(count), set()
            if self.plan not in ("Repo", "Pkgbuilds", "Packages") or not self.remaining:
                raise bootstrap.Refused("Unapproved AUR/make package plan")
        if complete and (match or (self.remaining and text[:1].isspace())):
            allowed = DEPS if self.plan == "Repo" else {"vscodium-bin"} if self.plan == "Pkgbuilds" else DEPS | {"vscodium-bin"}
            for token in text.split():
                names = [name for name in allowed if re.fullmatch(re.escape(name) + r"-[0-9][^\s]*", token)]
                if len(names) != 1 or names[0] in self.packages or self.remaining <= 0:
                    raise bootstrap.Refused("Package plan contains an unapproved/duplicate target")
                self.packages.add(names[0])
                self.remaining -= 1
            if not self.remaining:
                self.pkgbuild_seen |= self.plan == "Pkgbuilds" and self.packages == {"vscodium-bin"}
                self.pacman_plan = self.plan == "Packages"
        if stripped in PROMPTS:
            index = PROMPTS.index(stripped)
            if (not self.verified or not self.pkgbuild_seen or self.remaining or
                    self.counts[index] >= (2 if index == 2 else 1) or
                    (index == 0 and self.counts[1]) or (index == 2 and not self.pacman_plan)):
                raise bootstrap.Refused("Unverified/unapproved/repeated installation prompt")
            self.counts[index] += 1
            if index == 2:
                self.pacman_plan = False
            return b"y\n"
        if (complete or install.PROMPT_END.search(stripped)) and install.INTERACTIVE.search(stripped):
            raise bootstrap.Refused("Unexpected interactive question/menu; no answer sent")

    def feed(self, chunk):
        self.pending += chunk
        if len(self.pending) > 131072:
            raise bootstrap.Refused("Unbounded terminal output")
        text = bootstrap.ANSI.sub("", self.pending.decode("utf-8", errors="replace"))
        if "\x1b" in text:
            return []
        self.pending = b""
        lines, answers = text.replace("\r", "\n").split("\n"), []
        for index, line in enumerate(lines):
            complete = index < len(lines) - 1
            if not complete and line.strip() not in PROMPTS and any(p.startswith(line.strip()) for p in PROMPTS):
                self.pending = line.encode()
                continue
            # Pacman's prompt is also a prefix of Paru's colon-suffixed prompt:
            # wait for its trailing space/newline to disambiguate split reads.
            if not complete and line == PROMPTS[2]:
                self.pending = line.encode()
                continue
            answer = self.line(line, complete)
            if answer:
                answers.append(answer)
            elif not complete:
                self.pending = line.encode()
        return answers


def remote_script():
    return r'''set -euo pipefail
export PATH=/usr/bin:/bin LC_ALL=C TERM=dumb COLUMNS=1000
export PARU_CONF=/dev/null PARU_PAGER=/usr/bin/cat PAGER=/usr/bin/cat BAT_PAGER=/usr/bin/cat
export GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null
unset BASH_ENV ENV GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_CONFIG GIT_CONFIG_COUNT GIT_CONFIG_PARAMETERS
unset GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_COMMON_DIR
fail() { printf 'Reviewed VSCodium snapshot/native paru validation failed; refusing execution.\n' >&2; exit 65; }
[ "$(uname -s)" = Linux ] && [ "$(uname -m)" = x86_64 ] && [ "$EUID" -ne 0 ] || fail
root="$HOME"
for component in aur-review vscodium-bin; do
    root="$root/$component"; [ -d "$root" ] && [ ! -L "$root" ] || fail
done
[ "$(realpath -e -- "$root")" = "$root" ] && [ -d "$root/.git" ] && [ ! -L "$root/.git" ] || fail
cd -- "$root"
git_safe() { git -c core.fsmonitor=false -c core.hooksPath=/dev/null "$@"; }
[ "$(git_safe rev-parse --show-toplevel)" = "$root" ] || fail
[ "$(git_safe rev-parse HEAD)" = ''' + COMMIT + r''' ] || fail
[ "$(git_safe remote get-url origin)" = https://aur.archlinux.org/vscodium-bin.git ] || fail
if git_safe config --get-regexp '^filter\.' >/dev/null; then fail; fi
tracked=$(git_safe ls-files -v)
if printf '%s\n' "$tracked" | grep '^[a-zS]' >/dev/null; then fail; fi
[ -z "$(git_safe status --porcelain=v1 --untracked-files=all --ignored=matching)" ] || fail
[ -f PKGBUILD ] && [ ! -L PKGBUILD ] || fail
actual=$(sha256sum -- PKGBUILD)
[ "${actual%% *}" = ''' + RECIPE + r''' ] || fail
grep -Fq -- ''' + ARCHIVE + r''' PKGBUILD || fail
[ -f /usr/bin/paru ] && [ ! -L /usr/bin/paru ] && [ "$(pacman -Qqo /usr/bin/paru)" = paru ] || fail
case "$(/usr/bin/paru --version)" in 'paru v2.1.0'|'paru v2.1.0 '*) ;; *) fail ;; esac
linked=$(ldd /usr/bin/paru)
if printf '%s\n' "$linked" | grep -E '/nix/|not found' >/dev/null; then fail; fi
printf '%s\n' ''' + shlex.quote(MARKER) + r'''
exec /usr/bin/paru --build --install --needed --color never -- "$root"
'''


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--approve-reviewed-vscodium", required=True, action="store_true")
    cli.parse_args()
    try:
        if os.environ.get("LIMA_HOME", str(bootstrap.VM_HOME)) != str(bootstrap.VM_HOME):
            raise bootstrap.Refused("Only the isolated test LIMA_HOME is allowed")
        for path in (bootstrap.VM_HOME, bootstrap.VM_DIR, bootstrap.SSH_CONFIG):
            if path.resolve() != path:
                raise bootstrap.Refused("Test VM paths must not redirect through symlinks")
        env = bootstrap.environment()
        metadata = subprocess.run(["limactl", "list", "--json", bootstrap.INSTANCE], env=env,
                                  capture_output=True, text=True, check=True, timeout=30)
        bootstrap.validate_metadata(metadata.stdout)
        command = bootstrap.ssh_command()[:-1] + ["bash --noprofile --norc -c " + shlex.quote(remote_script())]
        parser = ReviewedParser()
        status = bootstrap.run_pty(command, env, parser)
        print(f"\nDriver: SSH/Paru exit status {status}; prompt approvals {parser.counts} (not a configuration-link test).", file=sys.stderr)
        return (status if status >= 0 else 128 - status) if parser.verified else (status if status > 0 else 1)
    except (bootstrap.Refused, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Driver refused/failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
