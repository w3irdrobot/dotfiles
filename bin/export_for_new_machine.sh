#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd)
DOTFILES_DIR=$(realpath "$SCRIPT_DIR/..")

if [[ $# -ne 1 ]]; then
	echo "Usage: $0 <export_base>"
	exit 1
fi

EXPORT_BASE="$1"
EXPORT_DIR="$EXPORT_BASE/machine_export"

mkdir -p "$EXPORT_DIR"

# export private GPG keys and their corresponding public keys
GPG_DIR="$EXPORT_DIR/gpg"
mkdir -p "$GPG_DIR"

# Export secret keys
gpg --export-secret-keys --armor > "$GPG_DIR/private-keys.asc"

# Export public keys
gpg --export --armor > "$GPG_DIR/public-keys.asc"

# Export trust database
gpg --export-ownertrust > "$GPG_DIR/trustdb.txt"

# Backup dracula-pro
DRACULA_PRO_DIR="$EXPORT_DIR/dracula-pro"
cp -r "$DOTFILES_DIR/dracula-pro" "$DRACULA_PRO_DIR"

# Backup ssh keys
SSH_DIR="$EXPORT_DIR/ssh"
cp -r "$HOME/.ssh" "$SSH_DIR"
rm "$SSH_DIR"/known_hosts*

# Backup sparrow wallets
SPARROW_DIR="$EXPORT_DIR/sparrow"
cp -r "$HOME/.sparrow" "$SPARROW_DIR"

echo "When setting up the new machine, make sure to import the output directory using"
echo "the MACHINE_EXPORT environment variable."
