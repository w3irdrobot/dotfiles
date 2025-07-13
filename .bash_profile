# shellcheck shell=bash

if [ -f ~/.bashrc ]; then
  # shellcheck source=./.bashrc
	source "$HOME/.bashrc"
fi

if [ -e /home/w3irdrobot/.nix-profile/etc/profile.d/nix.sh ]; then . /home/w3irdrobot/.nix-profile/etc/profile.d/nix.sh; fi # added by Nix installer
