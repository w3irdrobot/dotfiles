# shellcheck shell=bash
# shellcheck disable=SC2034 # Used by bootstrap.sh and scripts/check-pins.sh.
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
