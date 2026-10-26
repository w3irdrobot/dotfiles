# shellcheck shell=bash
# Vendor bootstrap RPM; never execute the installed launcher during validation.
preflight_discord() {
	local pin installed comparison status owner
	pin=$(python3 "$ROOT/scripts/check-updates.py" --print-discord-pin) || die 'Could not validate Discord RPM pin.'
	IFS='|' read -r DISCORD_VERSION DISCORD_URL DISCORD_SHA256 <<<"$pin"
	DISCORD_RPM_TARGET=${XDG_CACHE_HOME:-$HOME/.cache}/dotfiles/discord/$DISCORD_VERSION/discord-$DISCORD_VERSION.rpm
	check_discord_cache
	DISCORD_INSTALL_NEEDED=1
	if [[ -e /usr/bin/discord || -L /usr/bin/discord ]]; then
		owner=$(rpm -qf --qf '%{NAME}\n' /usr/bin/discord) || die 'Unmanaged Discord launcher; inspect it manually.'
		[[ $owner == discord && -x /usr/bin/discord ]] || die 'Discord launcher must be executable and owned by the discord RPM.'
	fi
	if installed=$(rpm -q --qf '%{VERSION}\n' discord 2>/dev/null); then
		[[ -x /usr/bin/discord ]] || die 'Installed Discord RPM is missing its launcher; repair it manually.'
		comparison=$(python3 "$ROOT/scripts/check-updates.py" --compare-discord "$installed") || die 'Could not compare installed Discord RPM.'
		if [[ $comparison == equal || $comparison == newer ]]; then
			# Read by install_packages in lib/fedora.sh.
			# shellcheck disable=SC2034
			DISCORD_INSTALL_NEEDED=0
			log "Keeping installed Discord RPM $installed; no downgrade or re-download."
		fi
	else
		status=$?
		[[ $status == 1 ]] || die 'Could not query installed Discord RPM; refusing package transactions.'
	fi
}

check_discord_cache() {
	[[ $DISCORD_RPM_TARGET == /* ]] || die 'Discord cache directory must be absolute.'
	local parent=${DISCORD_RPM_TARGET%/*}
	while [[ $parent != "$HOME" && $parent != / ]]; do
		[[ ! -L $parent && (! -e $parent || -d $parent) ]] || die "Conflicting Discord cache parent: $parent"
		parent=${parent%/*}
		[[ -n $parent ]] || parent=/
	done
	[[ ! -L $DISCORD_RPM_TARGET && (! -e $DISCORD_RPM_TARGET || -f $DISCORD_RPM_TARGET) ]] || die 'Conflicting Discord RPM cache destination.'
}

verify_discord_rpm() {
	local target=$1 metadata
	printf '%s  %s\n' "$DISCORD_SHA256" "$target" | sha256sum --check --strict --status - || die 'Discord RPM checksum mismatch; inspect cache manually.'
	metadata=$(rpm -qp --qf '%{NAME}|%{VERSION}|%{RELEASE}|%{ARCH}\n' "$target") || die 'Could not inspect Discord RPM header.'
	[[ $metadata == "discord|$DISCORD_VERSION|1|x86_64" ]] || die 'Discord RPM identity does not match the reviewed artifact.'
}

prepare_discord_rpm() (
	local target=$DISCORD_RPM_TARGET temp
	if ((DRY_RUN)); then
		log "Would download/verify pinned Discord RPM $DISCORD_VERSION before package transactions."
		return 0
	fi
	check_discord_cache
	if [[ -f $target ]]; then
		verify_discord_rpm "$target"
		return 0
	fi
	umask 077
	mkdir -p -- "${target%/*}"
	temp=$(mktemp -d "${target%/*}/.download.XXXXXXXX")
	trap 'rm -rf -- "$temp"' EXIT
	curl --proto '=https' --proto-redir '=https' --tlsv1.2 --fail --silent --show-error --location --output "$temp/discord.rpm" "$DISCORD_URL"
	verify_discord_rpm "$temp/discord.rpm"
	ln -- "$temp/discord.rpm" "$target"
)

validate_discord_install() {
	local owner
	owner=$(rpm -qf --qf '%{NAME}\n' /usr/bin/discord) || die 'Discord installation did not provide an RPM-owned launcher.'
	[[ $owner == discord && -x /usr/bin/discord ]] || die 'Discord RPM installation is incomplete.'
	log 'Discord vendor bootstrap RPM installed; first launch downloads the client. No application was launched.'
}

check_discord_release_notice() {
	if ((DRY_RUN)); then
		log 'Would check for a new Discord bootstrap RPM after updating; no network requests in dry-run.'
		return 0
	fi
	local status
	if module_selected discord || rpm -q discord >/dev/null 2>&1; then
		if ! python3 "$ROOT/scripts/check-updates.py" --only discord; then log 'Warning: Discord release check failed; status unknown. OS updates completed; retry dotfiles check-updates.'; fi
	else
		status=$?
		if [[ $status != 1 ]]; then log 'Warning: could not inspect installed Discord; release status unknown.'; fi
	fi
}
