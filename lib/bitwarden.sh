# shellcheck shell=bash
# Native upstream RPM preparation; the CLI owns protected DNF transactions.
load_bitwarden_pin() {
	local pin
	command -v python3 >/dev/null || die 'Python 3 is required to validate the Bitwarden release pin.'
	pin=$(python3 "$ROOT/scripts/check-updates.py" --print-bitwarden-pin) || die 'Could not validate the Bitwarden release pin.'
	IFS='|' read -r BITWARDEN_VERSION BITWARDEN_URL BITWARDEN_SHA256 <<<"$pin"
	BITWARDEN_RPM_TARGET=${XDG_CACHE_HOME:-$HOME/.cache}/dotfiles/bitwarden/$BITWARDEN_VERSION/Bitwarden-$BITWARDEN_VERSION-x86_64.rpm
	[[ $BITWARDEN_RPM_TARGET == /* ]] || die 'Bitwarden cache directory must be absolute.'
}

check_bitwarden_cache() {
	local parent=${BITWARDEN_RPM_TARGET%/*}
	while [[ $parent != "$HOME" && $parent != / ]]; do
		[[ ! -L $parent && (! -e $parent || -d $parent) ]] || die "Conflicting Bitwarden cache parent: $parent"
		parent=${parent%/*}
		[[ -n $parent ]] || parent=/
	done
	[[ ! -L $BITWARDEN_RPM_TARGET && (! -e $BITWARDEN_RPM_TARGET || -f $BITWARDEN_RPM_TARGET) ]] || die 'Conflicting Bitwarden RPM cache destination; inspect it manually.'
}

check_bitwarden_executable() {
	local target owner
	[[ -x /usr/bin/bitwarden ]] || die 'Installed Bitwarden RPM is missing its native executable; repair the package before continuing.'
	target=$(realpath -e -- /usr/bin/bitwarden) || die 'Could not resolve the native Bitwarden launcher; inspect it manually.'
	# The vendor RPM owns /opt/Bitwarden/bitwarden. Its post-install script
	# creates /usr/bin/bitwarden through alternatives (or a direct symlink),
	# so the launcher itself is not necessarily recorded as RPM-owned.
	case $target in
	/opt/Bitwarden/bitwarden | /usr/bin/bitwarden) ;;
	*) die 'Native Bitwarden launcher resolves to an unexpected executable; inspect it manually.' ;;
	esac
	owner=$(rpm -qf --qf '%{NAME}\n' "$target") || die 'Bitwarden launcher target is not an RPM-owned native executable; inspect it manually.'
	[[ $owner == bitwarden ]] || die 'Native Bitwarden executable must be owned by the bitwarden RPM; installation is incomplete.'
}

preflight_bitwarden() {
	load_bitwarden_pin
	check_bitwarden_cache
	BITWARDEN_INSTALL_NEEDED=1
	local installed status comparison
	if [[ -e /usr/bin/bitwarden || -L /usr/bin/bitwarden ]]; then
		check_bitwarden_executable
	fi
	if installed=$(rpm -q --qf '%{VERSION}\n' bitwarden 2>/dev/null); then
		check_bitwarden_executable
		comparison=$(python3 "$ROOT/scripts/check-updates.py" --compare-bitwarden "$installed") || die 'Could not compare the installed Bitwarden RPM with its reviewed pin.'
		if [[ $comparison == equal || $comparison == newer ]]; then
			# Consumed by install_packages in lib/fedora.sh.
			# shellcheck disable=SC2034
			BITWARDEN_INSTALL_NEEDED=0
			log "Keeping installed Bitwarden $installed (reviewed pin: $BITWARDEN_VERSION); no downgrade or re-download."
		fi
	else
		status=$?
		[[ $status == 1 ]] || die 'Could not inspect the installed Bitwarden RPM; refusing package transactions.'
	fi
}

verify_bitwarden_rpm() {
	local target=$1 metadata
	printf '%s  %s\n' "$BITWARDEN_SHA256" "$target" | sha256sum --check --strict --status - || die 'Bitwarden RPM checksum mismatch; nothing installed. Inspect cached files manually.'
	metadata=$(rpm -qp --qf '%{NAME}|%{VERSION}|%{RELEASE}|%{ARCH}\n' "$target") || die 'Could not inspect the verified Bitwarden RPM header.'
	[[ $metadata == "bitwarden|$BITWARDEN_VERSION|1|x86_64" ]] || die 'Bitwarden RPM name/version/release/architecture does not match the reviewed artifact.'
}

prepare_bitwarden_rpm() (
	local target=$BITWARDEN_RPM_TARGET temp
	if ((DRY_RUN)); then
		log "Would download/verify pinned Bitwarden $BITWARDEN_VERSION before package transactions."
		return 0
	fi
	check_bitwarden_cache
	if [[ -f $target ]]; then
		verify_bitwarden_rpm "$target"
		log "Reusing verified Bitwarden RPM: $target"
		return 0
	fi
	umask 077
	mkdir -p -- "${target%/*}"
	temp=$(mktemp -d "${target%/*}/.download.XXXXXXXX")
	trap 'rm -rf -- "$temp"' EXIT
	curl --proto '=https' --tlsv1.2 --fail --silent --show-error --location \
		--output "$temp/bitwarden.rpm" "$BITWARDEN_URL"
	verify_bitwarden_rpm "$temp/bitwarden.rpm"
	# Publish only a verified RPM, atomically, without replacing a new conflict.
	ln -- "$temp/bitwarden.rpm" "$target"
)

validate_bitwarden_install() {
	check_bitwarden_executable
}

check_bitwarden_release_notice() {
	local inspect=0 status
	if ((DRY_RUN)); then
		log 'Would check for a new Bitwarden desktop release after the system update; dry-run makes no network requests.'
		return 0
	fi
	if module_selected bitwarden; then
		inspect=1
	elif rpm -q bitwarden >/dev/null 2>&1; then
		inspect=1
	else
		status=$?
		if [[ $status != 1 ]]; then log 'Warning: could not inspect installed Bitwarden; release status is unknown.'; fi
	fi
	if ((inspect)); then
		if ! python3 "$ROOT/scripts/check-updates.py" --only bitwarden; then
			log 'Warning: Bitwarden release check failed; update status is unknown. OS updates completed; retry dotfiles check-updates later.'
		fi
	fi
}
