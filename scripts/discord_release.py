"""Reviewed Discord bootstrap RPM metadata and read-only vendor update notices."""

import json
from pathlib import Path
import re
import shutil
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
URL = re.compile(r"https://stable\.dl2?\.discordapp\.net/apps/linux/([0-9]+\.[0-9]+\.[0-9]+)/discord-\1\.rpm")
LATEST = "https://discord.com/api/download?platform=linux&format=rpm"


def version_key(value):
    if not isinstance(value, str) or not VERSION.fullmatch(value):
        raise ValueError("Invalid Discord RPM version")
    return tuple(map(int, value.split('.')))


def load_pin():
    pin = json.loads((ROOT / 'modules/discord-release.json').read_text())
    if not isinstance(pin, dict) or set(pin) != {'version', 'url', 'sha256'}:
        raise ValueError('Invalid Discord RPM pin fields')
    version_key(pin['version'])
    match = URL.fullmatch(pin['url']) if isinstance(pin['url'], str) else None
    if not match or match[1] != pin['version']:
        raise ValueError('Discord pin must use the exact stable vendor RPM URL')
    if not isinstance(pin['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', pin['sha256']):
        raise ValueError('Invalid Discord RPM SHA256 pin')
    return pin


def published_version():
    request = urllib.request.Request(LATEST, method='HEAD', headers={'User-Agent': 'curl/8.0'})
    with urllib.request.urlopen(request, timeout=10) as response:
        match = URL.fullmatch(response.url)
        if not match:
            raise ValueError('Unexpected Discord stable RPM redirect; check vendor manually')
        return match[1]


def check_updates():
    pin = load_pin()
    installed = 'unknown (RPM unavailable)'
    if shutil.which('rpm'):
        result = subprocess.run(['rpm', '-q', '--qf', '%{VERSION}\n', 'discord'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            installed = result.stdout.strip()
            version_key(installed)
        elif result.returncode == 1:
            installed = 'not installed'
        else:
            raise ValueError('Could not inspect installed Discord RPM')
    published = published_version()
    print(f'Discord installed bootstrap RPM: {installed}')
    print(f'Reviewed bootstrap pin: {pin["version"]}; published stable RPM: {published}')
    if version_key(published) > version_key(pin['version']):
        print('New Discord RPM: review/update modules/discord-release.json, then rerun install/update with Discord selected.')
    else:
        print('No newer stable Discord RPM than the reviewed pin.')
    print('https://discord.com/download')
    print('RPM version only: Discord downloads/updates its user-level client separately on launch; setup never launches it.')
