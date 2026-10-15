#!/usr/bin/env bash
# Public bootstrap: wget -qO- https://dotfiles.w3ird.tech/install.sh | bash
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
	local distro
	distro=$(sed -n 's/^ID=//p' /etc/os-release)
	distro=${distro//\"/}
	distro=${distro//\'/}
	[[ $distro == arch || $distro == manjaro ]] || die 'Only Arch and Manjaro are supported.'
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
	if ((dry_run)); then
		run git -C "$destination" fetch origin "refs/heads/$ref:refs/remotes/origin/$ref"
		printf 'Would verify fast-forward ancestry before updating.\n' >&2
	else
		git -C "$destination" fetch origin "refs/heads/$ref:refs/remotes/origin/$ref"
		git -C "$destination" merge-base --is-ancestor HEAD "refs/remotes/origin/$ref" || die 'Local checkout is ahead or diverged; refusing update.'
	fi
	run git -C "$destination" merge --ff-only --no-overwrite-ignore "refs/remotes/origin/$ref"
}

bootstrap_git() {
	local guard_opencode=0 query_status metadata repository name version
	local -a packages=(git ca-certificates)
	if ((dry_run)); then
		printf 'Would guard any installed OpenCode against refreshed Extra V2 metadata before installing packages.\n' >&2
	else
		if pacman -Qq -- opencode >/dev/null 2>&1; then
			guard_opencode=1
		else
			query_status=$?
			[[ $query_status == 1 ]] || die 'Cannot determine installed OpenCode ownership; refusing bootstrap package transactions.'
		fi
	fi
	phase 'Git prerequisites: refreshing databases and downloading without installing'
	run sudo pacman -Syu --downloadonly --needed git ca-certificates
	phase 'Git prerequisites: validating native OpenCode V2 policy'
	if ((guard_opencode)); then
		metadata=$(LC_ALL=C pacman -Si -- extra/opencode) || die 'OpenCode V2 repository metadata is unavailable. Databases/cache were refreshed, but no packages installed; full upgrade pending.'
		repository=$(printf '%s\n' "$metadata" | sed -n 's/^Repository[[:space:]]*:[[:space:]]*//p')
		name=$(printf '%s\n' "$metadata" | sed -n 's/^Name[[:space:]]*:[[:space:]]*//p')
		version=$(printf '%s\n' "$metadata" | sed -n 's/^Version[[:space:]]*:[[:space:]]*//p')
		if [[ $version == *:* ]]; then
			[[ $version =~ ^[0-9]+: ]] || die 'Invalid OpenCode package epoch; databases refreshed, no packages installed, full upgrade pending.'
			version=${version#*:}
		fi
		[[ $repository == extra && $name == opencode && $version =~ ^2\.[0-9][[:alnum:].+_-]*$ ]] || die 'Installed OpenCode must remain native Extra V2. Databases/cache refreshed, no packages installed; full upgrade pending. Do not run isolated pacman -S installs.'
		packages+=(extra/opencode)
	fi
	phase 'Git prerequisites: full upgrade using the checked indexes'
	run sudo pacman -Su --needed -- "${packages[@]}"
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
	phase 'Bootstrap platform validation: Arch/Manjaro x86_64, regular user'
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
