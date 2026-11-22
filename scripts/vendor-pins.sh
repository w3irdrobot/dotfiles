#!/usr/bin/env bash
# Manages the pinned vendor apps in pins.sh.
#   check    Report newer releases. Changes nothing.
#   bump     Download each newer release, verify the vendor checksum (Discord
#            publishes none, so its hash is taken from the HTTPS download), and
#            rewrite pins.sh.
#   install  Install the pinned RPMs and Signal after verifying checksums and,
#            where published, signatures. Keeps installed copies that are as new.
# shellcheck source-path=SCRIPTDIR
set -euo pipefail

if [[ "${DEBUG:-0}" == "1" ]]; then
	set -x
fi

ROOT=$(cd -- "$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")/.." && pwd -P)
readonly ROOT
readonly PINS=$ROOT/pins.sh
# shellcheck source=../pins.sh
source "$PINS"

readonly BITWARDEN_RELEASES='https://api.github.com/repos/bitwarden/clients/releases?per_page=50'
readonly DISCORD_LATEST='https://discord.com/api/download/stable?platform=linux&format=rpm'
readonly PROTON_MAIL_RELEASES=https://proton.me/download/mail/linux/version.json
readonly PROTON_MAIL_KEY=$ROOT/repos/RPM-GPG-KEY-proton-mail
readonly SIGNAL_DOWNLOADS=https://updates.signal.org/desktop
readonly SIGNAL_MANIFEST=$SIGNAL_DOWNLOADS/latest-linux.yml
readonly SIGNAL_KEY_URL=https://updates.signal.org/static/desktop/appimage.asc
# ~/.local/bin/signal-desktop (files/signal) launches the AppImage from here.
readonly SIGNAL_DIRECTORY=$HOME/.local/share/dotfiles/signal

log() { printf '%s\n' "$*" >&2; }
die() {
	log "vendor-pins: $*"
	exit 1
}

fetch() {
	curl --proto '=https' --tlsv1.2 --fail --silent --show-error --location "$@"
}

latest_bitwarden() {
	fetch "$BITWARDEN_RELEASES" |
		jq -r 'first(.[] | select(.prerelease | not) | .tag_name | select(startswith("desktop-v"))) | ltrimstr("desktop-v")'
}

# The download link redirects to a versioned URL: .../linux/x64/<version>/Discord.rpm
latest_discord() {
	local url
	url=$(fetch --head --output /dev/null --write-out '%{url_effective}' "$DISCORD_LATEST")
	url=${url%/*}
	printf '%s\n' "${url##*/}"
}

latest_signal() {
	fetch "$SIGNAL_MANIFEST" | sed -n 's/^version: //p'
}

latest_proton_mail() {
	fetch "$PROTON_MAIL_RELEASES" | jq -r 'first(.Releases[] | select(.CategoryName == "Stable") | .Version)'
}

# Replaces `readonly NAME=...` in pins.sh.
set_pin() {
	local name=$1 value=$2
	grep -q "^readonly $name=" "$PINS" || die "$name is missing from pins.sh."
	sed -i "s|^readonly $name=.*|readonly $name=$value|" "$PINS"
}

# Confirms a downloaded RPM is the package and version the pin will claim.
check_rpm() {
	local rpm=$1 name=$2 version=$3 actual
	actual=$(rpm -qp --qf '%{NAME}|%{VERSION}' "$rpm")
	[[ $actual == "$name|$version" ]] || die "Downloaded RPM is $actual, expected $name|$version."
}

bump_bitwarden() {
	local version=$1 url digest
	url=${BITWARDEN_URL//$BITWARDEN_VERSION/$version}
	digest=$(fetch "https://api.github.com/repos/bitwarden/clients/releases/tags/desktop-v$version" |
		jq -r --arg name "${url##*/}" '.assets[] | select(.name == $name) | .digest | ltrimstr("sha256:")')
	[[ -n $digest ]] || die "No published digest for ${url##*/}; the asset name may have changed."
	fetch --output "$WORK/bitwarden.rpm" "$url"
	printf '%s  %s\n' "$digest" "$WORK/bitwarden.rpm" | sha256sum --check --strict --status - ||
		die 'Bitwarden checksum does not match the GitHub release digest.'
	check_rpm "$WORK/bitwarden.rpm" bitwarden "$version"
	set_pin BITWARDEN_VERSION "$version"
	set_pin BITWARDEN_SHA256 "$digest"
}

bump_discord() {
	local version=$1 url digest
	url=${DISCORD_URL//$DISCORD_VERSION/$version}
	fetch --output "$WORK/discord.rpm" "$url"
	check_rpm "$WORK/discord.rpm" discord "$version"
	digest=$(sha256sum "$WORK/discord.rpm")
	set_pin DISCORD_VERSION "$version"
	set_pin DISCORD_SHA256 "${digest%% *}"
}

bump_proton_mail() {
	local version=$1 url release digest
	url=${PROTON_MAIL_URL//$PROTON_MAIL_VERSION/$version}
	release=$(fetch "$PROTON_MAIL_RELEASES" |
		jq -c --arg version "$version" 'first(.Releases[] | select(.Version == $version) | .File[] | select(.Url | endswith(".rpm")))')
	[[ $(jq -r .Url <<<"$release") == "$url" ]] || die "Proton's RPM URL changed; update PROTON_MAIL_URL in pins.sh."
	digest=$(jq -r .Sha512CheckSum <<<"$release")
	fetch --output "$WORK/proton-mail.rpm" "$url"
	printf '%s  %s\n' "$digest" "$WORK/proton-mail.rpm" | sha512sum --check --strict --status - ||
		die "Proton Mail checksum does not match version.json."
	check_rpm "$WORK/proton-mail.rpm" proton-mail "$version"
	set_pin PROTON_MAIL_VERSION "$version"
	set_pin PROTON_MAIL_SHA512 "$digest"
}

# Downloads a Signal AppImage and checks its signature against the pinned key,
# which is itself pinned by SHA-256.
download_signal() {
	local version=$1 url status
	url=$SIGNAL_DOWNLOADS/signal-desktop_${version}_x86_64.AppImage
	fetch --output "$WORK/Signal.AppImage" "$url"
	fetch --output "$WORK/Signal.AppImage.gpg" "$url.gpg"
	fetch --output "$WORK/signal.asc" "$SIGNAL_KEY_URL"
	printf '%s  %s\n' "$SIGNAL_KEY_SHA256" "$WORK/signal.asc" | sha256sum --check --strict --status - ||
		die 'Signal signing key does not match the pinned checksum.'
	mkdir -m 0700 -- "$WORK/gnupg"
	gpg --batch --homedir "$WORK/gnupg" --output "$WORK/signal.gpg" --dearmor "$WORK/signal.asc"
	status=$(gpgv --homedir "$WORK/gnupg" --keyring "$WORK/signal.gpg" --status-fd 1 \
		"$WORK/Signal.AppImage.gpg" "$WORK/Signal.AppImage") || die 'Signal signature check failed.'
	grep -q "VALIDSIG .*$SIGNAL_FINGERPRINT" <<<"$status" || die 'Signal was not signed by the pinned key.'
}

# Signal publishes a base64 SHA-512 in latest-linux.yml; pins.sh keeps SHA-256.
bump_signal() {
	local version=$1 manifest expected actual digest
	manifest=$(fetch "$SIGNAL_MANIFEST")
	[[ $(sed -n 's/^path: //p' <<<"$manifest") == "signal-desktop_${version}_x86_64.AppImage" ]] ||
		die 'Signal latest-linux.yml no longer describes this AppImage; rerun.'
	expected=$(sed -n 's/^sha512: //p' <<<"$manifest")
	download_signal "$version"
	actual=$(openssl dgst -sha512 -binary "$WORK/Signal.AppImage" | base64 --wrap=0)
	[[ $actual == "$expected" ]] || die 'Signal checksum does not match latest-linux.yml.'
	digest=$(sha256sum "$WORK/Signal.AppImage")
	set_pin SIGNAL_VERSION "$version"
	set_pin SIGNAL_SHA256 "${digest%% *}"
}

# Prints the newer version of an app, or nothing when it is current or the
# lookup failed.
newer_version() {
	local name=$1 pinned=$2 lookup=$3 latest
	if ! latest=$("$lookup") || [[ -z $latest ]]; then
		log "$(printf '%-12s %s pinned; could not check for updates' "$name" "$pinned")"
		return 0
	fi
	if [[ $latest == "$pinned" ]]; then
		log "$(printf '%-12s %s (latest)' "$name" "$pinned")"
		return 0
	fi
	log "$(printf '%-12s %s pinned, %s available' "$name" "$pinned" "$latest")"
	printf '%s\n' "$latest"
}

check_all() {
	local outdated=0
	[[ -z $(newer_version Bitwarden "$BITWARDEN_VERSION" latest_bitwarden) ]] || outdated=1
	[[ -z $(newer_version Discord "$DISCORD_VERSION" latest_discord) ]] || outdated=1
	[[ -z $(newer_version 'Proton Mail' "$PROTON_MAIL_VERSION" latest_proton_mail) ]] || outdated=1
	[[ -z $(newer_version Signal "$SIGNAL_VERSION" latest_signal) ]] || outdated=1
	if ((outdated)); then
		log 'Run "dotfiles bump-pins" to update pins.sh.'
	fi
}

bump_all() {
	local version bumped=0
	version=$(newer_version Bitwarden "$BITWARDEN_VERSION" latest_bitwarden)
	if [[ -n $version ]]; then
		bump_bitwarden "$version"
		bumped=1
	fi
	version=$(newer_version Discord "$DISCORD_VERSION" latest_discord)
	if [[ -n $version ]]; then
		bump_discord "$version"
		bumped=1
	fi
	version=$(newer_version 'Proton Mail' "$PROTON_MAIL_VERSION" latest_proton_mail)
	if [[ -n $version ]]; then
		bump_proton_mail "$version"
		bumped=1
	fi
	version=$(newer_version Signal "$SIGNAL_VERSION" latest_signal)
	if [[ -n $version ]]; then
		bump_signal "$version"
		bumped=1
	fi
	if ((bumped)); then
		log 'Updated pins.sh. Install with "dotfiles update", then commit pins.sh.'
	fi
}

# Installs a vendor RPM after verifying its checksum and, when given, its signature.
# Keeps an installed copy that is the same version or newer.
install_pinned_rpm() {
	local name=$1 version=$2 url=$3 algorithm=$4 digest=$5 key=${6:-} fingerprint=${7:-}
	local installed newest rpm=$WORK/$name.rpm
	if installed=$(rpm -q --qf '%{VERSION}' "$name" 2>/dev/null); then
		newest=$(printf '%s\n%s\n' "$installed" "$version" | sort -V | tail -n1)
		if [[ $newest == "$installed" ]]; then
			log "Keeping $name $installed (pinned $version)"
			return 0
		fi
	fi
	log "Installing $name $version"
	fetch --output "$rpm" "$url"
	printf '%s  %s\n' "$digest" "$rpm" | "${algorithm}sum" --check --strict --status - || die "$name checksum mismatch."
	if [[ -n $key ]]; then
		# A throwaway keyring leaves the system RPM keyring untouched.
		local -a keyring=(--dbpath "$WORK/$name-db" --define "_keyringpath $WORK/$name-keys" --define '_keyring fs')
		mkdir -- "$WORK/$name-db" "$WORK/$name-keys"
		rpmkeys "${keyring[@]}" --import "$key"
		[[ -f $WORK/$name-keys/gpg-pubkey-$fingerprint.key ]] || die "$name signing key does not match the pinned fingerprint."
		rpmkeys "${keyring[@]}" --checksig "$rpm" >/dev/null || die "$name signature check failed."
	fi
	check_rpm "$rpm" "$name" "$version"
	sudo dnf install "$rpm"
}

# Signal updates itself, so the pin only matters for a fresh install.
install_signal() {
	if [[ -x $SIGNAL_DIRECTORY/Signal.AppImage ]]; then
		log 'Keeping installed Signal; it updates itself'
		return 0
	fi
	log "Installing Signal $SIGNAL_VERSION"
	download_signal "$SIGNAL_VERSION"
	printf '%s  %s\n' "$SIGNAL_SHA256" "$WORK/Signal.AppImage" | sha256sum --check --strict --status - ||
		die 'Signal checksum mismatch.'
	mkdir -p -- "$SIGNAL_DIRECTORY"
	install -m 0700 "$WORK/Signal.AppImage" "$SIGNAL_DIRECTORY/Signal.AppImage"
}

install_all() {
	install_pinned_rpm bitwarden "$BITWARDEN_VERSION" "$BITWARDEN_URL" sha256 "$BITWARDEN_SHA256"
	install_pinned_rpm discord "$DISCORD_VERSION" "$DISCORD_URL" sha256 "$DISCORD_SHA256"
	install_pinned_rpm proton-mail "$PROTON_MAIL_VERSION" "$PROTON_MAIL_URL" sha512 "$PROTON_MAIL_SHA512" \
		"$PROTON_MAIL_KEY" "$PROTON_MAIL_FINGERPRINT"
	install_signal
}

main() {
	local command=${1:-check}
	case $command in
	check)
		check_all
		return 0
		;;
	bump | install) ;;
	*)
		log 'Usage: vendor-pins.sh [check|bump|install]'
		return 2
		;;
	esac
	WORK=$(mktemp -d)
	trap 'rm -rf -- "$WORK"' EXIT
	case $command in
	bump) bump_all ;;
	install) install_all ;;
	esac
}

main "$@"
