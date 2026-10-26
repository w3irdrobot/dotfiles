# shellcheck shell=bash
# Initial signed AppImage installation. Signal owns in-place application updates.
preflight_signal() {
	local pin parent
	pin=$(python3 "$ROOT/scripts/check-updates.py" --print-signal-pin) || die 'Could not validate initial Signal AppImage pin.'
	IFS='|' read -r SIGNAL_VERSION SIGNAL_SHA256 SIGNAL_KEY_SHA256 SIGNAL_FINGERPRINT <<<"$pin"
	SIGNAL_DIRECTORY=$HOME/.local/share/dotfiles/signal
	SIGNAL_CACHE=${XDG_CACHE_HOME:-$HOME/.cache}/dotfiles/signal/$SIGNAL_VERSION
	[[ $SIGNAL_CACHE == /* ]] || die 'Signal cache directory must be absolute.'
	for parent in "$SIGNAL_DIRECTORY" "$SIGNAL_CACHE"; do
		while [[ $parent != "$HOME" && $parent != / ]]; do
			[[ ! -L $parent && (! -e $parent || -d $parent) ]] || die "Conflicting Signal parent: $parent"
			parent=${parent%/*}
			[[ -n $parent ]] || parent=/
		done
	done
	SIGNAL_INSTALLED=0
	if [[ -e $SIGNAL_DIRECTORY ]]; then
		[[ -f $SIGNAL_DIRECTORY/managed && ! -L $SIGNAL_DIRECTORY/managed ]] || die 'Unmanaged/partial Signal directory; inspect it manually.'
		[[ $(<"$SIGNAL_DIRECTORY/managed") == dotfiles-signal-appimage-v1 ]] || die 'Unrecognized Signal installation marker.'
		[[ -f $SIGNAL_DIRECTORY/Signal.AppImage && ! -L $SIGNAL_DIRECTORY/Signal.AppImage && -x $SIGNAL_DIRECTORY/Signal.AppImage ]] || die 'Managed Signal AppImage is missing, symlinked, or not executable; repair manually.'
		SIGNAL_INSTALLED=1
	fi
	local executable
	executable=$(command -v signal-desktop) || executable=''
	if [[ -n $executable ]]; then
		[[ -L $executable && $(realpath -- "$executable") == "$ROOT/stow/signal/.local/bin/signal-desktop" ]] || die 'Conflicting Signal executable on PATH; resolve native/Flatpak installations manually.'
	fi
}

verify_signal_download() (
	local directory=$1 temp status
	local tool
	for tool in sha256sum gpg gpgv; do
		command -v "$tool" >/dev/null || die "Signal verification requires $tool before package transactions; install the Fedora workstation prerequisites first."
	done
	printf '%s  %s\n' "$SIGNAL_SHA256" "$directory/Signal.AppImage" "$SIGNAL_KEY_SHA256" "$directory/key.asc" | sha256sum --check --strict --status - || die 'Signal AppImage/key checksum mismatch.'
	temp=$(mktemp -d)
	trap 'rm -rf -- "$temp"' EXIT
	# Public-key conversion and gpgv use an isolated keyring, never ~/.gnupg.
	gpg --no-options --batch --homedir "$temp" --output "$temp/keyring.gpg" --dearmor "$directory/key.asc"
	status=$(gpgv --homedir "$temp" --keyring "$temp/keyring.gpg" --status-fd 1 "$directory/Signal.AppImage.gpg" "$directory/Signal.AppImage") || die 'Signal AppImage signature verification failed.'
	grep -Eq "^\[GNUPG:\] VALIDSIG ($SIGNAL_FINGERPRINT .*|.* $SIGNAL_FINGERPRINT)$" <<<"$status" || die 'Signal signature did not match the pinned signing identity.'
)

prepare_signal_appimage() (
	preflight_signal
	if ((SIGNAL_INSTALLED)); then
		log 'Keeping managed Signal AppImage; Signal owns its updates. No replacement or downgrade.'
		return 0
	fi
	if ((DRY_RUN)); then
		log "Would download/check initial Signal $SIGNAL_VERSION AppImage hash and vendor signature before package transactions."
		return 0
	fi
	local temp file
	if [[ -d $SIGNAL_CACHE ]]; then
		for file in Signal.AppImage Signal.AppImage.gpg key.asc; do
			[[ -f $SIGNAL_CACHE/$file && ! -L $SIGNAL_CACHE/$file ]] || die 'Partial/conflicting Signal download cache; inspect it manually.'
		done
		verify_signal_download "$SIGNAL_CACHE"
		return 0
	fi
	umask 077
	mkdir -p -- "${SIGNAL_CACHE%/*}"
	temp=$(mktemp -d "${SIGNAL_CACHE%/*}/.download.XXXXXXXX")
	trap 'rm -rf -- "$temp"' EXIT
	local url=https://updates.signal.org/desktop/signal-desktop_${SIGNAL_VERSION}_x86_64.AppImage
	curl --proto '=https' --proto-redir '=https' --tlsv1.2 -fsSL --output "$temp/Signal.AppImage" "$url"
	curl --proto '=https' --proto-redir '=https' --tlsv1.2 -fsSL --output "$temp/Signal.AppImage.gpg" "$url.gpg"
	curl --proto '=https' --proto-redir '=https' --tlsv1.2 -fsSL --output "$temp/key.asc" https://updates.signal.org/static/desktop/appimage.asc
	verify_signal_download "$temp"
	# mkdir refuses an intervening cache conflict; hard links never overwrite.
	mkdir -- "$SIGNAL_CACHE"
	for file in Signal.AppImage Signal.AppImage.gpg key.asc; do ln -- "$temp/$file" "$SIGNAL_CACHE/$file"; done
)

install_signal_appimage() (
	preflight_signal
	if ((SIGNAL_INSTALLED)); then return 0; fi
	if ((DRY_RUN)); then
		log 'Would publish the verified Signal AppImage and its managed launcher; never launch it during setup.'
		return 0
	fi
	verify_signal_download "$SIGNAL_CACHE"
	local temp
	umask 077
	mkdir -p -- "${SIGNAL_DIRECTORY%/*}"
	temp=$(mktemp -d "${SIGNAL_DIRECTORY%/*}/.signal.XXXXXXXX")
	trap 'rm -rf -- "$temp"' EXIT
	cp -- "$SIGNAL_CACHE/Signal.AppImage" "$temp/Signal.AppImage"
	chmod 0700 "$temp/Signal.AppImage"
	printf '%s\n' dotfiles-signal-appimage-v1 >"$temp/managed"
	# A new conflict is not overwritten or adopted.
	mkdir -- "$SIGNAL_DIRECTORY"
	ln -- "$temp/Signal.AppImage" "$SIGNAL_DIRECTORY/Signal.AppImage"
	ln -- "$temp/managed" "$SIGNAL_DIRECTORY/managed"
	log 'Initial signed Signal AppImage installed. Signal owns subsequent updates; login/Secret Service setup remain manual.'
)
