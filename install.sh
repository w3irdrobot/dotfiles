#!/usr/bin/env bash
# Download and review https://dotfiles.w3ird.tech/install.sh, then run bash install.sh.
set -euo pipefail
if [[ "${DEBUG:-0}" == "1" ]]; then set -x; fi

readonly REPOSITORY=https://github.com/w3irdrobot/dotfiles.git

DOTFILES_PHASE='Bootstrap argument validation'
log() { printf 'dotfiles bootstrap: %s\n' "$*" >&2; }
phase() {
	DOTFILES_PHASE=$1
	log "$1"
}
report_exit() {
	local status=$1
	if ((status != 0)); then printf 'dotfiles bootstrap: Failure during %s (exit %d).\n' "$DOTFILES_PHASE" "$status" >&2; fi
}
trap 'report_exit "$?"' EXIT

die() {
	printf 'dotfiles: %s\n' "$*" >&2
	exit 1
}
run() {
	printf '+ ' >&2
	printf '%q ' "$@" >&2
	printf '\n' >&2
	if ((! dry_run)); then "$@"; fi
}

check_platform() {
	[[ $(uname -s) == Linux && $(uname -m) == x86_64 ]] || die 'Only x86_64 Linux is supported.'
	[[ -r /etc/os-release ]] || die 'Missing /etc/os-release.'
	local distro version
	distro=$(sed -n 's/^ID=//p' /etc/os-release)
	distro=${distro//\"/}
	distro=${distro//\'/}
	version=$(sed -n 's/^VERSION_ID=//p' /etc/os-release)
	version=${version//\"/}
	version=${version//\'/}
	[[ $distro == fedora && $version == 44 ]] || die 'Only Fedora KDE Plasma Desktop 44 is supported.'
	[[ ! -e /run/ostree-booted ]] || die 'Fedora Atomic desktops are unsupported; use the regular KDE Plasma Desktop installation.'
	((EUID != 0)) || die 'Run as your regular user, not root.'
	[[ ${XDG_CONFIG_HOME:-$HOME/.config} == "$HOME/.config" ]] || die 'Custom XDG_CONFIG_HOME is unsupported; configs deploy to ~/.config. No setup changes applied.'
}

check_checkout() {
	[[ ! -L $destination && -d $destination/.git ]] || die "Not an ordinary repository checkout: $destination"
	local origin branch
	origin=$(git -C "$destination" remote get-url origin)
	case $origin in
	"$REPOSITORY" | "${REPOSITORY%.git}" | git@github.com:w3irdrobot/dotfiles.git) ;;
	*) die 'Unexpected origin; expected GitHub w3irdrobot/dotfiles. Inspect origin locally before retrying; refusing update.' ;;
	esac
	[[ -z $(git -C "$destination" status --porcelain --untracked-files=all) ]] || die 'Checkout is dirty; save your work before updating.'
	branch=$(git -C "$destination" symbolic-ref --quiet --short HEAD) || die 'Detached HEAD; select the intended branch yourself.'
	[[ $branch == "$ref" ]] || die "Checkout is on $branch, not $ref; refusing to switch branches."
	run git -C "$destination" fetch origin "refs/heads/$ref:refs/remotes/origin/$ref"
	if ((dry_run)); then
		printf 'Would verify fast-forward ancestry before updating.\n' >&2
	else
		git -C "$destination" merge-base --is-ancestor HEAD "refs/remotes/origin/$ref" || die 'Local checkout is ahead or diverged; refusing update.'
	fi
	run git -C "$destination" merge --ff-only --no-overwrite-ignore "refs/remotes/origin/$ref"
}

# Keep these standalone PATH guards identical to lib/dotfiles.sh; the public
# bootstrap cannot source checkout files before Git has been installed.
preflight_native_opencode_paths() {
	local remaining=${PATH-} directory candidate more
	# Shell startup prepends this directory even when the installer PATH omits it.
	check_native_opencode_path "$HOME/.local/bin/opencode" 1
	while :; do
		more=0
		if [[ $remaining == *:* ]]; then
			directory=${remaining%%:*}
			remaining=${remaining#*:}
			more=1
		else
			directory=$remaining
		fi
		# Empty entries mean the current directory, including a trailing colon.
		candidate=${directory:-.}/opencode
		check_native_opencode_path "$candidate" 0
		((more)) || break
	done
}

check_native_opencode_path() {
	local candidate=$1 explicit=$2 actual native
	local managed=$HOME/.local/share/dotfiles/opencode/2.1.4/opencode
	[[ -e $candidate || -L $candidate ]] || return 0
	[[ -e $candidate ]] || die "Dangling OpenCode shadow: $candidate; inspect and move it manually. Leaving it unchanged."
	# Ordinary non-executable files cannot be dispatched through PATH. Symlinks
	# and the explicitly protected startup path still require inspection.
	if ((! explicit)) && [[ ! -L $candidate && (! -f $candidate || ! -x $candidate) ]]; then return 0; fi
	actual=$(realpath -m -- "$candidate") || die "Could not resolve OpenCode shadow: $candidate; inspect it manually. Leaving it unchanged."
	native=$(realpath -m -- "$managed") || die 'Could not resolve managed OpenCode path; inspect it manually.'
	[[ $actual == "$native" ]] || die "Unmanaged OpenCode shadows the pinned binary: $candidate; inspect and move it manually. Leaving it unchanged."
}

bootstrap_git() {
	preflight_native_opencode_paths
	phase 'Git prerequisites: installing Fedora Git and CA certificates only'
	# Dependency-only bootstrap, not a system upgrade. The checkout owns snapshot
	# protection and pinned OpenCode validation for subsequent setup.
	run sudo dnf --refresh install git ca-certificates
}

main() {
	local destination="$HOME/projects/github.com/w3irdrobot/dotfiles" ref=master dry_run=0
	local -a setup_args=()
	while (($#)); do
		case $1 in
		--ref)
			(($# >= 2)) || die '--ref needs a branch'
			ref=$2
			shift 2
			;;
		--dry-run)
			dry_run=1
			setup_args+=(--dry-run)
			shift
			;;
		--groups)
			(($# >= 2)) || die '--groups needs a value'
			setup_args+=(--groups "$2")
			shift 2
			;;
		--docker-group)
			setup_args+=(--docker-group)
			shift
			;;
		--modules)
			(($# >= 2)) || die '--modules needs a value'
			[[ -n $2 ]] || die '--modules needs a nonempty value'
			setup_args+=(--modules "$2")
			shift 2
			;;
		--help | -h)
			printf 'Usage: install.sh [--ref BRANCH] [--groups core,ai,desktop] [--modules NAME[,NAME]] [--dry-run] [--docker-group]\n'
			return
			;;
		*) die "Unknown argument: $1" ;;
		esac
	done
	phase 'Bootstrap platform validation: Fedora 44 x86_64, regular user'
	check_platform
	log 'Platform validation passed.'
	[[ $ref != -* ]] || die 'Invalid branch.'
	phase 'Git prerequisites: checking the available clone tools'
	if ! command -v git >/dev/null; then
		bootstrap_git
		if ((dry_run)); then
			printf 'Would clone %s at %s and run bin/setup.\n' "$REPOSITORY" "$ref" >&2
			phase 'PLAN ONLY: bootstrap dry-run finished; no changes applied'
			printf 'PLAN ONLY: prerequisites, checkout clone and setup dispatch were not performed.\n'
			return
		fi
	fi
	log 'Git clone tooling is available.'
	git check-ref-format "refs/heads/$ref" || die 'Invalid branch.'
	if [[ -e $destination || -L $destination ]]; then
		phase 'Checkout update: verifying origin, cleanliness and fast-forward safety'
		check_checkout
	else
		phase 'Checkout clone: creating the public HTTPS checkout'
		run mkdir -p "$(dirname "$destination")"
		run git clone --branch "$ref" --single-branch "$REPOSITORY" "$destination"
		if ((dry_run)); then
			printf 'Would run bin/setup in the new checkout.\n' >&2
			phase 'PLAN ONLY: bootstrap dry-run finished; no changes applied'
			printf 'PLAN ONLY: checkout clone and setup dispatch were not performed.\n'
			return
		fi
	fi
	[[ -f $destination/bin/setup ]] || die 'Selected ref has no bin/setup.'
	phase 'Setup dispatch: running the selected checkout entrypoint'
	bash "$destination/bin/setup" "${setup_args[@]}"
	if ((dry_run)); then
		phase 'PLAN ONLY: bootstrap dispatch preview finished; no changes applied'
	else
		phase 'Complete: bootstrap checkout and setup dispatch'
	fi
}
main "$@"
