#!/usr/bin/env bash
# Checks or bumps the pinned vendor apps in pins.sh.
#   check  Report newer releases. Changes nothing.
#   bump   Download each newer release, verify the vendor checksum (Discord
#          publishes none, so its hash is taken from the HTTPS download), and
#          rewrite pins.sh. Bootstrap checks signatures again at install.
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
	local version=$1 work=$2 url digest
	url=${BITWARDEN_URL//$BITWARDEN_VERSION/$version}
	digest=$(fetch "https://api.github.com/repos/bitwarden/clients/releases/tags/desktop-v$version" |
		jq -r --arg name "${url##*/}" '.assets[] | select(.name == $name) | .digest | ltrimstr("sha256:")')
	[[ -n $digest ]] || die "No published digest for ${url##*/}; the asset name may have changed."
	fetch --output "$work/bitwarden.rpm" "$url"
	printf '%s  %s\n' "$digest" "$work/bitwarden.rpm" | sha256sum --check --strict --status - ||
		die 'Bitwarden checksum does not match the GitHub release digest.'
	check_rpm "$work/bitwarden.rpm" bitwarden "$version"
	set_pin BITWARDEN_VERSION "$version"
	set_pin BITWARDEN_SHA256 "$digest"
}

bump_discord() {
	local version=$1 work=$2 url digest
	url=${DISCORD_URL//$DISCORD_VERSION/$version}
	fetch --output "$work/discord.rpm" "$url"
	check_rpm "$work/discord.rpm" discord "$version"
	digest=$(sha256sum "$work/discord.rpm")
	set_pin DISCORD_VERSION "$version"
	set_pin DISCORD_SHA256 "${digest%% *}"
}

bump_proton_mail() {
	local version=$1 work=$2 url release digest
	url=${PROTON_MAIL_URL//$PROTON_MAIL_VERSION/$version}
	release=$(fetch "$PROTON_MAIL_RELEASES" |
		jq -c --arg version "$version" 'first(.Releases[] | select(.Version == $version) | .File[] | select(.Url | endswith(".rpm")))')
	[[ $(jq -r .Url <<<"$release") == "$url" ]] || die "Proton's RPM URL changed; update PROTON_MAIL_URL in pins.sh."
	digest=$(jq -r .Sha512CheckSum <<<"$release")
	fetch --output "$work/proton-mail.rpm" "$url"
	printf '%s  %s\n' "$digest" "$work/proton-mail.rpm" | sha512sum --check --strict --status - ||
		die "Proton Mail checksum does not match version.json."
	check_rpm "$work/proton-mail.rpm" proton-mail "$version"
	set_pin PROTON_MAIL_VERSION "$version"
	set_pin PROTON_MAIL_SHA512 "$digest"
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

check() {
	local outdated=0
	[[ -z $(newer_version Bitwarden "$BITWARDEN_VERSION" latest_bitwarden) ]] || outdated=1
	[[ -z $(newer_version Discord "$DISCORD_VERSION" latest_discord) ]] || outdated=1
	[[ -z $(newer_version 'Proton Mail' "$PROTON_MAIL_VERSION" latest_proton_mail) ]] || outdated=1
	if ((outdated)); then
		log 'Run "dotfiles bump-pins" to update pins.sh.'
	fi
}

bump() {
	local version bumped=0
	WORK=$(mktemp -d)
	trap 'rm -rf -- "$WORK"' EXIT
	version=$(newer_version Bitwarden "$BITWARDEN_VERSION" latest_bitwarden)
	if [[ -n $version ]]; then
		bump_bitwarden "$version" "$WORK"
		bumped=1
	fi
	version=$(newer_version Discord "$DISCORD_VERSION" latest_discord)
	if [[ -n $version ]]; then
		bump_discord "$version" "$WORK"
		bumped=1
	fi
	version=$(newer_version 'Proton Mail' "$PROTON_MAIL_VERSION" latest_proton_mail)
	if [[ -n $version ]]; then
		bump_proton_mail "$version" "$WORK"
		bumped=1
	fi
	if ((bumped)); then
		log 'Updated pins.sh. Install with "dotfiles bootstrap", then commit pins.sh.'
	fi
}

main() {
	case "${1:-check}" in
	check) check ;;
	bump) bump ;;
	*)
		log 'Usage: vendor-pins.sh [check|bump]'
		return 2
		;;
	esac
}

main "$@"
