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

# shellcheck source=./pins.sh
source "$ROOT/pins.sh"
readonly SSH_REMOTE=git@github.com:w3irdrobot/dotfiles.git
readonly AGENTFILES_REMOTE=git@github.com:w3irdrobot/agentfiles.git
readonly AGENTFILES=$HOME/projects/github.com/w3irdrobot/agentfiles

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

install_vendor_rpms() {
	"$ROOT/scripts/vendor-pins.sh" install
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

setup_tailscale() {
	log 'Enabling Tailscale'
	sudo systemctl enable --now tailscaled.service
	# Lets tailscale up/down/set run without sudo. Login stays manual.
	sudo tailscale set --operator="$USER"
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
	cat >&2 <<EOF

Done. Manual follow-ups:
  - Log out and back in so Plasma picks up the new environment and fonts.
  - Tailscale: tailscale up
  - Bitwarden: sign in, unlock, and enable the SSH agent.
  - Secrets: run secrets_export on the old machine, then secrets_import here.
  - Once SSH works, switch this checkout off HTTPS and set up agent config:
      git -C "$ROOT" remote set-url origin $SSH_REMOTE
      git clone $AGENTFILES_REMOTE $AGENTFILES
      $AGENTFILES/link.py --tools maple,codex,claude,opencode
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
	install_flatpaks
	setup_tailscale
	setup_system76
	install_optional "$docker" "$yubikey" "$bitcoin"
	configure_plasma
	setup_vscodium
	switch_home_manager
	print_next_steps
}

main "$@"
