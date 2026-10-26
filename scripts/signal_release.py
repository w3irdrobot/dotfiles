"""Validate initial Signal AppImage pins without inspecting user application data."""

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def pin_fields():
    pin = json.loads((ROOT / 'modules/signal-release.json').read_text())
    if not isinstance(pin, dict) or set(pin) != {'version', 'sha256', 'key_sha256', 'fingerprint'}:
        raise ValueError('Invalid Signal AppImage pin fields')
    if not isinstance(pin['version'], str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', pin['version']):
        raise ValueError('Invalid Signal AppImage version')
    for key in ('sha256', 'key_sha256'):
        if not isinstance(pin[key], str) or not re.fullmatch('[0-9a-f]{64}', pin[key]):
            raise ValueError('Invalid Signal SHA256 pin')
    if pin['fingerprint'] != '4B16B7232DFAA439AD791002EF9F501F13EED94C':
        raise ValueError('Unexpected Signal signing identity; review key rotation explicitly')
    return '|'.join(pin[key] for key in ('version', 'sha256', 'key_sha256', 'fingerprint'))
