#!/usr/bin/env bash
# Fedora system layer: RPMs, Flatpaks, pinned vendor apps, services, desktop
# tweaks, then the Home Manager user environment. Safe to rerun.
set -euo pipefail

if [[ "${DEBUG:-0}" == "1" ]]; then
	set -x
fi

ROOT=$(cd -- "$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")" && pwd -P)
readonly ROOT

# Vendor repositories from repos/, installed as /etc/yum.repos.d/dotfiles-<name>.repo.
REPOSITORIES=(brave ghostty tailscale vscodium)

PACKAGES=(
	git curl gnupg2 pinentry python3 bash-completion man-db man-pages
	nix nix-daemon flatpak libsecret fuse-libs
	kf6-kconfig glib2 xdg-desktop-portal-kde
	brave-browser ghostty codium tailscale
)

FLATPAKS=(org.telegram.desktop com.spotify.Client it.mijorus.gearlever)

# Fedora KDE defaults this setup does not use.
UNWANTED=(
	kmail kontact korganizer kaddressbook akregator kleopatra akonadi-import-wizard
	grantlee-editor pim-sieve-editor pim-data-exporter kdepim-addons kdepim-runtime
	akonadi-server akonadi-server-mysql
	kmahjongg kpat kmines
	kamoso kmouth qrca krfb krdc neochat kde-connect
	plasma-welcome plasma-welcome-fedora plasma-discover plasma-discover-notifier firefox
)

# Pinned vendor downloads. Check each vendor's checksum and signature when bumping.
# Bitwarden: SHA256 from the GitHub release asset digest (RPM is unsigned).
readonly BITWARDEN_VERSION=2026.10.4
readonly BITWARDEN_URL=https://github.com/bitwarden/clients/releases/download/desktop-v$BITWARDEN_VERSION/Bitwarden-$BITWARDEN_VERSION-x86_64.rpm
readonly BITWARDEN_SHA256=09abe8983dc493e107e9ae6f7b3f164cf58141cf4e74456611d7200d514576fd
# Discord: no vendor checksum or signature; SHA256 of the reviewed HTTPS download.
readonly DISCORD_VERSION=1.0.169
readonly DISCORD_URL=https://stable.dl2.discordapp.net/distro/app/stable/linux/x64/$DISCORD_VERSION/Discord.rpm
readonly DISCORD_SHA256=ef32125248e2a694a8683a695525a397e56d6ef3afe19c1adb401f6d4b566fad
# Proton Mail: SHA512 from https://proton.me/download/mail/linux/version.json,
# signed RPM (https://proton.me/support/mail-desktop-verify-rpm-fedora).
readonly PROTON_MAIL_VERSION=1.16.1
readonly PROTON_MAIL_URL=https://proton.me/download/mail/linux/$PROTON_MAIL_VERSION/ProtonMail-desktop-beta.rpm
readonly PROTON_MAIL_SHA512=1d2ea724d71a12e9469620ce325e104be722c64394ad643d9e7d9fa81b9bdfb91b432f8e82ee499628a6f1d15ecff79e1ccdcaeb61db535b1265f02fa7943620
readonly PROTON_MAIL_FINGERPRINT=1c27df7a717bcbcac760a84c0db4b0701e5fb04a
# Signal: initial AppImage only; Signal updates itself afterwards.
readonly SIGNAL_VERSION=8.35.0
readonly SIGNAL_SHA256=1ed1c81f5155284ea8fe8e5a2282ccd1f9650d71c59845534d1eeef967b1088d
readonly SIGNAL_KEY_SHA256=f601d18a2a9fbdf2bd11379a90952dd8a3b8ab9776aeccabc539da63461f04f2
readonly SIGNAL_FINGERPRINT=4B16B7232DFAA439AD791002EF9F501F13EED94C
readonly SIGNAL_DIRECTORY=$HOME/.local/share/dotfiles/signal

log() { printf '\033[1mdotfiles:\033[0m %s\n' "$*" >&2; }
die() {
	printf 'dotfiles: %s\n' "$*" >&2
	exit 1
}

usage() {
	cat <<'EOF'
Usage: bootstrap.sh [--docker] [--yubikey] [--bitcoin]

Sets up Fedora KDE (RPMs, Flatpaks, vendor apps, services, Plasma tweaks) and
switches the Home Manager environment. Safe to rerun.

  --docker   Install Docker (moby-engine). Group membership stays manual.
  --yubikey  Install YubiKey Manager and smart card support.
  --bitcoin  Install Bitcoin Core. Set `bitcoin = true` in home.nix for configs.
EOF
}

download() {
	curl --proto '=https' --proto-redir '=https' --tlsv1.2 --fail --silent --show-error --location --output "$2" "$1"
}

check_platform() {
	local id version
	id=$(sed -n 's/^ID=//p' /etc/os-release)
	version=$(sed -n 's/^VERSION_ID=//p' /etc/os-release)
	[[ $id == fedora && $version -ge 44 ]] || die 'Fedora 44 or newer is required.'
	[[ ! -e /run/ostree-booted ]] || die 'Fedora Atomic is unsupported; use the regular KDE edition.'
	[[ $(uname -m) == x86_64 ]] || die 'Only x86_64 is supported.'
	((EUID != 0)) || die 'Run as your regular user, not root.'
}

is_system76() {
	[[ -r /sys/class/dmi/id/sys_vendor && $(</sys/class/dmi/id/sys_vendor) == *[Ss]ystem76* ]]
}

add_repositories() {
	local name
	for name in "${REPOSITORIES[@]}"; do
		if ! cmp -s "$ROOT/repos/$name.repo" "/etc/yum.repos.d/dotfiles-$name.repo"; then
			log "Adding repository: $name"
			sudo install -m 0644 "$ROOT/repos/$name.repo" "/etc/yum.repos.d/dotfiles-$name.repo"
		fi
	done
}

install_packages() {
	log 'Updating Fedora'
	sudo dnf upgrade --refresh
	log 'Installing Fedora packages'
	sudo dnf install "${PACKAGES[@]}"
}

remove_unwanted() {
	local package
	local -a installed=()
	for package in "${UNWANTED[@]}"; do
		if rpm -q --quiet "$package"; then installed+=("$package"); fi
	done
	if ((${#installed[@]})); then
		log "Removing unused Fedora defaults: ${installed[*]}"
		sudo dnf remove "${installed[@]}"
	fi
}

# Installs a vendor RPM after verifying its checksum and, when given, its signature.
# Keeps an installed copy that is the same version or newer.
install_pinned_rpm() {
	local name=$1 version=$2 url=$3 algorithm=$4 digest=$5 key=${6:-} fingerprint=${7:-}
	local installed rpm=$WORK/$name.rpm
	if installed=$(rpm -q --qf '%{VERSION}' "$name" 2>/dev/null); then
		if [[ $(printf '%s\n%s\n' "$installed" "$version" | sort -V | tail -n1) == "$installed" ]]; then
			log "Keeping $name $installed (pinned $version)"
			return 0
		fi
	fi
	log "Installing $name $version"
	download "$url" "$rpm"
	printf '%s  %s\n' "$digest" "$rpm" | "${algorithm}sum" --check --strict --status - || die "$name checksum mismatch."
	if [[ -n $key ]]; then
		# A throwaway keyring leaves the system RPM keyring untouched.
		local -a keyring=(--dbpath "$WORK/$name-db" --define "_keyringpath $WORK/$name-keys" --define '_keyring fs')
		mkdir -- "$WORK/$name-db" "$WORK/$name-keys"
		rpmkeys "${keyring[@]}" --import "$key"
		[[ -f $WORK/$name-keys/gpg-pubkey-$fingerprint.key ]] || die "$name signing key does not match the pinned fingerprint."
		rpmkeys "${keyring[@]}" --checksig "$rpm" >/dev/null || die "$name signature check failed."
	fi
	[[ $(rpm -qp --qf '%{NAME}|%{VERSION}' "$rpm") == "$name|$version" ]] || die "$name RPM does not match the pinned version."
	sudo dnf install "$rpm"
}

install_vendor_rpms() {
	install_pinned_rpm bitwarden "$BITWARDEN_VERSION" "$BITWARDEN_URL" sha256 "$BITWARDEN_SHA256"
	install_pinned_rpm discord "$DISCORD_VERSION" "$DISCORD_URL" sha256 "$DISCORD_SHA256"
	install_pinned_rpm proton-mail "$PROTON_MAIL_VERSION" "$PROTON_MAIL_URL" sha512 "$PROTON_MAIL_SHA512" \
		"$ROOT/repos/RPM-GPG-KEY-proton-mail" "$PROTON_MAIL_FINGERPRINT"
}

install_signal() {
	if [[ -x $SIGNAL_DIRECTORY/Signal.AppImage ]]; then
		log 'Keeping installed Signal; it updates itself'
		return 0
	fi
	log "Installing Signal $SIGNAL_VERSION"
	local url=https://updates.signal.org/desktop/signal-desktop_${SIGNAL_VERSION}_x86_64.AppImage status
	download "$url" "$WORK/Signal.AppImage"
	download "$url.gpg" "$WORK/Signal.AppImage.gpg"
	download https://updates.signal.org/static/desktop/appimage.asc "$WORK/signal.asc"
	printf '%s  %s\n%s  %s\n' "$SIGNAL_SHA256" "$WORK/Signal.AppImage" "$SIGNAL_KEY_SHA256" "$WORK/signal.asc" |
		sha256sum --check --strict --status - || die 'Signal AppImage or key checksum mismatch.'
	mkdir -m 0700 -- "$WORK/gnupg"
	gpg --batch --homedir "$WORK/gnupg" --output "$WORK/signal.gpg" --dearmor "$WORK/signal.asc"
	status=$(gpgv --homedir "$WORK/gnupg" --keyring "$WORK/signal.gpg" --status-fd 1 \
		"$WORK/Signal.AppImage.gpg" "$WORK/Signal.AppImage") || die 'Signal signature check failed.'
	grep -q "VALIDSIG .*$SIGNAL_FINGERPRINT" <<<"$status" || die 'Signal was not signed by the pinned key.'
	mkdir -p -- "$SIGNAL_DIRECTORY"
	install -m 0700 "$WORK/Signal.AppImage" "$SIGNAL_DIRECTORY/Signal.AppImage"
}

install_flatpaks() {
	log "Installing Flatpaks: ${FLATPAKS[*]}"
	flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
	flatpak install --user --or-update flathub "${FLATPAKS[@]}"
}

setup_system76() {
	is_system76 || return 0
	log 'System76 hardware: installing drivers and power management'
	sudo install -m 0644 "$ROOT/repos/system76.repo" /etc/yum.repos.d/dotfiles-system76.repo
	sudo dnf install system76-driver system76-firmware system76-power firmware-manager
	# system76-power replaces Fedora's power profile daemons.
	local unit
	for unit in tuned.service tuned-ppd.service power-profiles-daemon.service; do
		if [[ $(systemctl show "$unit" --property=LoadState --value) == loaded ]]; then
			sudo systemctl mask --now "$unit"
		fi
	done
	sudo systemctl enable --now system76-firmware-daemon.service com.system76.PowerDaemon.service
	sudo systemctl enable system76-power-wake.service
}

install_optional() {
	local docker=$1 yubikey=$2 bitcoin=$3
	if ((docker)); then sudo dnf install moby-engine docker-cli docker-compose docker-buildx; fi
	if ((yubikey)); then sudo dnf install yubikey-manager pcsc-lite pcsc-lite-ccid; fi
	if ((bitcoin)); then sudo dnf install bitcoin-core-server bitcoin-core-utils; fi
}

# Ghostty replaces Konsole as Plasma's terminal and Ctrl+Alt+T target.
configure_plasma() {
	log 'Setting Ghostty as the Plasma terminal'
	kwriteconfig6 --file kdeglobals --group General --key TerminalApplication ghostty
	kwriteconfig6 --file kdeglobals --group General --key TerminalService com.mitchellh.ghostty.desktop
	kwriteconfig6 --file kglobalshortcutsrc --group services --group org.kde.konsole.desktop --key _launch none
	kwriteconfig6 --file kglobalshortcutsrc --group services --group com.mitchellh.ghostty.desktop --key _launch Ctrl+Alt+T
	if [[ -z ${DBUS_SESSION_BUS_ADDRESS:-} ]] ||
		[[ $(gdbus call --session --dest org.freedesktop.DBus --object-path /org/freedesktop/DBus \
			--method org.freedesktop.DBus.NameHasOwner org.kde.kglobalaccel) != '(true,)' ]]; then
		log 'Terminal shortcut applies at the next Plasma login.'
		return 0
	fi
	local -a accel=(gdbus call --session --dest org.kde.kglobalaccel --object-path /kglobalaccel)
	local konsole="['org.kde.konsole.desktop', '_launch', 'Konsole', 'Konsole']"
	local ghostty="['com.mitchellh.ghostty.desktop', '_launch', 'Ghostty', 'Ghostty']"
	"${accel[@]}" --method org.kde.KGlobalAccel.doRegister "$konsole" >/dev/null
	"${accel[@]}" --method org.kde.KGlobalAccel.doRegister "$ghostty" >/dev/null
	# NoAutoloading | SetPresent = 6; Qt Ctrl | Alt | T = 201326676.
	"${accel[@]}" --method org.kde.KGlobalAccel.setShortcut "$konsole" '[]' 6 >/dev/null
	"${accel[@]}" --method org.kde.KGlobalAccel.setShortcut "$ghostty" '[201326676]' 6 >/dev/null
}

setup_vscodium() {
	local installed extension
	installed=$(codium --list-extensions)
	if ! grep -Fxiq w3irdrobot.kestrel-theme <<<"$installed"; then
		log 'Installing the Kestrel VSCodium theme'
		python3 "$ROOT/scripts/build-vscodium-theme.py" --output "$WORK/kestrel.vsix"
		codium --install-extension "$WORK/kestrel.vsix"
	fi
	while IFS= read -r extension; do
		if [[ -n $extension ]] && ! grep -Fxiq "$extension" <<<"$installed"; then
			codium --install-extension "$extension"
		fi
	done <"$ROOT/files/vscodium/.config/VSCodium/extensions.txt"
}

switch_home_manager() {
	log 'Starting the Nix daemon'
	sudo systemctl enable --now nix-daemon.service
	log 'Switching the Home Manager environment'
	# -b moves Fedora's default dotfiles (and any stale links) aside as *.backup.
	nix --extra-experimental-features 'nix-command flakes' run "$ROOT#home-manager" -- \
		switch --flake "$ROOT#alex" -b backup
}

print_next_steps() {
	cat >&2 <<'EOF'

Done. Manual follow-ups:
  - Log out and back in so Plasma picks up the new environment and fonts.
  - Tailscale: sudo systemctl enable --now tailscaled && sudo tailscale up
               sudo tailscale set --operator="$USER"
  - Bitwarden: sign in, unlock, and enable the SSH agent.
  - Machine-local exports go in ~/.config/bash/variables.sh (see examples/).
  - Git identity/signing goes in ~/.gitconfig_local.
EOF
}

main() {
	local docker=0 yubikey=0 bitcoin=0
	while (($#)); do
		case $1 in
		--docker) docker=1 ;;
		--yubikey) yubikey=1 ;;
		--bitcoin) bitcoin=1 ;;
		-h | --help)
			usage
			return 0
			;;
		*)
			usage >&2
			return 2
			;;
		esac
		shift
	done
	check_platform
	WORK=$(mktemp -d)
	trap 'rm -rf -- "$WORK"' EXIT

	add_repositories
	install_packages
	remove_unwanted
	install_vendor_rpms
	install_signal
	install_flatpaks
	setup_system76
	install_optional "$docker" "$yubikey" "$bitcoin"
	configure_plasma
	setup_vscodium
	switch_home_manager
	print_next_steps
}

main "$@"
