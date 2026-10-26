#!/usr/bin/env bash
set -euo pipefail

if [[ "${DEBUG:-0}" == "1" ]]; then
	set -x
fi

ROOT=$(cd -- "$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")/.." && pwd -P)
readonly ROOT
# shellcheck source=lib/dotfiles.sh
source "$ROOT/lib/dotfiles.sh"

build_theme_cache() {
	local root source
	root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
	source=$root/stow/bat/.config/bat
	[[ -f $source/themes/Kestrel.tmTheme && ! -L $source/themes/Kestrel.tmTheme ]] || die 'Missing repository Kestrel theme.'
	# Setup precedes Stow: load themes from the repository, cache in bat's normal
	# user cache. The source is the parent of themes/, not themes/ itself.
	BAT_CONFIG_PATH=/dev/null bat cache --build --source "$source" || die 'Building the bat theme cache failed.'
}

main() {
	(($# == 0)) || die 'This setup module takes no arguments.'
	check_platform
	command -v bat >/dev/null 2>&1 || die 'Install the bat package first.'
	build_theme_cache
}

main "$@"
