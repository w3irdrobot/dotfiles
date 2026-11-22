#!/usr/bin/env bash
# Reports pinned vendor apps that have a newer release. Changes nothing.
# shellcheck source-path=SCRIPTDIR
set -euo pipefail

if [[ "${DEBUG:-0}" == "1" ]]; then
	set -x
fi

ROOT=$(cd -- "$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")/.." && pwd -P)
readonly ROOT
# shellcheck source=../pins.sh
source "$ROOT/pins.sh"

readonly BITWARDEN_RELEASES='https://api.github.com/repos/bitwarden/clients/releases?per_page=50'
readonly DISCORD_LATEST='https://discord.com/api/download/stable?platform=linux&format=rpm'
readonly PROTON_MAIL_RELEASES=https://proton.me/download/mail/linux/version.json

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

report() {
	local name=$1 pinned=$2 latest
	if ! latest=$("$3") || [[ -z $latest ]]; then
		printf '%-12s %s pinned; could not check for updates\n' "$name" "$pinned" >&2
		return 0
	fi
	if [[ $latest == "$pinned" ]]; then
		printf '%-12s %s (latest)\n' "$name" "$pinned"
	else
		printf '%-12s %s pinned, %s available: bump pins.sh\n' "$name" "$pinned" "$latest"
	fi
}

main() {
	report Bitwarden "$BITWARDEN_VERSION" latest_bitwarden
	report Discord "$DISCORD_VERSION" latest_discord
	report 'Proton Mail' "$PROTON_MAIL_VERSION" latest_proton_mail
}

main "$@"
