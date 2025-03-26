#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <path-to-machine-export-dir>"
    exit 1
fi

EXPORT_DIR="$1/machine_export"

if [[ ! -d "$EXPORT_DIR" ]]; then
    echo "Error: Machine export directory not found at $EXPORT_DIR"
    exit 1
fi

# Import GPG keys
GPG_DIR="$EXPORT_DIR/gpg"
if [[ -d "$GPG_DIR" ]]; then
    # Import private keys
    if [[ -f "$GPG_DIR/private-keys.asc" ]]; then
        gpg --import "$GPG_DIR/private-keys.asc"
    fi

    # Import public keys
    if [[ -f "$GPG_DIR/public-keys.asc" ]]; then
        gpg --import "$GPG_DIR/public-keys.asc"
    fi

    # Import trust database
    if [[ -f "$GPG_DIR/trustdb.txt" ]]; then
        gpg --import-ownertrust "$GPG_DIR/trustdb.txt"
    fi
fi

# Import dracula-pro themes
DRACULA_PRO_DIR="$EXPORT_DIR/dracula-pro"
if [[ -d "$DRACULA_PRO_DIR" ]]; then
    DOTFILES_DIR=$(cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd)/..
    rm -rf "$DOTFILES_DIR/dracula-pro"
    cp -r "$DRACULA_PRO_DIR" "$DOTFILES_DIR/"
fi

# Import SSH keys
SSH_DIR="$EXPORT_DIR/ssh"
if [[ -d "$SSH_DIR" ]]; then
    mkdir -p "$HOME/.ssh"
    cp -r "$SSH_DIR/"* "$HOME/.ssh/"
    chmod 700 "$HOME/.ssh"
    find "$HOME/.ssh" -type f -exec chmod 600 {} \;
fi

# Import Sparrow wallets
SPARROW_DIR="$EXPORT_DIR/sparrow"
if [[ -d "$SPARROW_DIR" ]]; then
    mkdir -p "$HOME/.sparrow"
    cp -r "$SPARROW_DIR/" "$HOME/.sparrow/"
fi

echo "Machine data imported successfully"
