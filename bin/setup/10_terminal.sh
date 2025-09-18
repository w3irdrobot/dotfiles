#!/usr/bin/env bash

set -euo pipefail

# shellcheck source=utils.sh
source "$SETUP_DIR/utils.sh"

log_info "Installing terminal and common tools"
yay -Syu --needed \
    bash-completion \
    bat \
    eza \
    fd \
    fzf \
    kitty \
    ripgrep \
    starship \
    xclip \
    zoxide
