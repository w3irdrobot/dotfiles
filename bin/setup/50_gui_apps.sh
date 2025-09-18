#!/usr/bin/env bash

set -euo pipefail

# shellcheck source=utils.sh
source "$SETUP_DIR/utils.sh"

log_info "Installing gui apps"
yay -Syu --needed \
    bitwarden-bin \
    brave-bin \
    thunderbird \
    chromium \
    discord \
    standardnotes-bin \
    signal-desktop
