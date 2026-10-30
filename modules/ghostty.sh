#!/usr/bin/env bash
set -euo pipefail

if [[ "${DEBUG:-0}" == "1" ]]; then
	set -x
fi

ROOT=$(cd -- "$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")/.." && pwd -P)
readonly ROOT
# shellcheck source=lib/dotfiles.sh
source "$ROOT/lib/dotfiles.sh"

configure_shortcut() {
	# Plasma 6 stores application shortcuts under the nested services group.
	kwriteconfig6 --file kglobalshortcutsrc --group services --group org.kde.konsole.desktop --key _launch none
	kwriteconfig6 --file kglobalshortcutsrc --group services --group com.mitchellh.ghostty.desktop --key _launch Ctrl+Alt+T
	if [[ -z ${DBUS_SESSION_BUS_ADDRESS:-} ]]; then
		log 'Terminal shortcut saved; it will apply at the next Plasma login.'
		return
	fi
	local owner result
	owner=$(gdbus call --session --dest org.freedesktop.DBus --object-path /org/freedesktop/DBus --method org.freedesktop.DBus.NameHasOwner org.kde.kglobalaccel)
	if [[ $owner != '(true,)' ]]; then
		log 'Terminal shortcut saved; it will apply at the next Plasma login.'
		return
	fi
	local -a accel=(gdbus call --session --dest org.kde.kglobalaccel --object-path /kglobalaccel)
	local konsole="['org.kde.konsole.desktop', '_launch', 'Konsole', 'Konsole']"
	local ghostty="['com.mitchellh.ghostty.desktop', '_launch', 'Ghostty', 'Ghostty']"
	"${accel[@]}" --method org.kde.KGlobalAccel.doRegister "$konsole" >/dev/null
	"${accel[@]}" --method org.kde.KGlobalAccel.doRegister "$ghostty" >/dev/null
	# NoAutoloading | SetPresent = 6; Qt Ctrl | Alt | T = 201326676.
	"${accel[@]}" --method org.kde.KGlobalAccel.setShortcut "$konsole" '[]' 6 >/dev/null
	result=$("${accel[@]}" --method org.kde.KGlobalAccel.setShortcut "$ghostty" '[201326676]' 6)
	[[ $result == '([201326676],)' ]] || die 'Could not assign Ctrl+Alt+T to Ghostty; check Plasma shortcut conflicts.'
}

main() {
	(($# == 0)) || die 'This setup module takes no arguments.'
	check_platform
	command -v ghostty >/dev/null 2>&1 || die 'Install the ghostty package first.'
	command -v kwriteconfig6 >/dev/null 2>&1 || die 'Install the kf6-kconfig package first.'
	command -v gdbus >/dev/null 2>&1 || die 'Install the glib2 package first.'
	# Merge only the terminal preference; never Stow the machine's kdeglobals.
	kwriteconfig6 --file kdeglobals --group General --key TerminalApplication ghostty
	kwriteconfig6 --file kdeglobals --group General --key TerminalService com.mitchellh.ghostty.desktop
	configure_shortcut
}

main "$@"
