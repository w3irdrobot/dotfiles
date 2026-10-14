#!/usr/bin/env python3
"""Controlled core install in the approved disposable guest, never on the host.

Usage: python3 -B tests/vm/run-install.py --commit FULL40SHA --recipe-sha256 SHA256
Both pins must be reviewed/published beforehand. No stdin forwarding, forced
transaction timeout, or VSCodium/AUR package approval. An AUR review stop is NOT
installation success. The shared PTY runner prints all guest/package output.
"""

import argparse
import importlib.util
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys


spec = importlib.util.spec_from_file_location("vm_bootstrap", Path(__file__).with_name("run-bootstrap.py"))
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)

PARU_PROMPT = "Build this pinned local paru PKGBUILD with its unchanged upstream lock? [y/N]"
DOWNLOAD_PHASE = "dotfiles: Database refresh: downloading the full upgrade without installing packages"
INSTALL_PHASE = "dotfiles: Full upgrade: installing against the checked repository indexes"
HELPER_PHASE = "dotfiles: AUR setup: preparing the helper and selected packages"
AUR_PHASE = "dotfiles: AUR packages: installing the selected dependencies"
# Anchor known interactive forms, not arbitrary question marks in build output,
# PKGBUILD comments, package descriptions, or URLs containing query strings.
INTERACTIVE = re.compile(
    r"^(?:::|==>|->)\s+(?:.*\[(?:[Yy]/[Nn]|[Nn]/[Yy])\]\s*$"
    r"|(?:Enter|Select|Choose|Proceed|Accept|Import|Replace|Remove|Continue|Confirm|"
    r"Edit|Review|Skip|Delete|Packages to exclude|Packages to cleanBuild|Diffs to show)\b"
    r"|\[(?:N|A|Ab|I|No)\](?:one|ll|ort|nstalled|tInstalled))"
    r"|^(?:\[sudo\]\s+)?(?:password|passphrase)(?:\s+for\s+[^:]+)?:\s*$"
    r"|^(?:Enter|Select|Choose|Continue|Confirm|Proceed)\b.*(?:\?|:)\s*$"
    r"|^(?:Build|Install|Remove|Replace|Download|Import|Proceed|Continue|Accept|Confirm|"
    r"Edit|Review|Skip|Delete|Abort|Retry|Do you|Are you|Would you)\b.*"
    r"\[(?:[Yy]/[Nn]|[Nn]/[Yy])\]\s*$",
    re.I,
)
PROMPT_END = re.compile(r"(?:[?:]|\[(?:y/n|n/y)\])\s*$", re.I)


def pin(value, length):
    if not re.fullmatch(rf"[0-9a-fA-F]{{{length}}}", value):
        raise argparse.ArgumentTypeError(f"Expected exactly {length} hexadecimal characters")
    return value.lower()


def verified_marker(commit, recipe_sha):
    return f"VM install driver: verified HEAD {commit} and recipe {recipe_sha}"


class InstallParser:
    def __init__(self, commit, recipe_sha):
        self.marker = verified_marker(commit, recipe_sha)
        self.pending = b""
        self.verified = False
        self.phase = None
        self.downloads = 0
        self.installs = 0
        self.native_install_approved = False
        self.paru_install_approved = False
        self.paru_approved = False
        self.aur_started = False
        self.stopped_at_review = False

    def line(self, text, complete=True):
        text = text.strip()
        if complete and text == self.marker:
            self.verified = True
        previous = {DOWNLOAD_PHASE: None, INSTALL_PHASE: DOWNLOAD_PHASE,
                    HELPER_PHASE: INSTALL_PHASE, AUR_PHASE: HELPER_PHASE}
        if complete and text in previous:
            if not self.verified or self.phase != previous[text]:
                raise bootstrap.Refused("Unverified, repeated, or out-of-order installer phase")
            self.phase = text
            if text == AUR_PHASE:
                self.aur_started = True
        if text in (*bootstrap.PROMPTS, PARU_PROMPT):
            if not self.verified or self.aur_started:
                self.refuse()
            if text == bootstrap.PROMPTS[0]:
                if self.phase != DOWNLOAD_PHASE or self.downloads:
                    self.refuse()
                self.downloads += 1
            elif text == bootstrap.PROMPTS[1]:
                if self.phase == INSTALL_PHASE and not self.native_install_approved:
                    self.native_install_approved = True
                elif self.phase == HELPER_PHASE and self.paru_approved and not self.paru_install_approved:
                    self.paru_install_approved = True
                else:
                    self.refuse()
                self.installs += 1
            else:
                if self.phase != HELPER_PHASE or self.paru_approved:
                    self.refuse()
                self.paru_approved = True
            return b"y\n"
        # A read can end at '==> Enter' in ordinary 'Entering...' output.
        # Only classify generic forms once the line or prompt has ended.
        if (complete or PROMPT_END.search(text)) and INTERACTIVE.search(text):
            self.refuse()
        return None

    def refuse(self):
        self.stopped_at_review = self.aur_started
        raise bootstrap.Refused("Unapproved/repeated interactive prompt; no answer sent (AUR packages are not approved)")

    def feed(self, chunk):
        self.pending += chunk
        if len(self.pending) > 131072:
            raise bootstrap.Refused("Unbounded terminal output; refusing to guess")
        text = bootstrap.ANSI.sub("", self.pending.decode("utf-8", errors="replace"))
        if "\x1b" in text:
            return []
        self.pending = b""
        lines = text.replace("\r", "\n").split("\n")
        answers = []
        for index, line in enumerate(lines):
            # Wait for fragmented approved prompts, even after their '?' arrives.
            if index == len(lines) - 1 and any(p.startswith(line.strip()) and p != line.strip()
                                                for p in (*bootstrap.PROMPTS, PARU_PROMPT)):
                self.pending = line.encode()
                continue
            answer = self.line(line, complete=index < len(lines) - 1)
            if answer is not None:
                answers.append(answer)
            elif index == len(lines) - 1:
                self.pending = line.encode()
        return answers


def remote_script(commit, recipe_sha):
    # Validate again for callers other than argparse; no shell text interpolation.
    commit, recipe_sha = pin(commit, 40), pin(recipe_sha, 64)
    return r'''set -euo pipefail
export LC_ALL=C PATH=/usr/bin:/bin
unset BASH_ENV ENV GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_CONFIG GIT_CONFIG_COUNT
unset GIT_CONFIG_PARAMETERS GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_COMMON_DIR
fail() { printf 'VM install driver: checkout/pin validation failed; refusing execution.\n' >&2; exit 65; }
[ "$(uname -s)" = Linux ] && [ "$(uname -m)" = x86_64 ] && [ "$EUID" -ne 0 ] || fail
[ -d "$HOME" ] && [ ! -L "$HOME" ] || fail
root="$HOME"
for component in projects github.com w3irdrobot dotfiles; do
    root="$root/$component"
    [ -d "$root" ] && [ ! -L "$root" ] || fail
done
[ "$(realpath -e -- "$root")" = "$root" ] || fail
[ -d "$root/.git" ] && [ ! -L "$root/.git" ] || fail
cd -- "$root"
git_safe() { git -c core.fsmonitor=false -c core.untrackedCache=false -c core.hooksPath=/dev/null "$@"; }
[ "$(git_safe rev-parse --show-toplevel)" = "$root" ] || fail
[ "$(git_safe rev-parse --verify HEAD)" = ''' + shlex.quote(commit) + r''' ] || fail
[ "$(git_safe symbolic-ref --quiet --short HEAD)" = rewrite/arch-bash ] || fail
case "$(git_safe remote get-url origin)" in
    https://github.com/w3irdrobot/dotfiles.git|https://github.com/w3irdrobot/dotfiles|git@github.com:w3irdrobot/dotfiles.git) ;;
    *) fail ;;
esac
# Reject all untracked AND ignored paths, rather than trusting .gitignore to hide
# an alternate installer, recipe, or local shell customization.
tracked=$(git_safe ls-files -v)
if printf '%s\n' "$tracked" | grep '^[a-zS]' >/dev/null; then fail; fi
[ -z "$(git_safe status --porcelain=v1 --untracked-files=all --ignored=matching)" ] || fail
for directory in bin modules modules/paru-recipe; do
    [ -d "$directory" ] && [ ! -L "$directory" ] || fail
done
for file in bin/dotfiles modules/paru-recipe/PKGBUILD; do
    [ -f "$file" ] && [ ! -L "$file" ] || fail
    git_safe ls-files --error-unmatch -- "$file" >/dev/null || fail
done
actual=$(sha256sum -- modules/paru-recipe/PKGBUILD)
[ "${actual%% *}" = ''' + shlex.quote(recipe_sha) + r''' ] || fail
printf '%s\n' ''' + shlex.quote(verified_marker(commit, recipe_sha)) + r'''
exec bash --noprofile --norc bin/dotfiles install --groups core
'''


def ssh_command(commit, recipe_sha):
    # Reuse every fixed-target SSH option; discard only the bootstrap remote cmd.
    return bootstrap.ssh_command()[:-1] + [
        "bash --noprofile --norc -c " + shlex.quote(remote_script(commit, recipe_sha))]


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--commit", required=True, type=lambda value: pin(value, 40))
    cli.add_argument("--recipe-sha256", required=True, type=lambda value: pin(value, 64))
    args = cli.parse_args()
    parser = InstallParser(args.commit, args.recipe_sha256)
    try:
        if os.environ.get("LIMA_HOME", str(bootstrap.VM_HOME)) != str(bootstrap.VM_HOME):
            raise bootstrap.Refused("Only the exact isolated test LIMA_HOME is allowed")
        for path in (bootstrap.VM_HOME, bootstrap.VM_DIR, bootstrap.SSH_CONFIG):
            if path.resolve() != path:
                raise bootstrap.Refused("Test home, instance, and SSH config must not redirect through symlinks")
        env = bootstrap.environment()
        metadata = subprocess.run(["limactl", "list", "--json", bootstrap.INSTANCE],
                                  env=env, capture_output=True, text=True, check=True, timeout=30)
        bootstrap.validate_metadata(metadata.stdout)
        print("Driver: isolated VM verified; guest pins/clean checkout must pass before any approvals. AUR packages remain unapproved.", flush=True)
        status = bootstrap.run_pty(ssh_command(args.commit, args.recipe_sha256), env, parser)
        print(f"\nDriver: SSH/installer exit status {status}; native install approved: {parser.native_install_approved}; paru install approved: {parser.paru_install_approved}; install confirmations: {parser.installs}; pinned paru review approved: {parser.paru_approved}.", file=sys.stderr)
        if not parser.verified:
            return status if status > 0 else 1
        return status if status >= 0 else 128 - status
    except (bootstrap.Refused, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Driver refused/failed: {type(error).__name__}: {error}", file=sys.stderr)
        if parser.stopped_at_review:
            print("Stopped at unapproved AUR review; this is not installation success. Review the fetched recipe before extending approvals.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
