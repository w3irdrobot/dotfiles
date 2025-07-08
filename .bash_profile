# shellcheck shell=bash

if [ -f ~/.bashrc ]; then
  # shellcheck source=./.bashrc
	source "$HOME/.bashrc"
fi
source "/home/alexsears/.rover/env"

if [ -e /home/alexsears/.nix-profile/etc/profile.d/nix.sh ]; then . /home/alexsears/.nix-profile/etc/profile.d/nix.sh; fi # added by Nix installer

. "$HOME/.cargo/env"

if [ -e /home/w3irdrobot/.nix-profile/etc/profile.d/nix.sh ]; then . /home/w3irdrobot/.nix-profile/etc/profile.d/nix.sh; fi # added by Nix installer
