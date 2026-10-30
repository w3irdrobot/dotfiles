#!/usr/bin/env bash
set -euo pipefail

if [[ "${DEBUG:-0}" == "1" ]]; then
	set -x
fi

ROOT=$(cd -- "$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")/.." && pwd -P)
readonly ROOT
# shellcheck source=lib/dotfiles.sh
source "$ROOT/lib/dotfiles.sh"

main() {
	(($# == 0)) || die 'This setup module takes no arguments.'
	check_platform
	command -v ghostty >/dev/null 2>&1 || die 'Install the ghostty package first.'
	command -v kwriteconfig6 >/dev/null 2>&1 || die 'Install the kf6-kconfig package first.'
	# Merge only the terminal preference; never Stow the machine's kdeglobals.
	kwriteconfig6 --file kdeglobals --group General --key TerminalApplication ghostty
	kwriteconfig6 --file kdeglobals --group General --key TerminalService com.mitchellh.ghostty.desktop
}

main "$@"
