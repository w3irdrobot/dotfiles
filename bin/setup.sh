#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
SETUP_DIR=$(realpath "$SCRIPT_DIR/setup")
DOTFILES_DIR=$(realpath "$SCRIPT_DIR/..")

export SCRIPT_DIR
export SETUP_DIR
export DOTFILES_DIR

# shellcheck source=setup/utils.sh
source "$SETUP_DIR/utils.sh"

"$SETUP_DIR/00_base_tools.sh"
"$SETUP_DIR/01_network.sh"
"$SETUP_DIR/02_git.sh"
"$SETUP_DIR/03_bluetooth.sh"
"$SETUP_DIR/10_terminal.sh"
"$SETUP_DIR/20_desktop.sh"
"$SETUP_DIR/21_yazi.sh"
"$SETUP_DIR/30_editors.sh"
"$SETUP_DIR/31_languages.sh"
"$SETUP_DIR/40_docker.sh"
"$SETUP_DIR/50_gui_apps.sh"
"$SETUP_DIR/60_cleanup.sh"

log_info "Installing stow and linking dotfiles"
yay -Syu --needed stow
just stow

