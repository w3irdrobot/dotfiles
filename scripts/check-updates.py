#!/usr/bin/env python3
"""Read-only Bitwarden desktop release checks; never installs or changes pins."""

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
VERSION = re.compile(r"[0-9]{4}\.[0-9]{1,2}\.[0-9]+")
RELEASES = "https://api.github.com/repos/bitwarden/clients/releases"


def version_key(value):
    if not isinstance(value, str) or not VERSION.fullmatch(value):
        raise ValueError("Invalid Bitwarden desktop version")
    return tuple(int(part) for part in value.split("."))


def release_url(version):
    version_key(version)
    return f"https://github.com/bitwarden/clients/releases/tag/desktop-v{version}"


def artifact_url(version):
    version_key(version)
    return (
        f"https://github.com/bitwarden/clients/releases/download/desktop-v{version}/"
        f"Bitwarden-{version}-x86_64.rpm"
    )


def load_pin():
    pin = json.loads((ROOT / "modules/bitwarden-release.json").read_text())
    if not isinstance(pin, dict) or set(pin) != {"version", "url", "sha256"}:
        raise ValueError("Invalid Bitwarden release pin fields")
    version_key(pin["version"])
    if pin["url"] != artifact_url(pin["version"]):
        raise ValueError("Bitwarden pin must use the exact upstream desktop x86_64 RPM URL")
    if not isinstance(pin["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", pin["sha256"]):
        raise ValueError("Invalid Bitwarden RPM SHA256 pin")
    return pin


def fetch_page(page):
    request = urllib.request.Request(
        f"{RELEASES}?per_page=10&page={page}",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "dotfiles-release-check"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        # Public release metadata only; no tokens or application auth stores.
        return json.load(response)


def latest_desktop_release():
    # GitHub lists releases newest first. Do not mistake browser/CLI releases,
    # prereleases, or a missing desktop RPM for a successful up-to-date check.
    for page in range(1, 11):
        releases = fetch_page(page)
        if not isinstance(releases, list):
            raise ValueError("Unexpected GitHub releases response")
        if not releases:
            break
        for release in releases:
            if not isinstance(release, dict):
                raise ValueError("Invalid GitHub release record")
            if release.get("draft") is not False or release.get("prerelease") is not False:
                continue
            tag = release.get("tag_name", "")
            if not isinstance(tag, str) or not tag.startswith("desktop-v"):
                continue
            version = tag.removeprefix("desktop-v")
            if not VERSION.fullmatch(version):
                continue
            expected = f"Bitwarden-{version}-x86_64.rpm"
            assets = release.get("assets")
            if not isinstance(assets, list):
                raise ValueError("Stable desktop release has no valid asset list")
            matches = [asset for asset in assets if isinstance(asset, dict) and asset.get("name") == expected]
            if len(matches) != 1:
                raise ValueError("Latest stable desktop release has no unique x86_64 RPM asset")
            asset = matches[0]
            digest = asset.get("digest", "")
            if asset.get("browser_download_url") != artifact_url(version) or not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
                raise ValueError("Latest stable desktop RPM lacks the expected URL or SHA256 digest")
            return {"version": version, "url": release_url(version), "sha256": digest.removeprefix("sha256:")}
    raise ValueError("No stable desktop RPM found within ten release pages; check upstream manually")


def installed_version():
    if not shutil.which("rpm"):
        return None
    result = subprocess.run(
        ["rpm", "-q", "--qf", "%{VERSION}\n", "bitwarden"],
        capture_output=True, text=True, timeout=10, check=False,
    )
    if result.returncode == 1:
        return "not installed"
    if result.returncode != 0:
        raise ValueError("Could not inspect the installed Bitwarden RPM")
    version = result.stdout.strip()
    version_key(version)
    return version


def check_updates():
    pin = load_pin()
    installed = installed_version()
    published = latest_desktop_release()
    print(f"Bitwarden installed RPM: {installed if installed is not None else 'unknown (RPM unavailable)'}")
    print(f"Reviewed installation pin: {pin['version']}")
    print(f"Published stable desktop: {published['version']}")
    if version_key(published["version"]) > version_key(pin["version"]):
        print("Newer desktop release available: review/update modules/bitwarden-release.json, then rerun dotfiles install/update with Bitwarden selected.")
    elif published["version"] == pin["version"] and published["sha256"] != pin["sha256"]:
        raise ValueError("Upstream digest changed for the pinned version; investigate before installing")
    else:
        print("No newer published desktop version than the reviewed pin.")
    if installed not in (None, "not installed") and version_key(installed) < version_key(pin["version"]):
        print("Installed RPM is behind the reviewed pin; rerun dotfiles install/update with Bitwarden selected.")
    print(published["url"])
    print("Release check only: no downloads installed and no pins changed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    internal = parser.add_mutually_exclusive_group()
    internal.add_argument("--print-bitwarden-pin", action="store_true", help=argparse.SUPPRESS)
    internal.add_argument("--compare-bitwarden", metavar="VERSION", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.print_bitwarden_pin:
        pin = load_pin()
        print("|".join(pin[key] for key in ("version", "url", "sha256")))
    elif args.compare_bitwarden is not None:
        installed, pinned = version_key(args.compare_bitwarden), version_key(load_pin()["version"])
        print("older" if installed < pinned else "newer" if installed > pinned else "equal")
    else:
        check_updates()


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError, urllib.error.URLError) as error:
        sys.exit(f"Bitwarden release check failed: {error}")
