# shellcheck shell=bash
# Fedora 44 / DNF5 only. Entrypoints own strict mode and logging.
MANUAL_MODULES=()
selected_repositories() {
	REPOSITORIES=()
	local module
	for module in "${MODULES[@]}"; do
		case $module in
		brave | ghostty | vscodium | system76 | mullvad | lazygit)
			REPOSITORIES+=("$module")
			;;
		esac
	done
}

preflight_repositories() {
	selected_repositories
	local name source target
	for name in "${REPOSITORIES[@]}"; do
		source=$ROOT/repos/$name.repo
		target=/etc/yum.repos.d/dotfiles-$name.repo
		[[ -f $source && ! -L $source ]] || die "Missing repository definition: $source"
		[[ ! -L $target ]] || die "Repository destination is a symlink: $target; inspect it manually."
		if [[ -e $target ]]; then
			cmp -s -- "$source" "$target" || die "Repository conflict: $target; inspect and move it manually before retrying."
		fi
	done
}

configure_repositories() {
	preflight_repositories
	local name target
	for name in "${REPOSITORIES[@]}"; do
		target=/etc/yum.repos.d/dotfiles-$name.repo
		if [[ ! -e $target ]]; then
			# Do not overwrite a file created since preflight, or follow symlinks.
			run sudo cp --no-clobber --no-dereference -- "$ROOT/repos/$name.repo" "$target"
			if ((! DRY_RUN)); then
				if [[ -L $target ]] || ! cmp -s -- "$ROOT/repos/$name.repo" "$target"; then
					die "Repository definition changed during setup: $target"
				fi
			fi
		fi
	done
}

require_native_nix_repository() {
	local package metadata
	for package in nix nix-core nix-daemon; do
		metadata=$(sudo dnf --cacheonly --repo=fedora --repo=updates repoquery \
			--available --arch=x86_64,noarch --latest-limit=1 --queryformat '%{name}\n' "$package") || die 'Could not query Fedora Nix packages.'
		[[ $metadata == "$package" || $metadata == "$package"$'\n'"$package" ]] || die "Fedora package $package is unavailable; no upstream installer fallback."
	done
}

install_packages() {
	phase 'Package preflight: native ownership and selected RPM sources'
	preflight_native_opencode_paths
	preflight_repositories
	if module_selected nix; then preflight_nix; fi
	if module_selected bitwarden; then preflight_bitwarden; fi
	if module_selected discord; then preflight_discord; fi
	local package available name
	local -a targets=(git stow wget curl ca-certificates xz tar coreutils diffutils btrfs-progs)
	local -A seen=() found=()
	for package in "${targets[@]}"; do seen[$package]=1; done
	for package in "${PACKAGES[@]}"; do
		if [[ ! -v seen[$package] ]]; then
			targets+=("$package")
			seen[$package]=1
		fi
	done
	phase 'RPM sources: preparing selected, signature-checked repository definitions'
	configure_repositories
	phase 'Repository refresh: metadata only, no package installation'
	run sudo dnf --refresh makecache
	phase 'RPM package preflight: resolving selected names from checked metadata'
	if ((! DRY_RUN)); then
		if module_selected nix; then require_native_nix_repository; fi
		# Resolve every selected name before upgrading anything. DNF's install
		# must also remain strict: no --skip-unavailable / --skip-broken.
		# DNF5 prints exactly this format; it does not add record separators.
		available=$(sudo dnf --cacheonly repoquery --available --arch=x86_64,noarch --queryformat '%{name}\n' "${targets[@]}") || die 'Could not resolve selected Fedora RPM packages.'
		while IFS= read -r name; do
			[[ -z $name ]] || found[$name]=1
		done <<<"$available"
		for package in "${targets[@]}"; do
			[[ -v found[$package] ]] || die "RPM package unavailable: $package; no package transaction started. See docs/packages.md."
		done
	fi
	if module_selected bitwarden && ((BITWARDEN_INSTALL_NEEDED)); then
		prepare_bitwarden_rpm
		targets+=("$BITWARDEN_RPM_TARGET")
	fi
	if module_selected discord && ((DISCORD_INSTALL_NEEDED)); then
		prepare_discord_rpm
		targets+=("$DISCORD_RPM_TARGET")
	fi
	if module_selected signal; then prepare_signal_appimage; fi
	log "RPM package targets (${#targets[@]}): ${targets[*]}"
	phase 'Upgrade protection: checking Btrfs snapshots and free space'
	begin_system_upgrade
	phase 'Full Fedora update: using the checked metadata, with interactive confirmation'
	# Cache metadata, not RPM payloads: --cacheonly would forbid downloading
	# packages that are not already cached on a fresh workstation.
	run sudo dnf --setopt=cacheonly=metadata --best upgrade
	phase 'Selected Fedora applications: installing RPM packages'
	if module_selected bitwarden && ((BITWARDEN_INSTALL_NEEDED && ! DRY_RUN)); then verify_bitwarden_rpm "$BITWARDEN_RPM_TARGET"; fi
	if module_selected discord && ((DISCORD_INSTALL_NEEDED && ! DRY_RUN)); then verify_discord_rpm "$DISCORD_RPM_TARGET"; fi
	run sudo dnf --setopt=cacheonly=metadata --best install "${targets[@]}"
	if module_selected nix; then
		phase 'Native Fedora Nix: preparing the daemon before linking'
		setup_nix --bootstrap
	fi
}

print_manual_modules() {
	local item
	if ((${#MANUAL_MODULES[@]})); then
		printf '  Manual application work (these applications were NOT installed by dotfiles):\n'
		for item in "${MANUAL_MODULES[@]}"; do printf '    %s\n' "$item"; done
		printf '  See docs/packages.md for sources and native-install notes.\n'
	fi
}
