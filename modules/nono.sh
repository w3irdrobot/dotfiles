#!/usr/bin/env bash
set -euo pipefail
if [[ "${DEBUG:-0}" == "1" ]]; then set -x; fi

ROOT=$(cd -- "$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")/.." && pwd -P)
readonly ROOT
# shellcheck source=lib/dotfiles.sh
source "$ROOT/lib/dotfiles.sh"

check_destination() {
	local target=$1 parent
	parent=$(dirname "$target")
	while [[ $parent != "$HOME" && $parent != / ]]; do
		[[ ! -L $parent && (! -e $parent || -d $parent) ]] || die "Conflicting parent: $parent"
		parent=$(dirname "$parent")
	done
}

preflight_nono() {
	NONO_TARGET=$HOME/.local/share/dotfiles/nono/0.80.0/nono
	NONO_LINK=$HOME/.local/bin/nono
	local target=$NONO_TARGET link=$NONO_LINK expected actual
	check_destination "$target"
	check_destination "$link"
	if [[ -L $link ]]; then
		expected=$(realpath -m "$target")
		actual=$(realpath -m "$link")
		[[ $actual == "$expected" && -e $link ]] || die "Conflicting or dangling nono link: $link"
	elif [[ -e $link ]]; then
		die "Unmanaged nono binary: $link; inspect and move it yourself first."
	fi
	[[ ! -L $target && (! -e $target || -f $target) ]] || die "Conflicting nono binary destination: $target"
}

install_nono() (
	local scratch archive binary target=$NONO_TARGET link=$NONO_LINK
	scratch=$(mktemp -d)
	trap 'rm -rf -- "$scratch"' EXIT
	archive=$scratch/nono.tar.gz
	wget --https-only --output-document="$archive" \
		https://github.com/nolabs-ai/nono/releases/download/v0.80.0/nono-v0.80.0-x86_64-unknown-linux-gnu.tar.gz
	# Immutable release asset digest published by GitHub's release API.
	printf '%s  %s\n' 6da665b61999570c10dffc7da78828fe1fb7f3cac53319e505cebecaef17037f "$archive" | sha256sum --check --strict -
	# Extract only the expected member, never arbitrary archive paths.
	binary=$scratch/nono
	tar --extract --gzip --to-stdout --file="$archive" nono >"$binary"
	[[ -s $binary ]] || die 'Verified nono archive contained no executable.'
	if [[ -e $target ]]; then
		cmp --silent "$binary" "$target" || die "Existing nono binary differs from the pinned release: $target"
		[[ -x $target ]] || die "Existing managed nono binary is not executable: $target; repair its executable permissions before continuing."
	else
		mkdir -p "$(dirname "$target")"
		install -m 0755 "$binary" "$target"
	fi
	if [[ ! -L $link ]]; then
		mkdir -p "$(dirname "$link")"
		ln -s "$target" "$link"
	fi
)

main() {
	DRY_RUN=0
	[[ $# == 0 || ($# == 1 && $1 == --check) ]] || die 'Usage: nono.sh [--check]'
	check_platform
	preflight_nono
	[[ ${1:-} != --check ]] || return 0
	install_nono
	log 'nono installed. Registry setup is manual: nono pull nolabs-ai/opencode@0.4.0'
	log 'Existing nono profiles/packages are never overwritten by dotfiles setup.'
}
main "$@"
