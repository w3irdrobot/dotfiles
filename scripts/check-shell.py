#!/usr/bin/env python3
"""Read-only Bash validation; include managed Bash helpers, not vendored skills."""

import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def shell_files():
    candidates = [ROOT / "install.sh", ROOT / "bin/dotfiles"]
    for directory in ("bin", "lib", "modules", "scripts", "shell", "examples", "stow"):
        base = ROOT / directory
        if base.exists():
            candidates.extend(
                p for p in base.rglob("*")
                if p.is_file() and "skills" not in p.relative_to(base).parts
            )
    result = []
    for path in sorted(set(candidates)):
        if not path.is_file():
            continue
        with path.open("rb") as source:
            head = source.read(256)
        if (
            path.suffix == ".sh"
            or b"shell=bash" in head
            or (head.startswith(b"#!") and b"bash" in head.splitlines()[0])
            or path.name in (".bashrc", ".bash_profile", ".bash_aliases")
        ):
            result.append(str(path.relative_to(ROOT)))
    return result


def main():
    missing = [tool for tool in ("bash", "shellcheck", "shfmt") if not shutil.which(tool)]
    if missing:
        sys.exit("Missing validation tools: " + ", ".join(missing))
    files = shell_files()
    if not files:
        sys.exit("No Bash files found")
    failed = False
    for path in files:
        lint = ["shellcheck", "--shell=bash", "--external-sources", "--source-path=SCRIPTDIR"]
        if path.startswith("stow/"):
            # Machine-local sourced files do not exist in the checkout.
            lint += ["--exclude=SC1091"]
        if path == "shell/functions.sh":
            # gshell intentionally exports credentials into its child shell only.
            lint += ["--exclude=SC1091,SC2030,SC2031"]
        for command in (["bash", "-n", path], [*lint, path], ["shfmt", "-d", path]):
            failed |= subprocess.run(command, cwd=ROOT, check=False).returncode != 0
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
