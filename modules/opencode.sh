#!/usr/bin/env bash
set -euo pipefail
if [[ "${DEBUG:-0}" == "1" ]]; then set -x; fi

ROOT=$(cd -- "$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")/.." && pwd -P)
readonly ROOT
# shellcheck source=lib/dotfiles.sh
source "$ROOT/lib/dotfiles.sh"

check_opencode_repository() {
	local metadata repository name version upstream
	metadata=$(LC_ALL=C pacman -Si -- opencode) || die 'Official Extra OpenCode metadata is unavailable; repair repository configuration/databases. No AUR fallback.'
	repository=$(printf '%s\n' "$metadata" | sed -n 's/^Repository[[:space:]]*:[[:space:]]*//p')
	name=$(printf '%s\n' "$metadata" | sed -n 's/^Name[[:space:]]*:[[:space:]]*//p')
	version=$(printf '%s\n' "$metadata" | sed -n 's/^Version[[:space:]]*:[[:space:]]*//p')
	[[ $repository == extra && $name == opencode ]] || die 'OpenCode must come from the official Extra repository under the name opencode.'
	upstream=$version
	if [[ $upstream == *:* ]]; then
		[[ $upstream =~ ^[0-9]+: ]] || die "Invalid OpenCode package version: $version"
		upstream=${upstream#*:}
	fi
	[[ $upstream =~ ^2\.[0-9][[:alnum:].+_-]*$ ]] || die "Extra OpenCode must be upstream V2; found version: $version"
}

check_native_opencode() {
	local version
	[[ -x /usr/bin/opencode ]] || die 'Native /usr/bin/opencode is missing; install the official Extra package first.'
	version=$(/usr/bin/opencode --version) || die 'Native OpenCode could not report its version; repair the package.'
	[[ $version =~ ^(opencode[[:space:]]+v)?2\.[0-9][[:alnum:].+_-]*$ ]] || die "Native OpenCode must report V2; found: $version"
}

main() {
	DRY_RUN=0
	[[ $# == 0 || ($# == 1 && $1 == --check) ]] || die 'Usage: opencode.sh [--check]'
	check_platform
	preflight_native_opencode_paths
	if [[ ${1:-} == --check ]]; then
		# Read-only local database inspection, not a synchronization or installation.
		check_opencode_repository
	else
		check_native_opencode
	fi
}
main "$@"
