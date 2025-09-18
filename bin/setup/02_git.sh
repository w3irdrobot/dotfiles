#!/usr/bin/env bash

set -euo pipefail

# shellcheck source=utils.sh
source "$SETUP_DIR/utils.sh"

log_info "Installing git tools"
yay -Syu --needed \
    diff-so-fancy \
    git \
    lazygit \
    nodejs-commitizen
