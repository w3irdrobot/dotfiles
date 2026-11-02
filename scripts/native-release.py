#!/usr/bin/env python3
"""Verify an existing versioned dotfiles binary before changing its launcher."""

import hashlib
import json
from pathlib import Path
import re
import sys


def verify(tool, link, home):
    link, home = Path(link), Path(home)
    if not link.is_symlink():
        raise ValueError(f'Not a managed launcher symlink: {link}')
    # Require the literal absolute versioned path, not an alias into the store.
    target = link.readlink()
    store = home / '.local/share/dotfiles' / tool
    if target.parent.parent != store or target.name != tool or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', target.parent.name):
        raise ValueError(f'Unmanaged {tool} launcher: {link}')
    parent = target.parent
    while parent != home:
        if parent.is_symlink() or not parent.is_dir():
            raise ValueError(f'Conflicting managed binary parent: {parent}')
        parent = parent.parent
    pins = json.loads((Path(__file__).resolve().parents[1] / 'modules/native-release-history.json').read_text())
    digest = pins[tool].get(target.parent.name)
    if target.is_symlink() or not target.is_file() or not target.stat().st_mode & 0o111:
        raise ValueError(f'Missing, dangling, or conflicting managed binary: {target}')
    if digest is None or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
        raise ValueError(f'Unknown or modified managed binary: {target}')


if __name__ == '__main__':
    try:
        verify(*sys.argv[1:])
    except (OSError, ValueError, KeyError, TypeError) as error:
        sys.exit(str(error))
