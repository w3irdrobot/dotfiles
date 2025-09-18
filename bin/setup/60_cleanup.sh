#!/usr/bin/env bash

set -euo pipefail

# shellcheck source=utils.sh
source "$SETUP_DIR/utils.sh"

log_info "Stopping unneeded services"
sudo systemctl disable --now \
    iwd \
    systemd-networkd
