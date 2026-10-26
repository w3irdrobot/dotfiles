#!/usr/bin/env python3
"""Build the repository's Kestrel VSIX locally using only the Python standard library."""

import argparse
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
THEME = ROOT / 'modules/vscodium-theme'
FILES = ('package.json', 'themes/kestrel-color-theme.json')


def theme_files():
    if THEME.is_symlink() or (THEME / 'themes').is_symlink():
        raise ValueError('Bundled theme directories must not be symlinks')
    files = {}
    for name in FILES:
        path = THEME / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'Missing/unsafe bundled theme source: {name}')
        files[name] = path.read_bytes()
    package = json.loads(files['package.json'])
    if not isinstance(package, dict) or package.get('publisher') != 'w3irdrobot' or package.get('name') != 'kestrel-theme':
        raise ValueError('Unexpected bundled theme identity')
    if package.get('version') != '0.0.1':
        raise ValueError('Review the version/path checks when updating the bundled theme version')
    if package.get('contributes', {}).get('themes') != [{
        'label': 'Kestrel', 'uiTheme': 'vs-dark', 'path': './themes/kestrel-color-theme.json'
    }]:
        raise ValueError('Unexpected bundled theme contribution')
    json.loads(files['themes/kestrel-color-theme.json'])
    return package, files


def vsix_manifest(package):
    namespace = 'http://schemas.microsoft.com/developer/vsx-schema/2011'
    ET.register_namespace('', namespace)

    def node(parent, name, attributes=None, text=None):
        child = ET.SubElement(parent, f'{{{namespace}}}{name}', attributes or {})
        child.text = text
        return child

    root = ET.Element(f'{{{namespace}}}PackageManifest', {'Version': '2.0.0'})
    metadata = node(root, 'Metadata')
    node(metadata, 'Identity', {'Id': package['name'], 'Version': package['version'],
                              'Publisher': package['publisher'], 'Language': 'en-US'})
    node(metadata, 'DisplayName', text=package['displayName'])
    node(metadata, 'Description', {'{http://www.w3.org/XML/1998/namespace}space': 'preserve'}, package['description'])
    node(metadata, 'Categories', text='Themes')
    properties = node(metadata, 'Properties')
    node(properties, 'Property', {'Id': 'Microsoft.VisualStudio.Code.Engine', 'Value': package['engines']['vscode']})
    installation = node(root, 'Installation')
    node(installation, 'InstallationTarget', {'Id': 'Microsoft.VisualStudio.Code'})
    node(root, 'Dependencies')
    assets = node(root, 'Assets')
    node(assets, 'Asset', {'Type': 'Microsoft.VisualStudio.Code.Manifest',
                         'Path': 'extension/package.json', 'Addressable': 'true'})
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def build(destination):
    package, files = theme_files()
    types = b'''<?xml version="1.0" encoding="utf-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="json" ContentType="application/json"/>
  <Default Extension="vsixmanifest" ContentType="text/xml"/>
</Types>'''
    entries = {'[Content_Types].xml': types, 'extension.vsixmanifest': vsix_manifest(package)}
    entries.update({f'extension/{name}': data for name, data in files.items()})
    # Never replace an existing VSIX. Fixed metadata makes identical builds match.
    with zipfile.ZipFile(destination, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)


def check_installed(directory):
    if directory.is_symlink() or (directory / 'themes').is_symlink():
        raise ValueError('Installed Kestrel directories must not be symlinks')
    _, files = theme_files()
    for name, expected in files.items():
        path = directory / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'Installed Kestrel content differs or is symlinked: {name}; review it manually')
        actual = path.read_bytes()
        if name == 'package.json':
            # VSCodium adds installation metadata to the extracted manifest.
            installed_manifest = json.loads(actual)
            if not isinstance(installed_manifest, dict):
                raise ValueError('Installed Kestrel manifest is not an object')
            installed_manifest.pop('__metadata', None)
            matches = installed_manifest == json.loads(expected)
        else:
            matches = actual == expected
        if not matches:
            raise ValueError(f'Installed Kestrel content differs: {name}; review it manually')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--output', type=Path)
    mode.add_argument('--check-installed', type=Path)
    args = parser.parse_args()
    if args.output is not None:
        build(args.output)
    else:
        check_installed(args.check_installed)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as error:
        sys.exit(f'Kestrel VSIX: {error}')
