#!/usr/bin/env bash
# Fresh-machine entry point:
#   curl -fsSL https://dotfiles.w3ird.tech/install.sh | bash
#   curl -fsSL https://dotfiles.w3ird.tech/install.sh | bash -s -- [--ref BRANCH] [bootstrap flags]
# Clones this repository (HTTPS, no SSH keys needed) and runs bootstrap.sh.
set -euo pipefail

if [[ "${DEBUG:-0}" == "1" ]]; then
	set -x
fi

readonly REPOSITORY=https://github.com/w3irdrobot/dotfiles.git
readonly DESTINATION=$HOME/projects/github.com/w3irdrobot/dotfiles

log() { printf 'dotfiles: %s\n' "$*" >&2; }
die() {
	log "$*"
	exit 1
}

main() {
	local ref=master
	local -a passthrough=()
	while (($#)); do
		case $1 in
		--ref)
			(($# >= 2)) || die '--ref needs a branch name.'
			ref=$2
			shift
			;;
		*) passthrough+=("$1") ;;
		esac
		shift
	done
	((EUID != 0)) || die 'Run as your regular user, not root.'
	# Piped installs read the script from stdin, so prompts must use the terminal.
	{ : </dev/tty; } 2>/dev/null || die 'A terminal is required for package prompts.'

	if ! command -v git >/dev/null; then
		log 'Installing git'
		# shellcheck disable=SC2024 # The redirect is for dnf's prompt, not a privileged read.
		sudo dnf install git </dev/tty
	fi
	if [[ -d $DESTINATION/.git ]]; then
		local branch
		branch=$(git -C "$DESTINATION" branch --show-current)
		[[ $branch == "$ref" ]] || die "$DESTINATION is on '$branch', not '$ref'; switch it or pass --ref $branch."
		log "Updating existing checkout: $DESTINATION"
		# Fast-forward only: local commits or conflicting edits stop the install instead of being lost.
		git -C "$DESTINATION" pull --ff-only --no-rebase origin "$ref" ||
			die "Could not fast-forward $DESTINATION; sort out its local changes and rerun."
	else
		log "Cloning $ref into $DESTINATION"
		mkdir -p -- "${DESTINATION%/*}"
		git clone --branch "$ref" "$REPOSITORY" "$DESTINATION"
	fi
	exec bash "$DESTINATION/bootstrap.sh" "${passthrough[@]}" </dev/tty
}

main "$@"
