#!/usr/bin/env bash
set -euo pipefail

if [[ "${DEBUG:-0}" == "1" ]]; then
	set -x
fi

die() {
	printf 'vscodium: %s\n' "$*" >&2
	exit 1
}

check_platform() {
	[[ $(uname -s) == Linux && $(uname -m) == x86_64 ]] || die 'Only x86_64 Linux is supported.'
	[[ -r /etc/os-release ]] || die 'Missing /etc/os-release.'
	local distro
	distro=$(sed -n 's/^ID=//p' /etc/os-release)
	distro=${distro//\"/}
	distro=${distro//\'/}
	[[ $distro == arch || $distro == manjaro ]] || die 'Only Arch and Manjaro are supported.'
	((EUID != 0)) || die 'Run as your regular user, not root.'
}

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
	while IFS= read -r extension || [[ -n $extension ]]; do
		if grep -Fxiq "$extension" <<<"$installed"; then
			continue
		fi
		codium --install-extension "$extension" || die "Installing VSCodium extension failed: $extension"
	done <"$manifest"
}

main() {
	(($# == 0)) || die 'This setup module takes no arguments.'
	check_platform
	command -v codium >/dev/null 2>&1 || die 'Install VSCodium first (codium command missing).'
	install_extensions
}

main "$@"
