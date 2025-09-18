#!/usr/bin/env bash

set -euo pipefail

# shellcheck source=utils.sh
source "$SETUP_DIR/utils.sh"

log_info "Installing hyprland and friends for desktop environment"
yay -Syu --needed \
    brightnessctl \
    hypridle \
    hyprland \
    hyprlock \
    hyprpaper \
    hyprpolkitagent \
    hyprsunset \
    mako \
    ttf-jetbrains-mono-nerd \
    uwsm \
    waybar \
    xdg-dekstop-portal-gtk \
    xdg-dekstop-portal-hyprland

systemctl --user enable --now \
    hypridle \
    hyprpaper \
    hyprpolkitagent \
    hyprsunset \
    mako \
    waybar

log_info "Enabling autologin"
sudo cp "$DOTFILES_DIR/autologin.conf" /etc/systemd/system/getty@tty1.service.d/autologin.conf
