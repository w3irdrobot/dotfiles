#!/usr/bin/env bash
set -euo pipefail
if [[ ${DEBUG:-0} == 1 ]]; then set -x; fi

ROOT=$(cd -- "$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")/.." && pwd -P)
readonly ROOT
# shellcheck source=lib/dotfiles.sh
source "$ROOT/lib/dotfiles.sh"

unit_property() {
	systemctl show "$1" --property="$2" --value || die "Could not inspect $1 ($2); no automatic service changes."
}

check_system76_dropins() {
	local unit=$1 dropins=$2 owner settings
	local fedora_default=/usr/lib/systemd/system/service.d/10-timeout-abort.conf
	[[ -n $dropins ]] || return 0
	# Fedora applies this packaged shutdown policy to every service. Accept only
	# its known setting, not arbitrary overrides merely located under /usr/lib.
	[[ $dropins == "$fedora_default" ]] || die "System76 unit has unreviewed drop-ins: $unit; review/activate it manually."
	[[ -f $fedora_default && ! -L $fedora_default ]] || die "Conflicting Fedora shutdown drop-in for $unit; inspect it manually."
	owner=$(rpm -qf --qf '%{NAME}\n' "$fedora_default") || die 'Fedora shutdown drop-in is not RPM-owned; inspect it manually.'
	[[ $owner == systemd ]] || die 'Unexpected Fedora shutdown drop-in package owner; inspect it manually.'
	settings=$(LC_ALL=C awk '
		/^[[:space:]]*($|#|;)/ { next }
		{ gsub(/^[[:space:]]+|[[:space:]]+$/, ""); print }
	' "$fedora_default") || die 'Could not inspect Fedora shutdown drop-in contents.'
	[[ $settings == $'[Service]\nTimeoutStopFailureMode=abort' ]] || die 'Fedora shutdown drop-in has unreviewed settings; inspect it manually.'
}

plan_system76_activation() {
	SYSTEM76_CONFLICTS=() SYSTEM76_MASKED=() SYSTEM76_CHANGE_NEEDED=0
	declare -gA SYSTEM76_WAS_ACTIVE=() SYSTEM76_WAS_ENABLED=()
	local unit package fragment owner state active enabled dropins
	for unit in system76-firmware-daemon.service com.system76.PowerDaemon.service system76-power-wake.service; do
		state=$(unit_property "$unit" LoadState)
		[[ $state == loaded ]] || die "Required System76 unit is missing or masked: $unit; inspect the RPM installation manually."
		fragment=$(unit_property "$unit" FragmentPath)
		case $fragment in "/usr/lib/systemd/system/$unit" | "/etc/systemd/system/$unit") ;; *) die "Unexpected System76 unit source: $unit; resolve local overrides manually." ;; esac
		dropins=$(unit_property "$unit" DropInPaths)
		check_system76_dropins "$unit" "$dropins"
		case $unit in system76-firmware-daemon.service) package=system76-firmware ;; *) package=system76-power ;; esac
		owner=$(rpm -qf --qf '%{NAME}\n' "$fragment") || die "System76 unit is not RPM-owned: $unit"
		[[ $owner == "$package" ]] || die "Unexpected System76 unit package owner: $unit"
		active=$(unit_property "$unit" ActiveState)
		enabled=$(unit_property "$unit" UnitFileState)
		case $active in active | inactive) ;; *) die "System76 unit is in an unexpected runtime state: $unit ($active); inspect it manually." ;; esac
		case $enabled in enabled | disabled) ;; *) die "System76 unit has an unsupported enablement state: $unit ($enabled); inspect it manually." ;; esac
		SYSTEM76_WAS_ACTIVE[$unit]=$active
		SYSTEM76_WAS_ENABLED[$unit]=$enabled
		if [[ $enabled != enabled || ($unit != system76-power-wake.service && $active != active) ]]; then SYSTEM76_CHANGE_NEEDED=1; fi
	done
	# Masking prevents D-Bus or another unit from reactivating a conflicting
	# backend. Keep its original enablement links intact for recovery.
	for unit in tuned.service tuned-ppd.service power-profiles-daemon.service tlp.service auto-cpufreq.service; do
		state=$(unit_property "$unit" LoadState)
		[[ $state != not-found ]] || continue
		active=$(unit_property "$unit" ActiveState)
		if [[ $state == masked ]]; then
			[[ $active == inactive ]] || die "Masked power backend is still running: $unit; resolve it manually."
			enabled=$(unit_property "$unit" UnitFileState)
			[[ $enabled == masked ]] || die "Power backend mask is not persistent: $unit; resolve it manually before activation."
			continue
		fi
		[[ $state == loaded && ($active == active || $active == inactive) ]] || die "Unexpected competing power backend state: $unit; resolve it manually."
		SYSTEM76_WAS_ACTIVE[$unit]=$active
		SYSTEM76_CONFLICTS+=("$unit")
		SYSTEM76_CHANGE_NEEDED=1
	done
}

confirm_system76_activation() {
	local answer
	if ! read -r -p 'Apply the displayed System76 service/power changes? [y/N] ' answer </dev/tty; then
		log 'No terminal confirmation received; System76 activation deferred.'
		return 1
	fi
	case ${answer,,} in y | yes) return 0 ;; *) return 1 ;; esac
}

restore_power_backends() {
	local unit power=com.system76.PowerDaemon.service
	log 'System76 power activation failed; restoring the power backend state changed by this run.'
	if [[ ${SYSTEM76_WAS_ACTIVE[$power]} == inactive ]]; then
		if ! run sudo systemctl stop "$power"; then
			log 'Could not stop System76 power; leaving competing backends masked to avoid running both. Restore the displayed services manually.'
			return 1
		fi
	fi
	if [[ ${SYSTEM76_WAS_ENABLED[$power]} == disabled ]]; then
		if ! run sudo systemctl disable "$power"; then log 'Could not restore disabled System76 power enablement; inspect it manually.'; fi
	fi
	for unit in "${SYSTEM76_MASKED[@]}"; do
		if ! run sudo systemctl unmask "$unit"; then
			log "Could not unmask $unit; restore it manually."
			continue
		fi
		if [[ ${SYSTEM76_WAS_ACTIVE[$unit]} == active ]]; then
			if ! run sudo systemctl start "$unit"; then log "Could not restart $unit; restore it manually."; fi
		fi
	done
}

activate_system76() {
	plan_system76_activation
	if ((! SYSTEM76_CHANGE_NEEDED)); then
		log 'System76 power/firmware services are already active and enabled; wake service enabled, competing backends absent/masked.'
		return 0
	fi
	log 'System76 activation plan:'
	log '  Enable/start system76-firmware-daemon.service and com.system76.PowerDaemon.service as needed.'
	log '  Enable system76-power-wake.service for suspend/resume; do not start it now.'
	local unit firmware=system76-firmware-daemon.service power=com.system76.PowerDaemon.service wake=system76-power-wake.service
	for unit in "${SYSTEM76_CONFLICTS[@]}"; do log "  Stop and persistently mask $unit (previously ${SYSTEM76_WAS_ACTIVE[$unit]}); keep its enablement links for recovery."; done
	log '  Keep Plasma PowerDevil. No firmware flashing, graphics/boot changes, privileged groups, or user notification timer changes.'
	if ! confirm_system76_activation; then
		log 'System76 activation deferred; applications remain installed. Rerun install/update in a terminal to activate them.'
		return 0
	fi
	# Firmware activation cannot remove the current power backend. Fail here
	# before masking anything if the independent firmware daemon is broken.
	if [[ ${SYSTEM76_WAS_ENABLED[$firmware]} != enabled || ${SYSTEM76_WAS_ACTIVE[$firmware]} != active ]]; then
		run sudo systemctl enable --now "$firmware" || die 'Could not activate the System76 firmware daemon; power backends were not changed.'
	fi
	if ! systemctl is-active --quiet "$firmware" || ! systemctl is-enabled --quiet "$firmware"; then
		die 'System76 firmware daemon is not active/enabled; power backends were not changed.'
	fi
	for unit in "${SYSTEM76_CONFLICTS[@]}"; do
		SYSTEM76_MASKED+=("$unit")
		if ! run sudo systemctl mask --now "$unit"; then
			restore_power_backends
			die 'Could not mask a competing power backend; review the restoration output.'
		fi
		if [[ $(unit_property "$unit" LoadState) != masked || $(unit_property "$unit" ActiveState) != inactive ]]; then
			restore_power_backends
			die 'Competing power backend is not masked/inactive; review the restoration output.'
		fi
	done
	if [[ ${SYSTEM76_WAS_ENABLED[$power]} != enabled || ${SYSTEM76_WAS_ACTIVE[$power]} != active ]]; then
		if ! run sudo systemctl enable --now "$power"; then
			restore_power_backends
			die 'Could not activate System76 power; review the restoration output. Firmware daemon may remain enabled.'
		fi
	fi
	if ! systemctl is-active --quiet "$power" || ! systemctl is-enabled --quiet "$power"; then
		restore_power_backends
		die 'System76 power failed its active/enabled check; review the restoration output.'
	fi
	if [[ ${SYSTEM76_WAS_ENABLED[$wake]} != enabled ]]; then
		run sudo systemctl enable "$wake" || die 'System76 power is running, but wake integration could not be enabled; inspect it manually.'
	fi
	systemctl is-enabled --quiet "$wake" || die 'System76 wake integration is not enabled; power/firmware services remain active.'
	log 'System76 firmware/power daemons active and enabled; suspend/resume wake integration enabled. Firmware updates remain manual.'
}

main() {
	DRY_RUN=0
	[[ $# == 0 || ($# == 1 && $1 == --check) ]] || die 'Usage: system76.sh [--check]'
	check_platform
	detect_system76
	((SYSTEM76_DETECTED)) || die 'System76 activation requires confirmed System76 hardware.'
	[[ -d /run/systemd/system ]] || die 'System76 activation requires running systemd.'
	[[ ${1:-} != --check ]] || return 0
	activate_system76
}
main "$@"
