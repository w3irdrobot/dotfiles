#!/usr/bin/env python3
"""Validate module package metadata; remote lookups require explicit --network."""

import argparse
from pathlib import Path
import re
import sys
import shutil
import subprocess

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
            if not separator or key not in ("group", "packages", "default", "manual"):
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


def validate_remote(packages):
    if not shutil.which("dnf"):
        raise ValueError("Network package validation requires Fedora 44 with DNF5 and the selected repos configured")
    result = subprocess.run(
        ["dnf", "--refresh", "repoquery", "--available", "--arch=x86_64,noarch", "--queryformat", "%{name}\\n", *sorted(packages)],
        check=True, text=True, capture_output=True, timeout=180,
    )
    missing = packages - set(result.stdout.splitlines())
    if missing:
        raise ValueError("Packages absent from configured Fedora RPM sources: " + ", ".join(sorted(missing)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--network", action="store_true", help="query configured Fedora RPM sources using DNF5 (metadata only)")
    args = parser.parse_args()
    packages = metadata()
    if not packages:
        raise ValueError("No packages= package metadata found; check metadata interface")
    if args.network:
        validate_remote(packages)
    print(
        f"Validated {len(packages)} package names"
        + (" against configured Fedora RPM metadata" if args.network else " (syntax only; no network)")
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        sys.exit(str(error))
