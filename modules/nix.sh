# shellcheck shell=bash
# Sourced helpers: the CLI owns strict mode, package transactions, and Stow.
# Arch ships the daemon units, nixbld sysusers, and daemon-socket tmpfiles.
# https://archlinux.org/packages/extra/x86_64/nix/files/

nix_package_owned() {
	local owner status
	if owner=$(pacman -Qqo -- /usr/bin/nix 2>/dev/null); then
		[[ $owner == nix ]]
	else
		status=$?
		[[ $status == 1 ]] || die 'Could not inspect native Nix package ownership; repair the pacman database.'
		return 1
	fi
}

preflight_nix() {
	[[ -d /run/systemd/system ]] || die 'Native Nix daemon setup requires running systemd.'
	if nix_package_owned; then
		[[ -x /usr/bin/nix ]] || die 'Package-owned native Nix is incomplete; repair the nix package before continuing.'
		return 0
	fi
	if [[ -e /usr/bin/nix || -L /usr/bin/nix || -e /nix || -L /nix || -e /etc/nix || -L /etc/nix ]] || command -v nix >/dev/null; then
		die 'Unmanaged or partial Nix installation detected; inspect and repair it manually before installing native Nix. Never mix installation methods.'
	fi
	local status
	if pacman -Qq nix >/dev/null 2>&1; then
		die 'Installed nix package is missing its owned native binary; repair it before continuing.'
	else
		status=$?
		[[ $status == 1 ]] || die 'Could not inspect the installed nix package; repair the pacman database.'
	fi
}

validate_nix() {
	local mode=${1:-client} configuration features
	[[ $# -le 1 && ($mode == bootstrap || $mode == client) ]] || die 'Usage: validate_nix [bootstrap|client]'
	nix_package_owned || die 'Native /usr/bin/nix must be owned by the nix package; no upstream installer fallback.'
	[[ -x /usr/bin/nix ]] || die 'Native Nix binary is missing or not executable; repair the nix package.'
	if ((DRY_RUN)); then
		log "Would validate the native Nix daemon and $mode client feature configuration."
		return 0
	fi
	systemctl is-active --quiet nix-daemon.service || die 'Native Nix daemon service is not active; repair it before continuing.'
	[[ -S /nix/var/nix/daemon-socket/socket ]] || die 'Native Nix daemon socket is missing; repair the service before continuing.'
	/usr/bin/nix --extra-experimental-features 'nix-command flakes' store ping --store daemon >/dev/null || die 'Native Nix daemon is not responding; repair it before continuing.'
	# Bootstrap runs before Stow and supplies feature flags explicitly. After links,
	# validate_nix (or validate_nix client) must check the actual user configuration.
	if [[ $mode == client ]]; then
		configuration=$(/usr/bin/nix config show) || die 'Nix client configuration could not be read; check the linked user nix.conf.'
		features=$(printf '%s\n' "$configuration" | sed -n 's/^experimental-features = //p')
		[[ " $features " == *' flakes '* && " $features " == *' nix-command '* ]] || die 'Nix client needs experimental-features = nix-command flakes; link the user nix.conf before validating client mode.'
	fi
}

wait_nix_daemon_ready() {
	if ((DRY_RUN)); then
		log 'Would wait for the native Nix daemon socket and store ping.'
		return 0
	fi
	# Type=simple can report active before the daemon binds its socket. Use one
	# elapsed-time budget, not an attempt count: slow pings consume the same budget.
	# timeout's kill grace and SECONDS' resolution allow at most 32 seconds total.
	local deadline=$((SECONDS + 30)) remaining ping_limit status
	while ((SECONDS < deadline)); do
		timeout --kill-after=1s 1s systemctl is-active --quiet nix-daemon.service || die 'Native Nix daemon service is not active (inactive/failed) or its state check timed out; repair it before continuing.'
		remaining=$((deadline - SECONDS))
		((remaining > 0)) || break
		if [[ -S /nix/var/nix/daemon-socket/socket ]]; then
			ping_limit=$remaining
			((ping_limit <= 5)) || ping_limit=5
			if timeout --kill-after=1s "${ping_limit}s" /usr/bin/nix --extra-experimental-features 'nix-command flakes' store ping --store daemon >/dev/null; then
				((SECONDS < deadline)) && return 0
				break
			else
				status=$?
				# Only a bounded probe timeout is retryable; preserve Nix's stderr
				# and stop on configuration, permissions, or other unexpected errors.
				[[ $status == 124 || $status == 137 ]] || die "Native Nix daemon is not responding: store ping failed (exit $status); repair it before continuing."
			fi
		fi
		((SECONDS < deadline)) || break
		sleep 1
	done
	die 'Native Nix daemon readiness timed out after a 30-second budget (32-second maximum); socket/store ping did not become ready. Inspect systemctl status and journalctl -u nix-daemon.service.'
}

setup_nix() {
	[[ $# == 0 || ($# == 1 && $1 == --bootstrap) ]] || die 'Usage: setup_nix [--bootstrap]'
	preflight_nix
	if ((DRY_RUN)); then
		run sudo systemctl enable --now nix-daemon.service
		return 0
	fi
	nix_package_owned || die 'Install the native nix package before setup_nix; no upstream installer fallback.'
	run sudo systemctl enable --now nix-daemon.service || die 'Could not enable/start the native Nix daemon service.'
	wait_nix_daemon_ready
	validate_nix bootstrap
}
