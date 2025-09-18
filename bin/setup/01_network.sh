#!/usr/bin/env bash

set -euo pipefail

# shellcheck source=utils.sh
source "$SETUP_DIR/utils.sh"

# install network manager
log_info "Installing network manager"
yay -Syu --needed \
    mullvad-vpn-bin \
    networkmanager \
    tor

log_info "Enabling network manager"
sudo systemctl enable --now \
    NetworkManager \
    systemd-resolved \
    tor
