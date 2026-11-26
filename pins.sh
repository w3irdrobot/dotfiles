# shellcheck shell=bash
# shellcheck disable=SC2034 # Used by bootstrap.sh and scripts/vendor-pins.sh.
# Pinned vendor downloads. Bump with `dotfiles bump-pins`.
# Bitwarden: SHA256 from the GitHub release asset digest (RPM is unsigned).
# oss- is the open-source build; bit- is the commercial one.
readonly BITWARDEN_VERSION=2026.11.0
readonly BITWARDEN_URL=https://github.com/bitwarden/clients/releases/download/desktop-v$BITWARDEN_VERSION/oss-Bitwarden-$BITWARDEN_VERSION-x86_64.rpm
readonly BITWARDEN_SHA256=b30e042c8e90c23eab9ed8c7fe95632f11ea99ce874131856e987d9bb740f655
# Discord: no vendor checksum or signature; SHA256 of the reviewed HTTPS download.
readonly DISCORD_VERSION=1.0.171
readonly DISCORD_URL=https://stable.dl2.discordapp.net/distro/app/stable/linux/x64/$DISCORD_VERSION/Discord.rpm
readonly DISCORD_SHA256=5d0c79c8b3ad8f84e871e8bf0ef60b4500787f6866fbfeb86c978eee425273b5
# Proton Mail: SHA512 from https://proton.me/download/mail/linux/version.json,
# signed RPM (https://proton.me/support/mail-desktop-verify-rpm-fedora).
readonly PROTON_MAIL_VERSION=1.16.1
readonly PROTON_MAIL_URL=https://proton.me/download/mail/linux/$PROTON_MAIL_VERSION/ProtonMail-desktop-beta.rpm
readonly PROTON_MAIL_SHA512=1d2ea724d71a12e9469620ce325e104be722c64394ad643d9e7d9fa81b9bdfb91b432f8e82ee499628a6f1d15ecff79e1ccdcaeb61db535b1265f02fa7943620
readonly PROTON_MAIL_FINGERPRINT=1c27df7a717bcbcac760a84c0db4b0701e5fb04a
# Signal: initial AppImage only; Signal updates itself afterwards.
readonly SIGNAL_VERSION=8.36.0
readonly SIGNAL_SHA256=76a653c8b38d8b9c7f48403c4bedbb69f99c3aa1e19062440a9996a40a7a07fc
readonly SIGNAL_KEY_SHA256=f601d18a2a9fbdf2bd11379a90952dd8a3b8ab9776aeccabc539da63461f04f2
readonly SIGNAL_FINGERPRINT=4B16B7232DFAA439AD791002EF9F501F13EED94C
