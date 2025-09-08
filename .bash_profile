# shellcheck shell=bash

set -e

if [ -f ~/.bashrc ]; then
  # shellcheck source=./.bashrc
	source "$HOME/.bashrc"
fi

if uwsm check may-start; then
  exec uwsm start hyprland.desktop
fi
