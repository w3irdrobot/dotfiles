#!/usr/bin/env bash

set -euo pipefail

# shellcheck source=utils.sh
source "$SETUP_DIR/utils.sh"

log_info "Installing bluetooth tools"
yay -Syu --needed \
    bluez \
    bluetui

log_info "Disabling auto-enabling the bluetooth device on startup"
sudo sed -i.bak -E 's/^[#;\s]*AutoEnable\s*=.*/AutoEnable=false/' /etc/bluetooth/main.conf

log_info "Enabling bluetooth"
sudo systemctl enable --now bluetooth
