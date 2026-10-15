# shellcheck shell=bash
# Entrypoints own strict mode. Metadata is data, never shell code.
die() {
	printf 'dotfiles: %s\n' "$*" >&2
	exit 1
}
log() { printf 'dotfiles: %s\n' "$*" >&2; }
phase() {
	DOTFILES_PHASE=$1
	log "$DOTFILES_PHASE"
}
run() {
	printf '+ ' >&2
	printf '%q ' "$@" >&2
	printf '\n' >&2
	if ((! DRY_RUN)); then "$@"; fi
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
	[[ $HOME == /* && -d $HOME ]] || die 'HOME must be an existing absolute directory.'
	[[ ${XDG_CONFIG_HOME:-$HOME/.config} == "$HOME/.config" ]] || die 'Custom XDG_CONFIG_HOME is unsupported; configs deploy to ~/.config. No setup changes applied.'
}

validate_groups() {
	[[ -n $GROUPS_CSV && $GROUPS_CSV != ,* && $GROUPS_CSV != *, && $GROUPS_CSV != *,,* ]] || die 'Invalid group list.'
	local group
	IFS=, read -r -a SELECTED_GROUPS <<<"$GROUPS_CSV"
	for group in "${SELECTED_GROUPS[@]}"; do
		case $group in core | ai | desktop | cloud | bitcoin | hardware) ;; *) die "Unknown group: $group" ;; esac
	done
}

group_selected() {
	local group
	for group in "${SELECTED_GROUPS[@]}"; do [[ $group != "$1" ]] || return 0; done
	return 1
}

validate_module_selectors() {
	REQUESTED_MODULES=()
	[[ -n ${MODULES_CSV:-} ]] || return 0
	[[ $MODULES_CSV != ,* && $MODULES_CSV != *, && $MODULES_CSV != *,,* ]] || die 'Invalid module list.'
	local module
	IFS=, read -r -a REQUESTED_MODULES <<<"$MODULES_CSV"
	for module in "${REQUESTED_MODULES[@]}"; do
		[[ $module =~ ^[a-z0-9][a-z0-9_-]*$ ]] || die "Invalid module selector: $module"
		[[ -f $ROOT/modules/$module.conf && ! -L $ROOT/modules/$module.conf ]] || die "Unknown module selector: $module"
	done
}

load_modules() {
	MODULES=() PACKAGES=() STOW_PACKAGES=()
	local file name line key value group package saw_group saw_packages saw_default default_enabled selector
	local -a module_packages=()
	local -A seen_packages=() requested_modules=() known_modules=()
	for selector in "${REQUESTED_MODULES[@]}"; do requested_modules[$selector]=1; done
	[[ -d $ROOT/modules ]] || die 'Missing modules directory.'
	while IFS= read -r -d '' file; do
		name=${file##*/}
		name=${name%.conf}
		[[ $name =~ ^[a-z0-9][a-z0-9_-]*$ ]] || die "Invalid module name: $name"
		known_modules[$name]=1
		group='' saw_group=0 saw_packages=0 saw_default=0 default_enabled=true
		module_packages=()
		while IFS= read -r line || [[ -n $line ]]; do
			[[ -n $line && $line != \#* ]] || continue
			[[ $line == *=* ]] || die "Invalid metadata line in $file: $line"
			key=${line%%=*}
			value=${line#*=}
			case $key in
			default)
				((! saw_default)) || die "Duplicate default in $file"
				saw_default=1
				case $value in true | false) default_enabled=$value ;; *) die "Invalid default in $file (expected true or false)" ;; esac
				;;
			group)
				((! saw_group)) || die "Duplicate group in $file"
				saw_group=1
				group=$value
				case $group in core | ai | desktop | cloud | bitcoin | hardware) ;; *) die "Invalid group in $file" ;; esac
				;;
			packages)
				((! saw_packages)) || die "Duplicate packages in $file"
				saw_packages=1
				read -r -a module_packages <<<"$value"
				for package in "${module_packages[@]}"; do
					[[ $package =~ ^[a-zA-Z0-9][a-zA-Z0-9@._+-]*$ ]] || die "Invalid package in $file: $package"
					case $package in rustup | rust | cargo | nvm | nodejs | npm | gcc | clang | cmake | go | jdk*) die "Global toolchain forbidden in $file: $package" ;; esac
				done
				;;
			*) die "Unknown metadata field in $file: $key" ;;
			esac
		done <"$file"
		((saw_group && saw_packages)) || die "Metadata requires group and packages: $file"
		if [[ -v requested_modules[$name] ]] || { [[ $default_enabled == true ]] && group_selected "$group"; }; then
			MODULES+=("$name")
			if [[ -d $ROOT/stow/$name ]]; then STOW_PACKAGES+=("$name"); fi
			for package in "${module_packages[@]}"; do
				if [[ ! -v seen_packages[$package] ]]; then
					PACKAGES+=("$package")
					seen_packages[$package]=1
				fi
			done
		fi
	done < <(find "$ROOT/modules" -maxdepth 1 -type f -name '*.conf' -print0 | LC_ALL=C sort -z)
	for selector in "${REQUESTED_MODULES[@]}"; do
		[[ -v known_modules[$selector] ]] || die "Unknown module selector: $selector"
	done
	((${#MODULES[@]})) || die 'No modules selected.'
}

preflight_links() {
	preflight_launcher
	local package source relative target parent expected actual
	local -A owners=() directories=()
	for package in "${STOW_PACKAGES[@]}"; do
		while IFS= read -r -d '' source; do
			relative=${source#"$ROOT/stow/$package/"}
			[[ $relative != .local/bin/dotfiles ]] || die 'The dotfiles launcher is managed outside Stow; remove its Stow entry.'
			target=$HOME/$relative
			if [[ -d $source && ! -L $source ]]; then
				[[ ! -v owners[$relative] ]] || die "File/directory collision at $relative"
				directories[$relative]=1
				[[ ! -L $target && (! -e $target || -d $target) ]] || die "Conflicting directory: $target"
			else
				[[ ! -v directories[$relative] ]] || die "File/directory collision at $relative"
				if [[ -v owners[$relative] ]]; then die "Two packages own $relative: ${owners[$relative]} and $package"; fi
				owners[$relative]=$package
			fi
			parent=$(dirname "$target")
			while [[ $parent != "$HOME" && $parent != / ]]; do
				[[ ! -L $parent ]] || die "Conflicting parent symlink: $parent"
				[[ ! -e $parent || -d $parent ]] || die "Conflicting parent file: $parent"
				parent=$(dirname "$parent")
			done
			if [[ -d $source && ! -L $source ]]; then
				continue
			elif [[ -L $target ]]; then
				expected=$(realpath -m "$source")
				actual=$(realpath -m "$target")
				[[ $expected == "$actual" && -e $target ]] || die "Conflicting or dangling link: $target"
			elif [[ -e $target ]]; then
				die "Conflict: $target (back it up and remove it yourself before linking)"
			fi
		done < <(find "$ROOT/stow/$package" -mindepth 1 \( -type d -o -type f -o -type l \) -print0)
	done
	if ((${#STOW_PACKAGES[@]})) && command -v stow >/dev/null; then
		stow --simulate --verbose --no-folding --dir="$ROOT/stow" --target="$HOME" --stow "${STOW_PACKAGES[@]}"
	fi
}

module_selected() {
	local module
	for module in "${MODULES[@]}"; do [[ $module != "$1" ]] || return 0; done
	return 1
}

preflight_launcher() {
	local launcher=$HOME/.local/bin/dotfiles parent
	[[ -f $ROOT/bin/dotfiles ]] || die 'Missing repository dotfiles entrypoint.'
	parent=$(dirname "$launcher")
	while [[ $parent != "$HOME" && $parent != / ]]; do
		[[ ! -L $parent && (! -e $parent || -d $parent) ]] || die "Conflicting launcher parent: $parent"
		parent=$(dirname "$parent")
	done
	if [[ -L $launcher ]]; then
		[[ $(readlink "$launcher") == "$ROOT/bin/dotfiles" && -e $launcher ]] || die "Unmanaged or dangling dotfiles launcher: $launcher"
	elif [[ -e $launcher ]]; then
		die "Unmanaged dotfiles launcher: $launcher; back it up and move it yourself first."
	fi
}

link_launcher() {
	phase 'Dotfiles launcher: checking the convenience command'
	preflight_launcher
	if [[ -L $HOME/.local/bin/dotfiles ]]; then
		log 'Dotfiles launcher already points to this checkout.'
		return 0
	fi
	run mkdir -p "$HOME/.local/bin"
	run ln -s "$ROOT/bin/dotfiles" "$HOME/.local/bin/dotfiles"
	if ((DRY_RUN)); then log 'Launcher creation planned only.'; else log 'Dotfiles launcher ready.'; fi
}

preflight_link_modules() {
	if module_selected ssh; then bash "$ROOT/modules/ssh.sh" --check; fi
}

link_configs() {
	local create_launcher=${1:-1}
	phase 'Configuration links: verifying the GNU Stow preflight'
	if ((${#STOW_PACKAGES[@]})) && ! command -v stow >/dev/null; then
		if ((DRY_RUN)); then log 'GNU Stow is missing; manual preflight passed, GNU Stow preflight required after installation.'; else die 'GNU Stow is required; run dotfiles install first.'; fi
	elif ((${#STOW_PACKAGES[@]})); then
		stow --simulate --verbose --no-folding --dir="$ROOT/stow" --target="$HOME" --stow "${STOW_PACKAGES[@]}"
	fi
	if module_selected ssh; then
		phase 'SSH permissions: source configs and the owned home directory only'
		run bash "$ROOT/modules/ssh.sh"
		if ((DRY_RUN)); then log 'SSH permission changes planned only.'; else log 'SSH permissions checked; live key files were not changed.'; fi
	fi
	phase 'Configuration links: applying selected packages'
	local package
	for package in "${STOW_PACKAGES[@]}"; do log "Config link preparation: $package"; done
	if ((${#STOW_PACKAGES[@]})); then run stow --verbose --no-folding --dir="$ROOT/stow" --target="$HOME" --stow "${STOW_PACKAGES[@]}"; fi
	for package in "${STOW_PACKAGES[@]}"; do
		if ((DRY_RUN)); then log "Config link planned: $package"; else log "Config links ready: $package"; fi
	done
	if ((create_launcher)); then link_launcher; fi
	if module_selected nix && ((! DRY_RUN)); then
		phase 'Native Nix: validating the daemon and linked client features'
		validate_nix
		log 'Native Nix daemon and linked client features validated.'
	fi
}

install_packages() {
	phase 'Package preflight: native ownership and helper health'
	# Full upgrades also affect unselected applications; reject unmanaged PATH
	# copies before downloads, without executing them (including in dry-runs).
	preflight_native_opencode_paths
	if group_selected core || ((${#PACKAGES[@]})); then validate_existing_paru; fi
	local package guard_opencode=0 query_status need_nix=0
	local -a baseline=(git stow wget ca-certificates xz)
	local -a official=() aur=() targets=()
	local -A transaction_seen=()
	if module_selected nix; then need_nix=1; fi
	for package in "${PACKAGES[@]}"; do
		if [[ $package == nix ]]; then need_nix=1; fi
	done
	# Before even download-only transactions, reject upstream/partial Nix if
	# selected or potentially required by a missing helper's Rust bootstrap.
	if ((need_nix)) || { ! command -v paru >/dev/null && { group_selected core || ((${#PACKAGES[@]})); }; }; then
		preflight_nix
	fi
	if module_selected opencode; then guard_opencode=1; fi
	for package in "${PACKAGES[@]}"; do
		if [[ $package == opencode ]]; then guard_opencode=1; fi
	done
	if ((DRY_RUN)); then
		log 'Dry-run uses cached indexes only. After download-only synchronization, the real guard checks Extra/OpenCode V2 whenever selected or already installed.'
	else
		# Query package ownership, not PATH: system upgrades include unselected apps.
		if pacman -Qq -- opencode >/dev/null 2>&1; then
			guard_opencode=1
		else
			query_status=$?
			[[ $query_status == 1 ]] || die 'Could not determine installed OpenCode package ownership; refusing the repository upgrade.'
		fi
	fi
	# Refresh and download the full upgrade, but install nothing until V2 is checked.
	phase 'Database refresh: downloading the full upgrade without installing packages'
	run sudo pacman -Syu --downloadonly --needed "${baseline[@]}"
	phase 'Repository policy: checking native packages and OpenCode V2'
	if ((guard_opencode && DRY_RUN)); then
		if pacman -Si -- extra/opencode >/dev/null 2>&1; then
			log 'Cached Extra/OpenCode metadata is available; its V2 suitability will be checked only after an actual refresh.'
		else
			log 'Extra/OpenCode is missing from the cached indexes; a real refresh and successful V2 guard are required, never an AUR fallback.'
		fi
	fi
	if ((guard_opencode && ! DRY_RUN)); then
		if ! guard_native_opencode_repository; then
			die 'OpenCode must remain native Extra V2. Repository databases/cache were refreshed, but no packages were installed; a full upgrade is still pending. Do not run isolated pacman -S installs against these refreshed databases.'
		fi
	fi
	phase 'Package sources: resolving official repositories and AUR'
	for package in "${PACKAGES[@]}"; do
		if [[ $package == opencode ]]; then
			# The guard, not generic AUR fallback, owns this dependency. An explicit
			# Extra target also prevents a higher-priority repository substituting it.
			official+=(extra/opencode)
		elif [[ $package == nix ]]; then
			# Required native dependency; never classify Nix as an AUR fallback.
			need_nix=1
		elif pacman -Si -- "$package" >/dev/null 2>&1; then
			official+=("$package")
		else
			aur+=("$package")
		fi
	done
	if ((guard_opencode)) && [[ ! " ${official[*]} " == *' extra/opencode '* ]]; then official+=(extra/opencode); fi
	# Include helper prerequisites in the same full transaction, rather than
	# installing them separately against newly refreshed repository databases.
	if { group_selected core || ((${#aur[@]})); } && ! command -v paru >/dev/null; then
		if pacman -Si -- paru >/dev/null 2>&1; then
			official+=(paru)
		else
			official+=(base-devel openssl)
			need_nix=1
		fi
	fi
	if ((need_nix)); then
		if ((DRY_RUN)); then
			log 'Native repository Nix is required; availability must be verified against refreshed indexes before a real full upgrade.'
			official+=(nix)
		else
			require_native_nix_repository
			official+=("$NIX_REPOSITORY_TARGET")
		fi
	fi
	for package in "${baseline[@]}" "${official[@]}"; do
		if [[ ! -v transaction_seen[$package] ]]; then
			targets+=("$package")
			transaction_seen[$package]=1
		fi
	done
	# No second -y: use exactly the indexes inspected by the guard, with a full -u.
	log "Official package targets (${#targets[@]}): ${targets[*]}"
	if ((${#aur[@]})); then log "AUR package targets (${#aur[@]}): ${aur[*]}"; else log 'AUR package targets: none.'; fi
	phase 'Full upgrade: installing against the checked repository indexes'
	run sudo pacman -Su --needed -- "${targets[@]}"
	if ((need_nix)); then
		phase 'Native Nix: bootstrap configuration before linking'
		setup_nix --bootstrap
	fi
	phase 'AUR setup: preparing the helper and selected packages'
	if group_selected core || ((${#aur[@]})); then
		ensure_paru
	else
		log 'No AUR helper changes required for this selection.'
	fi
	if ((${#aur[@]})); then
		phase 'AUR packages: installing the selected dependencies'
		run paru -S --needed -- "${aur[@]}"
	fi
}

guard_native_opencode_repository() {
	local metadata repository name version
	if ! metadata=$(LC_ALL=C pacman -Si -- extra/opencode); then
		log 'Official Extra/OpenCode metadata is unavailable; no AUR fallback.'
		return 1
	fi
	repository=$(printf '%s\n' "$metadata" | sed -n 's/^Repository[[:space:]]*:[[:space:]]*//p')
	name=$(printf '%s\n' "$metadata" | sed -n 's/^Name[[:space:]]*:[[:space:]]*//p')
	version=$(printf '%s\n' "$metadata" | sed -n 's/^Version[[:space:]]*:[[:space:]]*//p')
	[[ $repository == extra && $name == opencode ]] || {
		log 'OpenCode must come from native Extra under the name opencode.'
		return 1
	}
	if [[ $version == *:* ]]; then
		[[ $version =~ ^[0-9]+: ]] || {
			log 'Invalid OpenCode package epoch.'
			return 1
		}
		version=${version#*:}
	fi
	[[ $version =~ ^2\.[0-9][[:alnum:].+_-]*$ ]] || {
		log "Native Extra OpenCode must remain V2; found $version."
		return 1
	}
}

require_native_nix_repository() {
	local metadata repository name
	metadata=$(LC_ALL=C pacman -Si -- nix) || die 'Native Nix is unavailable. Repository databases were refreshed but no packages were installed; a full upgrade remains pending. No AUR/upstream fallback.'
	repository=$(printf '%s\n' "$metadata" | sed -n 's/^Repository[[:space:]]*:[[:space:]]*//p')
	name=$(printf '%s\n' "$metadata" | sed -n 's/^Name[[:space:]]*:[[:space:]]*//p')
	[[ $name == nix ]] || die 'Unexpected Nix repository metadata; no packages installed and a full upgrade remains pending.'
	case $repository in core | extra | multilib) ;; *) die 'Nix must be available from an official repository. No packages installed; full upgrade remains pending. No AUR/upstream fallback.' ;; esac
	NIX_REPOSITORY_TARGET=$repository/nix
}

# Keep these PATH guards identical to their standalone copies in install.sh.
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
	[[ -e $candidate || -L $candidate ]] || return 0
	[[ -e $candidate ]] || die "Dangling OpenCode shadow: $candidate; inspect and move it manually. Leaving it unchanged."
	# Ordinary non-executable files cannot be dispatched through PATH. Symlinks
	# and the explicitly protected startup path still require inspection.
	if ((! explicit)) && [[ ! -L $candidate && (! -f $candidate || ! -x $candidate) ]]; then return 0; fi
	[[ $candidate != /usr/bin/opencode ]] || return 0
	actual=$(realpath -m -- "$candidate") || die "Could not resolve OpenCode shadow: $candidate; inspect it manually. Leaving it unchanged."
	native=$(realpath -m -- /usr/bin/opencode) || die 'Could not resolve native OpenCode path; inspect it manually.'
	[[ $actual == "$native" ]] || die "Unmanaged OpenCode shadows the native package: $candidate; inspect and move it manually. Leaving it unchanged."
}

# shellcheck source=modules/paru.sh
source "$ROOT/modules/paru.sh"

validate_existing_paru() {
	command -v paru >/dev/null || return 0
	if ((DRY_RUN)); then
		log 'Would check that the existing paru reports a valid version before package transactions.'
		return 0
	fi
	local version
	version=$(paru --version) || die 'Existing paru cannot run; repair or remove the broken helper before continuing.'
	version=${version%%$'\n'*}
	[[ $version =~ ^paru[[:space:]]v[0-9]+\.[0-9]+(\.[0-9]+)?([[:space:]]|$) ]] || die 'Existing paru reports an unexpected version; repair the helper before continuing.'
}

# shellcheck source=modules/nix.sh
source "$ROOT/modules/nix.sh"

preflight_custom_modules() {
	local module
	for module in "${MODULES[@]}"; do
		case $module in
		opencode) preflight_native_opencode_paths ;;
		nono) bash "$ROOT/modules/$module.sh" --check ;;
		esac
	done
}

setup_modules() {
	phase 'Module configuration: preparing selected tools'
	local module
	for module in "${MODULES[@]}"; do
		phase "Module configuration: $module"
		log "Preparing module: $module"
		if [[ $module == ssh ]]; then
			log 'SSH permission changes are deferred until config-link preflight finishes.'
		elif [[ $module == nix ]]; then
			setup_nix --bootstrap
		elif [[ -f $ROOT/modules/$module.sh ]]; then
			run bash "$ROOT/modules/$module.sh"
		fi
		if ((DRY_RUN)); then log "Module planned: $module"; else log "Module preparation finished: $module"; fi
	done
}

docker_membership() {
	((DOCKER_GROUP)) || return 0
	phase 'Docker access: explicitly requested group membership'
	if ((! DRY_RUN)); then getent group docker >/dev/null || die 'Docker group does not exist; install Docker first.'; fi
	local user
	user=$(id -un)
	if id -nG "$user" | tr ' ' '\n' | grep -qx docker; then return 0; fi
	log 'Docker membership grants root-equivalent access. Log out and back in afterwards.'
	run sudo usermod --append --groups docker "$user"
}

preflight_docker_membership() {
	((DOCKER_GROUP)) || return 0
	if module_selected docker; then return 0; fi
	if ! command -v docker >/dev/null || ! getent group docker >/dev/null; then
		die '--docker-group requires Docker already installed with its group, or select --modules docker / --groups cloud.'
	fi
}

update_system() {
	phase 'System update preflight: custom paths and helper health'
	preflight_custom_modules
	validate_existing_paru
	install_packages
	if command -v paru >/dev/null; then
		phase 'AUR update: upgrading installed AUR packages'
		# Native paru is upgraded by the full pacman transaction above. Foreign
		# paru must never rebuild from a mutable AUR recipe; review a frozen pin.
		run paru -Sua --ignore paru
	fi
	setup_modules
	log 'Nix and native applications are repository-managed; project flake.lock updates remain project-owned.'
}

print_next_steps() {
	local command=$1 scope=${2:-} variables=$HOME/.config/bash/variables.sh
	printf '\nNext steps:\n'
	if [[ $command == update ]]; then
		printf '  Restart affected apps; reopen your terminal for shell/config changes.\n'
		if [[ $scope == configs ]]; then printf '  Config updates do not install new dependencies. Rerun dotfiles install with the same selections when needed.\n'; fi
		printf '  Selections are explicit on each command: repeat --groups %s' "$GROUPS_CSV"
		if [[ -n ${MODULES_CSV:-} ]]; then printf ' --modules %s' "$MODULES_CSV"; fi
		printf '.\n'
		return 0
	fi
	if [[ $command == link ]]; then printf '  Linking did not install packages. Run dotfiles install with the same selections if tools/dependencies are missing.\n'; fi
	printf '  No personal credentials, SSH keys, or wallet data were imported.\n'
	if module_selected bash; then
		printf '  Open a new terminal. A custom distro ~/.bash_profile must source ~/.bashrc.\n'
		printf '  Store machine environment overrides in ~/.config/bash/variables.sh, outside this checkout.\n'
		printf '  These commands are instructions only; do not overwrite an existing local file:\n'
		printf '    (umask 077; mkdir -p %q)\n' "$HOME/.config/bash"
		printf '    if [[ ! -e %q && ! -L %q ]]; then (umask 077; cp -n -- %q %q); fi\n' "$variables" "$variables" "$ROOT/examples/local-variables.sh" "$variables"
		printf '    if [[ -f %q && ! -L %q ]]; then chmod 0600 -- %q; fi\n' "$variables" "$variables" "$variables"
		printf '  Edit that private file yourself; setup never creates, reads, or modifies it. Managed nono profiles deny ~/.config/bash.\n'
	fi
	if module_selected opencode; then
		printf '  OpenCode env references: EXA_API_KEY, GITHUB_MCP_TOKEN, MAPLE_API_KEY. Configure only the services you use; no values were installed.\n'
		printf '  Exported secrets can be inherited by AI processes even when the file is denied. Prefer credential injection where available.\n'
	fi
	if module_selected git; then printf '  Set personal Git identity/signing preferences in ~/.gitconfig_local.\n'; fi
	if module_selected ssh; then printf '  Add SSH keys and authenticate manually; dotfiles did not generate or import keys.\n'; fi
	if module_selected bitwarden; then printf '  Log in to native Bitwarden, unlock the vault, and enable its SSH agent. Default socket: ~/.bitwarden-ssh-agent.sock.\n'; fi
	if module_selected nono; then
		if [[ $command == link ]] || ((DRY_RUN)); then
			printf '  Install prepares nono and its pinned OpenCode pack; linking and dry-runs do not install the pack.\n'
		else
			printf '  Nono and its pinned OpenCode pack are ready. Sign in manually only to services you use; no authentication was automated.\n'
		fi
	fi
	if ((DOCKER_GROUP)); then printf '  Log out and back in for Docker membership if it changed (root-equivalent access).\n'; fi
	if module_selected mullvad; then printf '  Manage mullvad-daemon.service and connect in Mullvad manually when ready; dotfiles did not change networking.\n'; fi
	if module_selected bitcoin || module_selected electrs || module_selected sparrow; then
		printf '  Bitcoin: review Tor, absolute storage paths, and service setup manually. Wallet/key migration is separate.\n'
		if module_selected electrs; then printf '  Set up electrs manually in its project Nix environment; check storage, ports, and Tor before starting it.\n'; fi
	fi
	if module_selected nix; then printf '  Use per-project flakes/dev shells; each project owns its flake.lock and toolchains.\n'; fi
}

update_checkout() {
	[[ ${DOTFILES_UPDATED:-0} != 1 ]] || return 0
	local origin branch
	origin=$(git -C "$ROOT" remote get-url origin)
	case $origin in https://github.com/w3irdrobot/dotfiles.git | https://github.com/w3irdrobot/dotfiles | git@github.com:w3irdrobot/dotfiles.git) ;; *) die 'Unexpected origin; expected GitHub w3irdrobot/dotfiles. Inspect origin locally before retrying; refusing update.' ;; esac
	[[ -z $(git -C "$ROOT" status --porcelain --untracked-files=all) ]] || die 'Checkout is dirty; save your work before updating configs.'
	branch=$(git -C "$ROOT" symbolic-ref --quiet --short HEAD) || die 'Detached HEAD; select a branch yourself.'
	if ((DRY_RUN)); then
		run git -C "$ROOT" fetch origin "refs/heads/$branch:refs/remotes/origin/$branch"
		log 'Would verify fast-forward ancestry; preview uses current checkout metadata.'
	else
		git -C "$ROOT" fetch origin "refs/heads/$branch:refs/remotes/origin/$branch"
		git -C "$ROOT" merge-base --is-ancestor HEAD "refs/remotes/origin/$branch" || die 'Local checkout is ahead or diverged; refusing update.'
	fi
	run git -C "$ROOT" merge --ff-only --no-overwrite-ignore "refs/remotes/origin/$branch"
}
