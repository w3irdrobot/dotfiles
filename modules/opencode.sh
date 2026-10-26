#!/usr/bin/env bash
set -euo pipefail
if [[ "${DEBUG:-0}" == "1" ]]; then set -x; fi

ROOT=$(cd -- "$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")/.." && pwd -P)
readonly ROOT
# shellcheck source=lib/dotfiles.sh
source "$ROOT/lib/dotfiles.sh"

# Source: https://opencode.ai/v2/install, pinned native npm artifact, not npm install.
# Registry SHA512 integrity was matched before recording both SHA256 digests.
readonly OPENCODE_VERSION=2.1.4
readonly OPENCODE_URL=https://registry.npmjs.org/@opencode/cli-linux-x64-baseline/-/cli-linux-x64-baseline-2.1.4.tgz
readonly OPENCODE_ARCHIVE_SHA256=bfcb5c1931063e9835179ef4f1ee35eb3598d23ec77c31f0d5beedb45419fd25
readonly OPENCODE_BINARY_SHA256=ca9b3ee262e33bb4e7aa0e1230dc61086a474c8c8016b980081d0719712fd2e7

check_opencode_parent() {
	local parent
	parent=$(dirname "$1")
	while [[ $parent != "$HOME" && $parent != / ]]; do
		[[ ! -L $parent && (! -e $parent || -d $parent) ]] || die "Conflicting OpenCode parent: $parent"
		parent=$(dirname "$parent")
	done
}

verify_opencode_binary() {
	local target=$1
	[[ -f $target && ! -L $target && -x $target ]] || die "Pinned OpenCode binary is missing, non-executable, or a symlink: $target"
	printf '%s  %s\n' "$OPENCODE_BINARY_SHA256" "$target" | sha256sum --check --strict --status - || die "Pinned OpenCode binary checksum mismatch: $target; inspect and move it manually."
}

preflight_opencode() {
	OPENCODE_TARGET=$HOME/.local/share/dotfiles/opencode/2.1.4/opencode
	OPENCODE_LINK=$HOME/.local/bin/opencode
	check_opencode_parent "$OPENCODE_TARGET"
	check_opencode_parent "$OPENCODE_LINK"
	preflight_native_opencode_paths
	if [[ -e $OPENCODE_LINK && ! -L $OPENCODE_LINK ]]; then
		die "Unmanaged OpenCode launcher: $OPENCODE_LINK; inspect and move it manually."
	fi
	if [[ -e $OPENCODE_TARGET || -L $OPENCODE_TARGET ]]; then verify_opencode_binary "$OPENCODE_TARGET"; fi
}

setup_opencode() (
	umask 077
	preflight_opencode
	local target=$OPENCODE_TARGET link=$OPENCODE_LINK temp version
	if [[ ! -e $target ]]; then
		mkdir -p -- "${target%/*}" "${link%/*}"
		temp=$(mktemp -d "${target%/*}/.download.XXXXXXXX")
		trap 'rm -rf -- "$temp"' EXIT
		curl --proto '=https' --tlsv1.2 --fail --silent --show-error --location \
			--output "$temp/archive.tgz" "$OPENCODE_URL"
		printf '%s  %s\n' "$OPENCODE_ARCHIVE_SHA256" "$temp/archive.tgz" | sha256sum --check --strict --status - || die 'OpenCode archive checksum mismatch; nothing installed.'
		tar --extract --gzip --file "$temp/archive.tgz" --directory "$temp" \
			--no-same-owner --no-same-permissions package/bin/opencode
		[[ -f $temp/package/bin/opencode && ! -L $temp/package/bin/opencode ]] || die 'OpenCode archive did not contain a regular executable file.'
		chmod 0755 -- "$temp/package/bin/opencode"
		verify_opencode_binary "$temp/package/bin/opencode"
		version=$("$temp/package/bin/opencode" --version) || die 'Verified OpenCode binary could not report its version.'
		[[ $version == "$OPENCODE_VERSION" || $version == "opencode v$OPENCODE_VERSION" ]] || die "Verified OpenCode must report pinned V2 $OPENCODE_VERSION; found $version"
		# A same-filesystem hard link publishes atomically and refuses a new conflict.
		ln -- "$temp/package/bin/opencode" "$target"
	else
		log "Pinned OpenCode $OPENCODE_VERSION is already installed and verified."
	fi
	if [[ ! -L $link ]]; then
		mkdir -p -- "${link%/*}"
		ln -s -- "$target" "$link"
	fi
	log "Pinned upstream OpenCode $OPENCODE_VERSION ready: $link"
)

main() {
	DRY_RUN=0
	[[ $# == 0 || ($# == 1 && $1 == --check) ]] || die 'Usage: opencode.sh [--check]'
	check_platform
	preflight_opencode
	if [[ ${1:-} == --check ]]; then
		log "OpenCode $OPENCODE_VERSION destination preflight passed; no binary executed or downloaded."
	else
		setup_opencode
	fi
}
main "$@"
