#!/usr/bin/env bash

set -euo pipefail

# shellcheck source=utils.sh
source "$SETUP_DIR/utils.sh"

# install yay
if ! command -v yay &> /dev/null
then
    log_info "Installing yay"
    (
        cd "$(mktemp -d)"
        sudo pacman -S --needed git base-devel
        git clone https://aur.archlinux.org/yay.git
        cd yay
        makepkg -si
    )
fi

log_info "Installing base tools"
yay -Syu --needed \
    jq \
    just \
    man-db \
    pacman-contrib \
    unzip \
    zip

log_info "Enabling paccache and ssh-agent"
sudo systemctl enable --now paccache.timer
systemctl --user enable --now ssh-agent.socket
