#!/usr/bin/env bash
set -euo pipefail

if [[ "${DEBUG:-0}" == "1" ]]; then
	set -x
fi

ROOT=$(cd -- "$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")/.." && pwd -P)
readonly ROOT
# shellcheck source=lib/dotfiles.sh
source "$ROOT/lib/dotfiles.sh"

preflight_ssh() {
	local directory=$ROOT/stow/ssh/.ssh file
	[[ -d $directory && ! -L $directory ]] || die 'Missing repository SSH directory or unexpected symlink.'
	[[ -O $directory ]] || die 'Repository SSH directory must be owned by the current user.'
	[[ -f $directory/config && ! -L $directory/config ]] || die 'Missing repository SSH config or unexpected symlink.'
	SSH_SOURCE_FILES=()
	shopt -s nullglob dotglob
	for file in "$directory"/*; do
		[[ -f $file && ! -L $file ]] || die "Unexpected SSH source entry: $file"
		[[ -O $file ]] || die "SSH source must be owned by the current user: $file"
		SSH_SOURCE_FILES+=("$file")
	done
	if [[ -e $HOME/.ssh || -L $HOME/.ssh ]]; then
		[[ -d $HOME/.ssh && ! -L $HOME/.ssh ]] || die "$HOME/.ssh must be a non-symlink directory."
		[[ -O $HOME/.ssh ]] || die "$HOME/.ssh must be owned by the current user."
	fi
}

restore_permissions() {
	# Only source-controlled config files, never live keys or credential files.
	# Git cannot retain 0600; Stow symlinks inherit their target's permissions.
	chmod 0700 -- "$ROOT/stow/ssh/.ssh" || die 'Could not restore repository SSH directory permissions.'
	chmod 0600 -- "${SSH_SOURCE_FILES[@]}" || die 'Could not restore repository SSH config permissions.'
	if [[ ! -e $HOME/.ssh ]]; then mkdir -m 0700 -- "$HOME/.ssh"; fi
	# Only this directory's mode changes. Never recurse into live keys or credentials.
	[[ -d $HOME/.ssh && ! -L $HOME/.ssh && -O $HOME/.ssh ]] || die "$HOME/.ssh changed during setup; refusing permission changes."
	chmod 0700 -- "$HOME/.ssh" || die 'Could not set ~/.ssh directory permissions.'
}

main() {
	[[ $# == 0 || ($# == 1 && $1 == --check) ]] || die 'Usage: ssh.sh [--check]'
	check_platform
	preflight_ssh
	[[ ${1:-} != --check ]] || return 0
	restore_permissions
}

main "$@"
