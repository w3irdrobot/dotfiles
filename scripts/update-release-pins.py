#!/usr/bin/env python3
"""Prepare reviewed release pins in the checkout; never install downloaded code."""

import argparse
import base64
import hashlib
import io
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

import discord_release

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('dotfiles_check_updates', ROOT / 'scripts/check-updates.py')
check_updates = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_updates)
TOOLS = ('opencode', 'nono', 'bitwarden', 'discord', 'signal')


def download(url):
    if not url.startswith('https://'):
        raise ValueError('Release URLs must use HTTPS')
    request = urllib.request.Request(url, headers={'User-Agent': 'dotfiles-release-pins'})
    with urllib.request.urlopen(request, timeout=60) as response:
        if not response.url.startswith('https://'):
            raise ValueError('Insecure release redirect')
        return response.read()


def metadata(url):
    return json.loads(download(url))


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def version(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', value):
        raise ValueError(f'Not a stable release version: {value!r}')
    return tuple(map(int, value.split('.')))


def member(archive, name):
    # Read a single regular member; never extract paths or execute downloaded code.
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as tar:
        matches = [entry for entry in tar.getmembers() if entry.name == name]
        if len(matches) != 1 or not matches[0].isfile():
            raise ValueError(f'Archive lacks a unique regular {name}')
        return tar.extractfile(matches[0]).read()


def checked_asset(release, name):
    if release.get('draft') is not False or release.get('prerelease') is not False:
        raise ValueError('Expected a published stable release')
    assets = [asset for asset in release['assets'] if asset['name'] == name]
    if len(assets) != 1:
        raise ValueError(f'Missing unique release asset: {name}')
    asset = assets[0]
    digest = asset.get('digest', '')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', digest):
        raise ValueError('Upstream asset has no SHA256 digest; review manually')
    data = download(asset['browser_download_url'])
    if digest != 'sha256:' + sha256(data):
        raise ValueError('Upstream asset digest mismatch')
    return asset['browser_download_url'], data


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f'Expected one source occurrence of {old!r}')
    return text.replace(old, new, 1)


def native(tool):
    path = ROOT / f'modules/{tool}.sh'
    text = path.read_text()
    if tool == 'opencode':
        old = re.search(r'OPENCODE_VERSION=([0-9.]+)', text)[1]
        info = metadata('https://registry.npmjs.org/@opencode/cli-linux-x64-baseline/latest')
        new = info['version']
        version(new)
        if version(new)[0] != 2:
            raise ValueError('OpenCode major-version changes require manual review')
        archive = download(info['dist']['tarball'])
        integrity = 'sha512-' + base64.b64encode(hashlib.sha512(archive).digest()).decode()
        if integrity != info['dist']['integrity']:
            raise ValueError('npm SHA512 integrity mismatch')
        binary = member(archive, 'package/bin/opencode')
        previous_hash = re.search(r'OPENCODE_BINARY_SHA256=([a-f0-9]{64})', text)[1]
        changes = {
            'OPENCODE_VERSION': new, 'OPENCODE_URL': info['dist']['tarball'],
            'OPENCODE_ARCHIVE_SHA256': sha256(archive), 'OPENCODE_BINARY_SHA256': sha256(binary),
        }
        for key, value in changes.items():
            text = re.sub(rf'(?m)^readonly {key}=.*$', f'readonly {key}={value}', text)
        text = text.replace(f'/opencode/{old}/opencode', f'/opencode/{new}/opencode')
        files = {path: text}
        for relative in ('install.sh', 'lib/dotfiles.sh'):
            guard = ROOT / relative
            source = guard.read_text()
            source = source.replace(f'/opencode/{old}/opencode', f'/opencode/{new}/opencode')
            marker = '\t# Previous verified OpenCode releases (maintained by update-release-pins).'
            record = f'\t{old}) digest={previous_hash} ;;'
            if record not in source:
                source = replace_once(source, marker, marker + '\n' + record)
            files[guard] = source
        readme = ROOT / 'README.md'
        files[readme] = readme.read_text().replace(f'/opencode/{old}/opencode', f'/opencode/{new}/opencode')
        return old, new, files, sha256(binary), previous_hash
    old = re.search(r'/dotfiles/nono/([0-9.]+)/nono', text)[1]
    release = metadata('https://api.github.com/repos/nolabs-ai/nono/releases/latest')
    new = release['tag_name'].removeprefix('v')
    version(new)
    name = f'nono-v{new}-x86_64-unknown-linux-gnu.tar.gz'
    url, archive = checked_asset(release, name)
    previous = re.search(r"printf '%s  %s\\n' ([a-f0-9]{64})", text)[1]
    text = text.replace(f'/nono/{old}/nono', f'/nono/{new}/nono')
    text = re.sub(r'https://github.com/nolabs-ai/nono/releases/download/[^\s]+', url, text)
    text = replace_once(text, previous, sha256(archive))
    binary_hash = sha256(member(archive, 'nono'))
    return old, new, {path: text}, binary_hash, None


def signal_pin(old):
    release = metadata('https://api.github.com/repos/signalapp/Signal-Desktop/releases/latest')
    if release.get('draft') is not False or release.get('prerelease') is not False:
        raise ValueError('Expected a stable Signal release')
    new = release['tag_name'].removeprefix('v')
    version(new)
    url = f'https://updates.signal.org/desktop/signal-desktop_{new}_x86_64.AppImage'
    image, signature = download(url), download(url + '.gpg')
    key = download('https://updates.signal.org/static/desktop/appimage.asc')
    if sha256(key) != old['key_sha256']:
        raise ValueError('Signal signing key changed; review rotation manually')
    with tempfile.TemporaryDirectory(prefix='dotfiles-signal-') as directory:
        temp = Path(directory)
        for name, data in (('image', image), ('image.gpg', signature), ('key.asc', key)):
            (temp / name).write_bytes(data)
        command = ['gpg', '--homedir', directory, '--batch', '--no-auto-key-retrieve']
        subprocess.run(command + ['--import', str(temp / 'key.asc')], check=True, capture_output=True)
        result = subprocess.run(command + ['--status-fd', '1', '--verify', str(temp / 'image.gpg'), str(temp / 'image')],
                                check=True, capture_output=True, text=True)
        if not any(line.startswith('[GNUPG:] VALIDSIG ') and old['fingerprint'] in line.split()
                   for line in result.stdout.splitlines()):
            raise ValueError('Signal signature has an unexpected signing identity')
    return {**old, 'version': new, 'sha256': sha256(image)}


def rpm_pin(tool, old):
    if tool == 'bitwarden':
        release = check_updates.latest_desktop_release()
        pin = {'version': release['version'], 'url': check_updates.artifact_url(release['version']),
               'sha256': release['sha256']}
        data = download(pin['url'])
        if sha256(data) != pin['sha256']:
            raise ValueError('Bitwarden RPM digest mismatch')
    else:
        new = discord_release.published_version()
        # Resolve the stable endpoint again and ensure it still names that version.
        with urllib.request.urlopen(urllib.request.Request(discord_release.LATEST,
                                     headers={'User-Agent': 'curl/8.0'}), timeout=60) as response:
            match = discord_release.URL.fullmatch(response.url)
            if not match or match[1] != new:
                raise ValueError('Discord release changed during download; retry')
            data = response.read()
            pin = {'version': new, 'url': response.url, 'sha256': sha256(data)}
        print('Discord: recording HTTPS download hash; vendor supplies no independent checksum.')
    with tempfile.TemporaryDirectory(prefix='dotfiles-rpm-') as directory:
        path = Path(directory) / 'release.rpm'
        path.write_bytes(data)
        identity = subprocess.run(['rpm', '-qp', '--qf', '%{NAME}|%{VERSION}|%{ARCH}', str(path)],
                                  capture_output=True, text=True, check=True).stdout
        if identity != f'{tool}|{pin["version"]}|x86_64':
            raise ValueError(f'Unexpected {tool} RPM identity')
    return pin


def prepare(tool):
    if tool in ('opencode', 'nono'):
        old, new, files, digest, _previous = native(tool)
        if old == new and any(path.read_text() != content for path, content in files.items()):
            raise ValueError(f'{tool}: upstream changed the existing pin; investigate manually')
        history_path = ROOT / 'modules/native-release-history.json'
        history = json.loads(history_path.read_text())
        if version(new) < version(old):
            raise ValueError(f'{tool}: refusing downgrade {old} -> {new}')
        known = history[tool].get(new)
        if known is not None and known != digest:
            raise ValueError(f'{tool}: binary digest changed for {new}')
        history[tool][new] = digest
        files[history_path] = json.dumps(history, indent=2) + '\n'
    else:
        path = ROOT / f'modules/{tool}-release.json'
        old_pin = json.loads(path.read_text())
        pin = signal_pin(old_pin) if tool == 'signal' else rpm_pin(tool, old_pin)
        old, new = old_pin['version'], pin['version']
        if version(new) < version(old):
            raise ValueError(f'{tool}: refusing downgrade {old} -> {new}')
        if new == old and pin != old_pin:
            raise ValueError(f'{tool}: upstream changed the existing pin; investigate manually')
        files = {path: json.dumps(pin, indent=2) + '\n'}
    print(f'{tool}: {old} -> {new}')
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tool', choices=TOOLS, action='append', help='refresh only this tool (repeatable; default: all tools)')
    parser.add_argument('--dry-run', action='store_true', help='show selection without network or writes')
    args = parser.parse_args()
    tools = list(dict.fromkeys(args.tool)) if args.tool else TOOLS
    if args.dry_run:
        print('PLAN ONLY: would refresh pins for ' + ', '.join(tools) + '; no network or writes.')
        return
    # Refuse unrelated work rather than overwriting it; never fetch/pull/commit.
    status = subprocess.check_output(['git', '-C', str(ROOT), 'status', '--porcelain'], text=True)
    if status:
        raise ValueError('Checkout must be clean before refreshing release pins; preserve/review your work first')
    origin = subprocess.check_output(['git', '-C', str(ROOT), 'remote', 'get-url', 'origin'], text=True).strip()
    if origin not in ('https://github.com/w3irdrobot/dotfiles.git', 'https://github.com/w3irdrobot/dotfiles',
                      'git@github.com:w3irdrobot/dotfiles.git'):
        raise ValueError('Unexpected origin; expected GitHub w3irdrobot/dotfiles')
    edits = {}
    for tool in tools:
        files = prepare(tool)
        # Native tools both contribute to history; merge those entries explicitly.
        history_path = ROOT / 'modules/native-release-history.json'
        if history_path in edits and history_path in files:
            merged = json.loads(edits[history_path])
            merged[tool] = json.loads(files[history_path])[tool]
            files[history_path] = json.dumps(merged, indent=2) + '\n'
        edits.update(files)
    # All downloads/verification complete before the first repository write.
    if subprocess.check_output(['git', '-C', str(ROOT), 'status', '--porcelain'], text=True):
        raise ValueError('Checkout changed during verification; no pins written')
    for path in edits:
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'Unexpected pin destination: {path}')
    originals = {path: path.read_text() for path in edits}
    try:
        for path, content in edits.items():
            if content != originals[path]:
                path.write_text(content)
    except Exception:
        for path, content in originals.items():
            if not path.is_symlink():
                path.write_text(content)
        raise
    print('Pins prepared only. Review git diff, then explicitly run dotfiles install with the desired selections.')
    print('No binaries installed, launchers changed, services restarted, or commits created.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, tarfile.TarError, subprocess.SubprocessError) as error:
        sys.exit(f'Release pin refresh failed: {error}')
