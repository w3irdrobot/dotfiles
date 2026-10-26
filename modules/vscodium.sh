#!/usr/bin/env bash
set -euo pipefail

if [[ "${DEBUG:-0}" == "1" ]]; then
	set -x
fi

ROOT=$(cd -- "$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")/.." && pwd -P)
readonly ROOT
# shellcheck source=lib/dotfiles.sh
source "$ROOT/lib/dotfiles.sh"

preflight_kestrel_theme() {
	local directory=$HOME/.vscode-oss/extensions/w3irdrobot.kestrel-theme-0.0.1 file
	file=$directory
	while [[ $file != "$HOME" && $file != / ]]; do
		[[ ! -L $file && (! -e $file || -d $file) ]] || die "Conflicting Kestrel extension directory: $file"
		file=${file%/*}
		[[ -n $file ]] || file=/
	done
	for file in package.json themes/kestrel-color-theme.json; do
		if [[ -L $directory/$file ]]; then
			die "Kestrel still has legacy Stow links at $directory. Review/unlink the two old theme files and remove their empty directories before installing the local VSIX; see docs/packages.md. Nothing removed automatically."
		fi
	done
}

install_kestrel_theme() (
	local installed=$1 location temp directory=$HOME/.vscode-oss/extensions/w3irdrobot.kestrel-theme-0.0.1
	if grep -Fxiq w3irdrobot.kestrel-theme <<<"$installed"; then
		location=$(codium --locate-extension w3irdrobot.kestrel-theme) || die 'Could not locate the registered Kestrel extension.'
		[[ $location == /* && -d $location && ! -L $location ]] || die 'Kestrel extension registration has an unexpected/missing directory; inspect it manually.'
		python3 "$ROOT/scripts/build-vscodium-theme.py" --check-installed "$location" || die 'Existing Kestrel differs from the bundled theme; refusing to replace it automatically.'
		log 'Kestrel is registered with matching regular files; reusing it.'
		return 0
	fi
	[[ ! -e $directory ]] || die "Unregistered Kestrel directory already exists: $directory; inspect/remove it manually before installation."
	umask 077
	temp=$(mktemp -d)
	trap 'rm -rf -- "$temp"' EXIT
	python3 "$ROOT/scripts/build-vscodium-theme.py" --output "$temp/kestrel.vsix"
	codium --install-extension "$temp/kestrel.vsix" || die 'Installing the local Kestrel VSIX failed.'
	installed=$(codium --list-extensions) || die 'Could not verify Kestrel extension registration.'
	grep -Fxiq w3irdrobot.kestrel-theme <<<"$installed" || die 'Kestrel VSIX installation did not register the extension.'
	location=$(codium --locate-extension w3irdrobot.kestrel-theme) || die 'Could not locate installed Kestrel.'
	[[ $location == /* && -d $location && ! -L $location ]] || die 'Installed Kestrel directory is unavailable or unexpected.'
	python3 "$ROOT/scripts/build-vscodium-theme.py" --check-installed "$location" || die 'Installed Kestrel content did not match the bundled theme.'
)

install_extensions() {
	local root manifest installed extension
	root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
	manifest=$root/stow/vscodium/.config/VSCodium/extensions.txt
	[[ -f $manifest && ! -L $manifest ]] || die 'Missing repository extension manifest.'
	installed=$(codium --list-extensions) || die 'Could not list installed VSCodium extensions.'
	# Validate every identifier before making any changes.
	while IFS= read -r extension || [[ -n $extension ]]; do
		[[ $extension =~ ^[a-zA-Z0-9-]+\.[a-zA-Z0-9-]+$ ]] || die "Invalid extension identifier: $extension"
	done <"$manifest"
	install_kestrel_theme "$installed"
	while IFS= read -r extension || [[ -n $extension ]]; do
		if grep -Fxiq "$extension" <<<"$installed"; then
			continue
		fi
		codium --install-extension "$extension" || die "Installing VSCodium extension failed: $extension"
	done <"$manifest"
}

main() {
	[[ $# == 0 || ($# == 1 && $1 == --check) ]] || die 'Usage: vscodium.sh [--check]'
	check_platform
	preflight_kestrel_theme
	[[ ${1:-} != --check ]] || return 0
	command -v codium >/dev/null 2>&1 || die 'Install VSCodium first (codium command missing).'
	install_extensions
}

main "$@"
