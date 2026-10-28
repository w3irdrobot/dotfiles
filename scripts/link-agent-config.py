#!/usr/bin/env python3
"""Opt-in, conflict-refusing links for Maple/Codex/OpenCode shared skills."""

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "stow/opencode/.config/opencode/skills"


def links(home):
    names = json.loads((ROOT / "agent-config/skills.json").read_text())
    if not isinstance(names, list) or not names:
        raise ValueError("Skill allowlist must be a nonempty list")
    if any(not isinstance(name, str) or not name or
           any(char not in "abcdefghijklmnopqrstuvwxyz0123456789-" for char in name)
           for name in names) or len(names) != len(set(names)):
        raise ValueError("Skill allowlist contains invalid or duplicate names")
    result = [(home / ".agents/AGENTS.md", ROOT / "agent-config/AGENTS.md")]
    for name in names:
        source = SKILLS / name
        if not (source / "SKILL.md").is_file():
            raise ValueError(f"Missing skill: {name}")
        result.append((home / ".agents/skills" / name, source))
    return result


def preflight(home, plan):
    if not home.is_dir():
        raise ValueError(f"Target home must already exist: {home}")
    for destination, source in plan:
        if not source.exists():
            raise ValueError(f"Missing source: {source}")
        for parent in destination.parents:
            if parent == home:
                break
            if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
                raise ValueError(f"Conflicting parent: {parent}")
        if os.path.lexists(destination):
            if (destination.is_symlink() and destination.exists()
                    and os.readlink(destination) == str(source)):
                continue
            raise ValueError(f"Conflict: {destination}; move it manually after review")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=Path.home(),
                        help="existing target home (default: current user's home)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    home = args.home.expanduser().resolve()
    try:
        plan = links(home)
        preflight(home, plan)
        for destination, source in plan:
            if destination.is_symlink():
                print(f"Already linked: {destination}")
                continue
            if args.dry_run:
                print(f"Would link: {destination} -> {source}")
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.symlink_to(source, target_is_directory=source.is_dir())
                print(f"Linked: {destination} -> {source}")
    except (OSError, ValueError) as error:
        print(f"agent-config: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
