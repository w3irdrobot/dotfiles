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

log_info "Adding user to docker group"
sudo groupadd -f docker
sudo usermod -aG docker "$USER"
