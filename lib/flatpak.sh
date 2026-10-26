# shellcheck shell=bash
# Explicit user-scoped Flathub installs; system remotes/apps are left alone.
selected_flatpaks() {
	FLATPAK_APPS=()
	if module_selected telegram; then FLATPAK_APPS+=(org.telegram.desktop); fi
	if module_selected gearlever; then FLATPAK_APPS+=(it.mijorus.gearlever); fi
}

inspect_user_flathub() {
	FLATHUB_PRESENT=0
	local remotes name url options
	remotes=$(flatpak remotes --user --columns=name,url,options) || die 'Could not inspect user Flatpak remotes.'
	while IFS=$'\t' read -r name url options; do
		[[ $name == flathub ]] || continue
		[[ $url == https://dl.flathub.org/repo/ || $url == https://dl.flathub.org/repo ]] || die 'Conflicting user flathub remote URL; inspect it manually.'
		[[ $options != *no-gpg-verify* && $options != *disabled* && $options != *no-enumerate* ]] || die 'User flathub remote has unsafe/unsupported options; inspect it manually.'
		FLATHUB_PRESENT=1
	done <<<"$remotes"
}

preflight_flatpaks() {
	selected_flatpaks
	((${#FLATPAK_APPS[@]})) || return 0
	((! DRY_RUN)) || return 0
	if command -v flatpak >/dev/null; then
		inspect_user_flathub
		check_selected_flatpak_origins
	fi
}

check_selected_flatpak_origins() {
	local apps app origin
	apps=$(flatpak list --user --app --columns=application) || die 'Could not list user Flatpak applications.'
	for app in "${FLATPAK_APPS[@]}"; do
		if grep -Fxq -- "$app" <<<"$apps"; then
			origin=$(flatpak info --user --show-origin "$app") || die "Could not inspect user Flatpak origin: $app"
			[[ $origin == flathub ]] || die "User Flatpak $app is from a different remote; resolve it manually."
		fi
	done
}

setup_flatpaks() {
	selected_flatpaks
	((${#FLATPAK_APPS[@]})) || return 0
	if ((DRY_RUN)); then
		log "Would configure verified user Flathub and install selected Flatpaks: ${FLATPAK_APPS[*]}"
		return 0
	fi
	inspect_user_flathub
	check_selected_flatpak_origins
	if ((! FLATHUB_PRESENT)); then
		run flatpak remote-add --user --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
		inspect_user_flathub
		((FLATHUB_PRESENT)) || die 'User Flathub remote was not created.'
	fi
	local apps app origin
	apps=$(flatpak list --user --app --columns=application) || die 'Could not list user Flatpak applications.'
	for app in "${FLATPAK_APPS[@]}"; do
		if ! grep -Fxq -- "$app" <<<"$apps"; then run flatpak install --user flathub "$app"; fi
		origin=$(flatpak info --user --show-origin "$app") || die "User Flatpak installation incomplete: $app"
		[[ $origin == flathub ]] || die "User Flatpak $app is from a different remote; resolve it manually."
	done
}

update_user_flatpaks() {
	if ((DRY_RUN)); then
		log 'Would update installed user Flatpaks if Flatpak is available; system Flatpaks stay untouched.'
		return 0
	fi
	if command -v flatpak >/dev/null; then
		phase 'User Flatpak updates: interactive, system installations untouched'
		run flatpak update --user
	fi
}
