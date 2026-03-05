#!/usr/bin/env bash

set -euo pipefail

# shellcheck source=utils.sh
source "$SETUP_DIR/utils.sh"

log_info "Installing hyprland and friends for desktop environment"
yay -Syu --needed \
    brightnessctl \
    grim \
    hypridle \
    hyprland \
    hyprlock \
    hyprpaper \
    hyprpolkitagent \
    hyprsunset \
    mako \
    slurp \
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

# https://adamhollister.com/hyprland-clamshell-mode
log_info "Setting up clamshell mode"
sudo mkdir -p /etc/systemd/logind.conf.d
sudo cp "$DOTFILES_DIR/clamshell.conf" /etc/systemd/logind.conf.d/

log_info "Enabling autologin"
sudo cp "$DOTFILES_DIR/autologin.conf" /etc/systemd/system/getty@tty1.service.d/autologin.conf
