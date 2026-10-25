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

# shellcheck source=lib/hardware.sh
source "$ROOT/lib/hardware.sh"

load_modules() {
	MODULES=() PACKAGES=() STOW_PACKAGES=() MANUAL_MODULES=()
	detect_system76
	local file name line key value group package saw_group saw_packages saw_default default_enabled selector manual
	local -a module_packages=()
	local -A seen_packages=() requested_modules=() known_modules=()
	for selector in "${REQUESTED_MODULES[@]}"; do requested_modules[$selector]=1; done
	[[ -d $ROOT/modules ]] || die 'Missing modules directory.'
	while IFS= read -r -d '' file; do
		name=${file##*/}
		name=${name%.conf}
		[[ $name =~ ^[a-z0-9][a-z0-9_-]*$ ]] || die "Invalid module name: $name"
		known_modules[$name]=1
		group='' saw_group=0 saw_packages=0 saw_default=0 default_enabled=true manual=''
		module_packages=()
		while IFS= read -r line || [[ -n $line ]]; do
			[[ -n $line && $line != \#* ]] || continue
			[[ $line == *=* ]] || die "Invalid metadata line in $file: $line"
			key=${line%%=*}
			value=${line#*=}
			case $key in
			manual)
				[[ -z $manual && -n $value ]] || die "Invalid or duplicate manual guidance in $file"
				manual=$value
				;;
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
		if [[ $name == system76 && $SYSTEM76_DETECTED == 0 ]]; then
			[[ ! -v requested_modules[$name] ]] || die 'System76 support requires confirmed System76 DMI vendor information.'
			continue
		fi
		if [[ -v requested_modules[$name] ]] || { [[ $default_enabled == true ]] && group_selected "$group"; } ||
			{ [[ $name == system76 && $SYSTEM76_DETECTED == 1 ]] && group_selected core; }; then
			MODULES+=("$name")
			if [[ -n $manual ]]; then
				MANUAL_MODULES+=("$name: $manual")
				log "Manual application setup required: $name: $manual"
			fi
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

check_upgrade_free_space() {
	# A full upgrade needs room for downloads, unpacked packages, and snapshot
	# metadata. Refuse before touching the package database when it is too tight.
	local target minimum available
	while IFS='|' read -r target minimum; do
		[[ -d $target ]] || continue
		available=$(df -Pk "$target" 2>/dev/null | awk 'NR == 2 { print $4 }')
		[[ $available =~ ^[0-9]+$ ]] || die "Could not determine free space for $target; refusing the package transaction."
		((available >= minimum * 1024)) || die "Only $((available / 1024)) MiB free on $target; at least ${minimum} MiB is required before upgrading."
	done <<'EOF'
/|2048
/boot|256
/efi|64
/boot/efi|64
EOF
}

prune_dotfiles_snapshots() {
	local parent=$1 current=$2 keep=${DOTFILES_SNAPSHOT_KEEP:-5}
	local entry name
	local -a snapshots=()
	[[ $keep =~ ^[1-9][0-9]*$ ]] || die "Invalid DOTFILES_SNAPSHOT_KEEP: $keep"
	for entry in "$parent"/dotfiles-*; do
		[[ -d $entry ]] || continue
		name=${entry##*/}
		[[ $name != "$current" ]] || continue
		snapshots+=("$name")
	done
	((${#snapshots[@]} >= keep)) || return 0
	# Timestamp names sort chronologically. Keep the current snapshot plus the
	# newest (keep - 1) older ones; delete only this repository's snapshots.
	local sorted=''
	sorted=$(printf '%s\n' "${snapshots[@]}" | LC_ALL=C sort)
	snapshots=()
	while IFS= read -r name; do snapshots+=("$name"); done <<<"$sorted"
	local excess index
	excess=$((${#snapshots[@]} - keep + 1))
	for ((index = 0; index < excess; index++)); do
		name=${snapshots[index]}
		run sudo btrfs subvolume delete "$parent/$name" || log "Warning: could not prune old snapshot $name; delete it manually."
	done
}

write_upgrade_rollback_notes() {
	local state=$1 name=$2 source=$3 root_top=$4 snapshot_top=$5 boot_separate=$6
	{
		printf 'Pre-upgrade Btrfs snapshot: %s\n' "$name"
		printf 'Created: %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')"
		printf 'Device: %s\n' "$source"
		printf 'Root subvolume: %s\n' "$root_top"
		printf 'Snapshot at the Btrfs top level: %s\n' "$snapshot_top"
		printf '\nRollback requires live media and a mounted Btrfs top level.\n'
		printf 'Open any LUKS container first if the device is encrypted.\n'
		printf '  mount -o subvolid=5 %q /mnt\n' "$source"
		printf '  mv /mnt/%s /mnt/%s.broken-%s\n' "$root_top" "$root_top" "$name"
		printf '  btrfs subvolume snapshot /mnt/%s /mnt/%s\n' "$snapshot_top" "$root_top"
		printf '  umount /mnt\n'
		printf '\nIf fstab or the bootloader pins a subvolid instead of a subvolume name,\n'
		printf 'update that id after recreating the root subvolume.\n'
		if ((boot_separate)); then
			printf '\nA separate /boot or EFI partition is not part of this snapshot.\n'
			printf 'After restoring, chroot and reinstall the kernel or restore your boot backup.\n'
		fi
		printf '\nPackages installed before the upgrade are recorded in packages-before.txt.\n'
	} >"$state/rollback.txt" || die "Could not write rollback notes in $state."
}

create_btrfs_snapshot() {
	local source fsroot root_top snapshots_target snapshots_type snapshots_source
	local parent='' parent_top='' temp='' mounted=0 name timestamp snapshot_top
	local state boot_separate=0
	source=$(findmnt -n -o SOURCE --target / 2>/dev/null) || die 'Could not determine the Btrfs root device; refusing the package transaction.'
	source=${source%%\[*}
	fsroot=$(findmnt -n -o FSROOT --target / 2>/dev/null) || die 'Could not determine the Btrfs root subvolume; refusing the package transaction.'
	[[ $fsroot == /* && $fsroot != / ]] || die 'The Btrfs root is the filesystem top level, not a subvolume; configure a root subvolume before upgrading.'
	root_top=${fsroot#/}
	timestamp=$(date +%Y%m%d-%H%M%S)
	name=dotfiles-$timestamp-$$
	# Prefer an already-mounted snapshot subvolume, such as @snapshots.
	if [[ -d /.snapshots ]]; then
		snapshots_target=$(findmnt -n -o TARGET --target /.snapshots 2>/dev/null || true)
		snapshots_type=$(findmnt -n -o FSTYPE --target /.snapshots 2>/dev/null || true)
		snapshots_source=$(findmnt -n -o SOURCE --target /.snapshots 2>/dev/null || true)
		snapshots_source=${snapshots_source%%\[*}
		if [[ $snapshots_target == /.snapshots && $snapshots_type == btrfs && $snapshots_source == "$source" ]]; then
			parent=/.snapshots
			parent_top=$(findmnt -n -o FSROOT --target /.snapshots)
			parent_top=${parent_top#/}
			# Snapshots nested inside the root subvolume would move with it during
			# rollback. Fall back to a top-level @snapshots subvolume instead.
			if [[ $parent_top == "$root_top" || $parent_top == "$root_top/"* ]]; then
				parent=''
				parent_top=''
			fi
		fi
	fi
	if [[ -z $parent ]]; then
		temp=$(sudo mktemp -d /run/dotfiles-btrfs.XXXXXXXX) || die 'Could not create a temporary Btrfs top-level mountpoint; refusing the package transaction.'
		if ! run sudo mount -o subvolid=5 -- "$source" "$temp"; then
			sudo rmdir "$temp" >/dev/null 2>&1 || true
			die "Could not mount the Btrfs top level from $source; refusing the package transaction."
		fi
		mounted=1
		if [[ -e $temp/@.snapshots ]] && sudo btrfs subvolume show "$temp/@.snapshots" >/dev/null 2>&1; then
			# Reuse an existing top-level snapshot subvolume even when it is not
			# currently mounted at /.snapshots.
			parent=$temp/@.snapshots
			parent_top=@.snapshots
		elif [[ ! -e $temp/@snapshots ]]; then
			if ! run sudo btrfs subvolume create "$temp/@snapshots"; then
				sudo umount "$temp" >/dev/null 2>&1 || true
				sudo rmdir "$temp" >/dev/null 2>&1 || true
				die 'Could not create the @snapshots subvolume; refusing the package transaction.'
			fi
			parent=$temp/@snapshots
			parent_top=@snapshots
		elif ! sudo btrfs subvolume show "$temp/@snapshots" >/dev/null 2>&1; then
			sudo umount "$temp" >/dev/null 2>&1 || true
			sudo rmdir "$temp" >/dev/null 2>&1 || true
			die 'The Btrfs @snapshots path exists but is not a subvolume; refusing the package transaction.'
		else
			parent=$temp/@snapshots
			parent_top=@snapshots
		fi
	fi
	if ! run sudo btrfs subvolume snapshot -r "$(if ((mounted)); then printf '%s/%s' "$temp" "$root_top"; else printf /; fi)" "$parent/$name"; then
		if ((mounted)); then
			sudo umount "$temp" >/dev/null 2>&1 || true
			sudo rmdir "$temp" >/dev/null 2>&1 || true
		fi
		die 'Could not create the pre-upgrade Btrfs snapshot; refusing the package transaction.'
	fi
	if ! sudo btrfs subvolume show "$parent/$name" >/dev/null 2>&1; then
		if ((mounted)); then
			sudo umount "$temp" >/dev/null 2>&1 || true
			sudo rmdir "$temp" >/dev/null 2>&1 || true
		fi
		die 'The pre-upgrade snapshot could not be verified; refusing the package transaction.'
	fi
	prune_dotfiles_snapshots "$parent" "$name"
	if ((mounted)); then
		run sudo umount "$temp" || die "Could not unmount $temp; unmount it manually before upgrading."
		sudo rmdir "$temp" >/dev/null 2>&1 || true
	fi
	if [[ -n $parent_top ]]; then snapshot_top=$parent_top/$name; else snapshot_top=$name; fi
	local mountpoint
	for mountpoint in /boot /boot/efi /efi; do
		[[ -d $mountpoint ]] || continue
		if [[ $(findmnt -n -o TARGET --target "$mountpoint" 2>/dev/null || true) == "$mountpoint" ]]; then
			boot_separate=1
		fi
	done
	state=${XDG_STATE_HOME:-$HOME/.local/state}/dotfiles/upgrades/$name
	mkdir -p -- "$state" || die "Could not create upgrade state directory: $state"
	rpm -qa --qf '%{NAME} %{EPOCHNUM}:%{VERSION}-%{RELEASE}.%{ARCH}\n' | LC_ALL=C sort >"$state/packages-before.txt" || die 'Could not record installed RPM packages before upgrading.'
	{
		printf 'snapshot=%s\n' "$name"
		printf 'source=%s\n' "$source"
		printf 'root_subvolume=%s\n' "$root_top"
		printf 'snapshot_top=%s\n' "$snapshot_top"
	} >"$state/snapshot.txt"
	write_upgrade_rollback_notes "$state" "$name" "$source" "$root_top" "$snapshot_top" "$boot_separate"
	DOTFILES_UPGRADE_SNAPSHOT=$name
	DOTFILES_UPGRADE_STATE=$state
	DOTFILES_UPGRADE_BEFORE=$state/packages-before.txt
	log "Pre-upgrade Btrfs snapshot ready: $name"
	log "Rollback notes: $state/rollback.txt"
}

begin_system_upgrade() {
	DOTFILES_UPGRADE_SNAPSHOT='' DOTFILES_UPGRADE_STATE='' DOTFILES_UPGRADE_BEFORE=''
	local fstype
	if ((DRY_RUN)); then
		log 'Would verify Btrfs snapshot support, free space, and RPM state, then create a read-only pre-upgrade snapshot.'
		return 0
	fi
	command -v findmnt >/dev/null || die 'findmnt is required to verify upgrade safety; refusing the package transaction.'
	fstype=$(findmnt -n -o FSTYPE --target / 2>/dev/null) || die 'Could not determine the root filesystem type; refusing the package transaction.'
	if [[ $fstype != btrfs ]]; then
		log "Root filesystem is $fstype, not btrfs; no pre-upgrade snapshot will be created."
		return 0
	fi
	command -v btrfs >/dev/null || die 'btrfs-progs is required to snapshot this Btrfs root; refusing the package transaction.'
	command -v df >/dev/null || die 'df is required to check free space before upgrading; refusing the package transaction.'
	rpm --verifydb || die 'The RPM database failed its consistency check; repair it before upgrading.'
	check_upgrade_free_space
	create_btrfs_snapshot
}

end_system_upgrade() {
	local before=${DOTFILES_UPGRADE_BEFORE:-} changed
	[[ -n $before && -f $before ]] || return 0
	if ! rpm --verifydb; then
		log 'Warning: the RPM database failed its consistency check after the upgrade. Inspect it before rebooting.'
	fi
	changed=$(awk '
		NR == FNR { before[$1] = $2; next }
		$1 ~ /^(kernel|dracut|systemd|grub2|shim|akmod|kmod|nvidia|linux-firmware)/ && before[$1] != $2 { print $1 }
	' "$before" <(rpm -qa --qf '%{NAME} %{EPOCHNUM}:%{VERSION}-%{RELEASE}.%{ARCH}\n') | LC_ALL=C sort -u)
	if [[ -n $changed ]]; then
		log "Boot-critical packages changed: $changed"
		log 'Reboot before relying on the updated kernel, initramfs, bootloader, or graphics stack.'
	fi
	log "Pre-upgrade snapshot retained: $DOTFILES_UPGRADE_SNAPSHOT"
	log "Rollback notes: $DOTFILES_UPGRADE_STATE/rollback.txt"
	DOTFILES_UPGRADE_BEFORE='' DOTFILES_UPGRADE_STATE='' DOTFILES_UPGRADE_SNAPSHOT=''
}

# shellcheck source=lib/fedora.sh
source "$ROOT/lib/fedora.sh"

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

# shellcheck source=modules/nix.sh
source "$ROOT/modules/nix.sh"

preflight_custom_modules() {
	local module
	for module in "${MODULES[@]}"; do
		case $module in
		opencode) bash "$ROOT/modules/opencode.sh" --check ;;
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
	phase 'System update preflight: native paths and module prerequisites'
	preflight_custom_modules
	install_packages
	end_system_upgrade
	setup_modules
	log 'Nix and native applications are repository-managed; project flake.lock updates remain project-owned.'
}

print_next_steps() {
	local command=$1 scope=${2:-} variables=$HOME/.config/bash/variables.sh
	printf '\nNext steps:\n'
	print_manual_modules
	if [[ $command == update ]]; then
		printf '  Restart affected apps; reopen your terminal for shell/config changes.\n'
		printf '  Reboot if the update reported boot-critical package changes.\n'
		if [[ $scope == configs ]]; then printf '  Config updates do not install new dependencies. Rerun dotfiles install with the same selections when needed.\n'; fi
		printf '  Selections are explicit on each command: repeat --groups %s' "$GROUPS_CSV"
		if [[ -n ${MODULES_CSV:-} ]]; then printf ' --modules %s' "$MODULES_CSV"; fi
		printf '.\n'
		return 0
	fi
	if [[ $command == link ]]; then printf '  Linking did not install packages. Run dotfiles install with the same selections if tools/dependencies are missing.\n'; fi
	if module_selected system76; then system76_next_steps; fi
	if module_selected plasma; then
		printf "  Log into Plasma (Wayland); verify echo \"\$XDG_SESSION_TYPE\" reports wayland. Setup does not install/switch the desktop session.\n"
		printf '  Test portal file pickers/screen sharing and an unlocked Secret Service provider (KWallet if supported/configured, otherwise a provider you choose); setup does not configure wallets or autostart.\n'
	fi
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
	run git -C "$ROOT" fetch origin "refs/heads/$branch:refs/remotes/origin/$branch"
	if ((DRY_RUN)); then
		log 'Would verify fast-forward ancestry; preview uses current checkout metadata.'
	else
		git -C "$ROOT" merge-base --is-ancestor HEAD "refs/remotes/origin/$branch" || die 'Local checkout is ahead or diverged; refusing update.'
	fi
	run git -C "$ROOT" merge --ff-only --no-overwrite-ignore "refs/remotes/origin/$branch"
}
