# shellcheck shell=bash
# Read-only hardware/session discovery; entrypoints own strict mode.
detect_system76() {
	SYSTEM76_DETECTED=0 SYSTEM76_MODEL=unknown
	local vendor model
	if [[ ! -r /sys/class/dmi/id/sys_vendor ]]; then
		log 'System76 detection: DMI vendor unavailable; automatic hardware support skipped.'
		return 0
	fi
	vendor=$(</sys/class/dmi/id/sys_vendor)
	vendor=${vendor,,}
	vendor=${vendor//[[:space:]]/}
	case $vendor in
	system76 | system76inc. | system76,inc.)
		# Consumed by load_modules in lib/dotfiles.sh.
		# shellcheck disable=SC2034
		SYSTEM76_DETECTED=1
		;;
	*) return 0 ;;
	esac
	if [[ -r /sys/class/dmi/id/product_name ]]; then
		model=$(</sys/class/dmi/id/product_name)
		# DMI is machine-supplied data; never print arbitrary control characters.
		if [[ $model =~ ^[a-zA-Z0-9._\ -]+$ ]]; then SYSTEM76_MODEL=$model; fi
	fi
	log "System76 detected (model: $SYSTEM76_MODEL)."
}

report_desktop_session() {
	case ${XDG_SESSION_TYPE:-} in
	wayland) log 'Desktop session: Wayland. Fedora 44 KDE Plasma is the expected baseline.' ;;
	x11) log 'Desktop session: X11. Select Plasma (Wayland) at login for the expected baseline; setup will not switch sessions.' ;;
	*)
		if [[ -n ${WAYLAND_DISPLAY:-} ]]; then
			log 'Desktop session: Wayland display present; session type unspecified.'
		else
			log 'Desktop session: unknown/TTY; continuing without changing desktop or login settings.'
		fi
		;;
	esac
}

system76_next_steps() {
	printf '  System76 packages selected for %s. Install/update offers confirmed power/firmware service activation; linking alone does not activate services.\n' "$SYSTEM76_MODEL"
	printf '  Review the activation output; if deferred, rerun install/update in a terminal. Resolve unknown backend conflicts manually; keep Plasma PowerDevil.\n'
	printf '  Review firmware-manager permissions/polkit locally; no privileged group membership was added. Firmware updates remain manual.\n'
}
