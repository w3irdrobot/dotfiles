#!/usr/bin/env python3
"""Link shared instructions and skills for selected local execution tools."""

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "agent-config/skills"
INSTRUCTIONS = ROOT / "agent-config/instructions/AGENTS.md"
TOOLS = ("maple", "codex", "claude", "opencode")


def links(home, tools=("maple",)):
    if not tools or len(set(tools)) != len(tools) or any(tool not in TOOLS for tool in tools):
        raise ValueError("Select unique tools from: " + ", ".join(TOOLS))
    names = json.loads((ROOT / "agent-config/skills.json").read_text())
    if not isinstance(names, list) or not names:
        raise ValueError("Skill allowlist must be a nonempty list")
    if any(not isinstance(name, str) or not name or
           any(char not in "abcdefghijklmnopqrstuvwxyz0123456789-" for char in name)
           for name in names) or len(names) != len(set(names)):
        raise ValueError("Skill allowlist contains invalid or duplicate names")
    result = [(home / ".agents/AGENTS.md", INSTRUCTIONS)]
    instruction_paths = {
        "codex": ".codex/AGENTS.md",
        "claude": ".claude/CLAUDE.md",
        "opencode": ".config/opencode/AGENTS.md",
    }
    for tool in tools:
        if tool in instruction_paths:
            result.append((home / instruction_paths[tool], INSTRUCTIONS))
    for name in names:
        source = SKILLS / name
        if not (source / "SKILL.md").is_file():
            raise ValueError(f"Missing skill: {name}")
        result.append((home / ".agents/skills" / name, source))
        if "claude" in tools:
            result.append((home / ".claude/skills" / name, source))
        if "opencode" in tools:
            # Keep explicit discovery working when external skill discovery is off.
            result.append((home / ".config/opencode/skills" / name, source))
    if "opencode" in tools:
        for source in sorted((ROOT / "agent-config/agents/opencode").glob("*.md")):
            result.append((home / ".config/opencode/agents" / source.name, source))
    return result


def owned_link(destination, source):
    return (destination.is_symlink() and destination.exists()
            and destination.resolve() == source.resolve())


def preflight(home, plan):
    if not home.is_dir():
        raise ValueError(f"Target home must already exist: {home}")
    stow_root = ROOT / "stow/opencode/.config/opencode"
    allowed = {stow_root.resolve(), SKILLS.resolve(),
               (ROOT / "agent-config/agents/opencode").resolve()}
    for destination, source in plan:
        if not source.exists():
            raise ValueError(f"Missing source: {source}")
        for parent in destination.parents:
            if parent == home:
                break
            # A Stow-managed directory may resolve to this exact source tree.
            if (parent.is_symlink() and parent.resolve() not in allowed
                    or parent.exists() and not parent.is_dir()):
                raise ValueError(f"Conflicting parent: {parent}")
        if os.path.lexists(destination):
            if owned_link(destination, source) or destination.resolve() == source.resolve():
                continue
            raise ValueError(f"Conflict: {destination}; move it manually after review")
        if any(parent.is_symlink() for parent in destination.parents if parent != home):
            raise ValueError(f"Refusing to create files through a linked parent: {destination}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=Path.home(),
                        help="existing target home (default: current user's home)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--tools", required=True,
                        help="comma-separated selection: maple,codex,claude,opencode")
    args = parser.parse_args()
    home = args.home.expanduser().resolve()
    try:
        tools = tuple(args.tools.split(","))
        config_variables = {"codex": "CODEX_HOME", "claude": "CLAUDE_CONFIG_DIR",
                            "opencode": "XDG_CONFIG_HOME"}
        for variable in (config_variables[tool] for tool in tools if tool in config_variables):
            if os.environ.get(variable):
                expected = {"CODEX_HOME": home / ".codex",
                            "CLAUDE_CONFIG_DIR": home / ".claude",
                            "XDG_CONFIG_HOME": home / ".config"}[variable]
                if Path(os.environ[variable]).expanduser().resolve() != expected:
                    raise ValueError(f"Custom {variable} is unsupported; use the tool's default layout")
        if "codex" in tools and os.path.lexists(home / ".codex/AGENTS.override.md"):
            raise ValueError("Codex AGENTS.override.md would shadow shared instructions; review it first")
        plan = links(home, tools)
        preflight(home, plan)
        for destination, source in plan:
            if destination.exists() and destination.resolve() == source.resolve():
                print(f"Already linked: {destination}")
                continue
            if args.dry_run:
                print(f"Would link: {destination} -> {source}")
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.symlink_to(source, target_is_directory=source.is_dir())
                print(f"Linked: {destination} -> {source}")
    except (OSError, ValueError, RuntimeError) as error:
        print(f"agent-config: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
