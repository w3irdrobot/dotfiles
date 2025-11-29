#!/usr/bin/env bash

set -euo pipefail

# shellcheck source=utils.sh
source "$SETUP_DIR/utils.sh"

log_info "Installing rust"
yay -Syu --needed \
    rustup

rustup install stable

yay -Syu --needed \
    cargo-binstall \
    cargo-generate \
    cargo-outdated \
    cargo-nextest \
    cargo-release
