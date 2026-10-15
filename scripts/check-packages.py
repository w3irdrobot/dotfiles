#!/usr/bin/env python3
"""Validate module package metadata; remote lookups require explicit --network."""

import argparse
import json
from pathlib import Path
import re
import sys
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9@._+-]*$")


def metadata():
    paths = sorted((ROOT / "modules").glob("*.conf"))
    if not paths:
        raise ValueError("No modules/*.conf metadata found")
    packages = set()
    for path in paths:
        fields = {}
        for number, line in enumerate(path.read_text().splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, separator, value = line.partition("=")
            if not separator or key not in ("group", "packages", "default"):
                raise ValueError(f"{path.name}:{number}: expected key=value data")
            if key in fields:
                raise ValueError(f"{path.name}:{number}: duplicate {key}")
            fields[key] = value
            if key == "packages":
                for package in value.split():
                    if not PACKAGE.fullmatch(package):
                        raise ValueError(f"{path.name}:{number}: invalid package {package!r}")
                    packages.add(package)
        if not {"group", "packages"} <= set(fields):
            raise ValueError(f"{path.name}: requires group and packages")
        if fields["group"] not in ("core", "ai", "desktop", "cloud", "bitcoin", "hardware"):
            raise ValueError(f"{path.name}: invalid group")
        if fields.get("default", "true") not in ("true", "false"):
            raise ValueError(f"{path.name}: default must be true or false")
    return packages


def get_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": "dotfiles-package-validation/1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def validate_remote(packages):
    aur = []
    for package in sorted(packages):
        # Omitting the architecture filter includes Arch's architecture-independent
        # packages. Still reject results for architectures this installer cannot use.
        query = urllib.parse.urlencode({"name": package})
        data = get_json("https://archlinux.org/packages/search/json/?" + query)
        if not any(
            item["pkgname"] == package and item.get("arch") in ("x86_64", "any")
            for item in data.get("results", [])
        ):
            aur.append(package)
    missing = set()
    for start in range(0, len(aur), 50):
        batch = aur[start:start + 50]
        query = urllib.parse.urlencode([("arg[]", name) for name in batch])
        data = get_json("https://aur.archlinux.org/rpc/v5/info?" + query)
        if data.get("type") == "error":
            raise ValueError(f"AUR RPC error: {data.get('error')}")
        found = {item["Name"] for item in data.get("results", [])}
        missing.update(set(batch) - found)
    if missing:
        raise ValueError(
            "Packages absent from Arch (x86_64/any) and AUR: " + ", ".join(sorted(missing))
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--network", action="store_true", help="query Arch and AUR over HTTPS")
    args = parser.parse_args()
    packages = metadata()
    if not packages:
        raise ValueError("No packages= package metadata found; check metadata interface")
    if args.network:
        validate_remote(packages)
    print(
        f"Validated {len(packages)} package names"
        + (" against Arch/AUR metadata" if args.network else " (syntax only; no network)")
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError) as error:
        sys.exit(str(error))
