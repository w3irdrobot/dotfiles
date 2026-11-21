#!/usr/bin/env bash
set -euo pipefail

if [[ "${DEBUG:-0}" == "1" ]]; then
	set -x
fi

ROOT=$(cd -- "$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")/.." && pwd -P)
readonly ROOT
# shellcheck source=lib/dotfiles.sh
source "$ROOT/lib/dotfiles.sh"

# Top-level packages only; DNF removes their now-unused dependencies.
UNWANTED=(
	# KDE email/calendar suite and its Akonadi backend
	kmail kontact korganizer kaddressbook akregator kleopatra akonadi-import-wizard
	grantlee-editor pim-sieve-editor pim-data-exporter kdepim-addons kdepim-runtime
	akonadi-server akonadi-server-mysql
	# Games
	kmahjongg kpat kmines
	# Niche KDE apps
	kamoso kmouth qrca krfb krdc neochat kde-connect
	# Plasma extras and browser
	plasma-welcome plasma-welcome-fedora plasma-discover plasma-discover-notifier firefox
)

main() {
	(($# == 0)) || die 'This setup module takes no arguments.'
	check_platform
	local package
	local -a installed=()
	for package in "${UNWANTED[@]}"; do
		if rpm -q --quiet "$package"; then installed+=("$package"); fi
	done
	if ((${#installed[@]} == 0)); then
		log 'No unwanted Fedora defaults are installed.'
		return 0
	fi
	log "Removing unwanted Fedora defaults: ${installed[*]}"
	sudo dnf remove "${installed[@]}"
}

main "$@"
