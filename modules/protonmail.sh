#!/usr/bin/env bash
set -euo pipefail

if [[ "${DEBUG:-0}" == "1" ]]; then
	set -x
fi

ROOT=$(cd -- "$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")/.." && pwd -P)
readonly ROOT
# shellcheck source=lib/dotfiles.sh
source "$ROOT/lib/dotfiles.sh"

# To update, copy the RPM version and SHA512 from
# https://proton.me/download/mail/linux/version.json
# Proton signs its RPMs (1.16.0+); see https://proton.me/support/mail-desktop-verify-rpm-fedora
readonly PROTON_MAIL_VERSION=1.16.1
readonly PROTON_MAIL_URL=https://proton.me/download/mail/linux/$PROTON_MAIL_VERSION/ProtonMail-desktop-beta.rpm
readonly PROTON_MAIL_SHA512=1d2ea724d71a12e9469620ce325e104be722c64394ad643d9e7d9fa81b9bdfb91b432f8e82ee499628a6f1d15ecff79e1ccdcaeb61db535b1265f02fa7943620
readonly PROTON_MAIL_KEY=$ROOT/repos/RPM-GPG-KEY-proton-mail
readonly PROTON_MAIL_FINGERPRINT=1c27df7a717bcbcac760a84c0db4b0701e5fb04a

main() {
	(($# == 0)) || die 'This setup module takes no arguments.'
	check_platform
	local installed newest temp rpm
	if installed=$(rpm -q --qf '%{VERSION}' proton-mail 2>/dev/null); then
		newest=$(printf '%s\n%s\n' "$installed" "$PROTON_MAIL_VERSION" | sort -V | tail -n1)
		if [[ $newest == "$installed" ]]; then
			log "Keeping installed Proton Mail $installed (pinned $PROTON_MAIL_VERSION)."
			return 0
		fi
	fi
	temp=$(mktemp -d)
	trap 'rm -rf -- "$temp"' EXIT
	rpm=$temp/proton-mail.rpm
	curl --proto '=https' --tlsv1.2 --fail --silent --show-error --location --output "$rpm" "$PROTON_MAIL_URL"
	printf '%s  %s\n' "$PROTON_MAIL_SHA512" "$rpm" | sha512sum --check --strict --status - || die 'Proton Mail RPM checksum mismatch.'
	# Check against a throwaway keyring so the system RPM keyring is untouched.
	local -a keyring=(--dbpath "$temp/db" --define "_keyringpath $temp/keys" --define '_keyring fs')
	mkdir -- "$temp/db" "$temp/keys"
	rpmkeys "${keyring[@]}" --import "$PROTON_MAIL_KEY"
	[[ -f $temp/keys/gpg-pubkey-$PROTON_MAIL_FINGERPRINT.key ]] || die 'Proton Mail signing key does not match the pinned fingerprint.'
	rpmkeys "${keyring[@]}" --checksig "$rpm" >/dev/null || die 'Proton Mail RPM signature check failed.'
	[[ $(rpm -qp --qf '%{NAME}|%{VERSION}|%{ARCH}' "$rpm") == "proton-mail|$PROTON_MAIL_VERSION|x86_64" ]] || die 'Proton Mail RPM identity does not match the pin.'
	sudo dnf install "$rpm"
}

main "$@"
