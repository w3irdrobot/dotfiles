#!/usr/bin/env bash

set -euo pipefail

# shellcheck source=utils.sh
source "$SETUP_DIR/utils.sh"

log_info "Installing docker"
yay -Syu --needed \
    docker \
    docker-compose \
    lazydocker

sudo systemctl enable --now \
    docker.socket
