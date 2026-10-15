# shellcheck shell=bash
# Sourced by lib/dotfiles.sh; entrypoints own shell options.
approve_paru_recipe() {
	[[ -t 0 || -t 1 || -t 2 ]] || die 'Review paru PKGBUILD interactively; then rerun from a terminal.'
	cat "$1" >/dev/tty || die 'Could not display the pinned paru recipe on the controlling terminal.'
	local answer
	read -r -p 'Build this pinned local paru PKGBUILD with its unchanged upstream lock? [y/N] ' answer </dev/tty || die 'A controlling terminal is required for PKGBUILD approval.'
	[[ $answer == y || $answer == Y ]] || die 'paru build cancelled.'
}

validate_paru_build_dependencies() {
	local dependency version
	for dependency in base-devel git pacman openssl 'libalpm.so=16-64'; do
		pacman -T "$dependency" || die "Missing pinned paru dependency: $dependency"
	done
	# Do not accept a different ABI, even if pacman's virtual provider is stale.
	version=$(PKG_CONFIG_PATH='' PKG_CONFIG_LIBDIR=/usr/lib/pkgconfig:/usr/share/pkgconfig /usr/bin/pkg-config --modversion libalpm) || die 'Could not inspect native libalpm.'
	[[ $version == 16.* ]] || die "Pinned paru supports libalpm 16 only; found $version. Review a new upstream commit, never update Cargo.lock."
}

ensure_paru() {
	if command -v paru >/dev/null; then
		validate_existing_paru
		log 'Using the existing paru helper.'
		return 0
	fi
	if ((DRY_RUN)); then
		log 'Would prefer native repository paru; otherwise review modules/paru-recipe/PKGBUILD and build its pinned source with cargo fetch --locked, then cargo build --frozen. No dependency updates.'
		return 0
	fi
	if pacman -Si -- paru >/dev/null 2>&1; then die 'Repository paru was selected for the full upgrade but is not runnable; repair the helper before continuing.'; fi
	((EUID != 0)) || die 'Build paru as your regular user, not root.'
	(
		local scratch
		scratch=$(mktemp -d "${TMPDIR:-/tmp}/dotfiles-paru.XXXXXXXX") || die 'Could not create paru build directory.'
		trap 'rm -rf -- "$scratch"' EXIT
		cp -- "$ROOT/modules/paru-recipe/PKGBUILD" "$scratch/PKGBUILD" || die 'Could not copy the pinned paru recipe.'
		approve_paru_recipe "$scratch/PKGBUILD"
		validate_paru_build_dependencies
		preflight_nix
		setup_nix --bootstrap
		cd "$scratch" || exit 1
		# Only Rust/Cargo come from Nix. Native makepkg retains dependency checks
		# and package ownership; no --nodeps, dependency installation, or profile.
		# shellcheck disable=SC2016 # Expand in the isolated Nix child, not this shell.
		/usr/bin/nix --extra-experimental-features 'nix-command flakes' \
			shell 'github:NixOS/nixpkgs/7fd4004d0511991fff3a0524856a9be09e28c5f0#rustc' \
			'github:NixOS/nixpkgs/7fd4004d0511991fff3a0524856a9be09e28c5f0#cargo' \
			--command /usr/bin/bash --noprofile --norc -c '
				export PARU_CARGO="$(command -v cargo)" RUSTC="$(command -v rustc)"
				export PATH=/usr/bin:/bin CARGO_HOME="$PWD/cargo-home"
				# makepkg restores these environment paths after loading its config.
				# Isolate both source/build trees and every output from global caches.
				export PKGDEST="$PWD" SRCDEST="$PWD" SRCPKGDEST="$PWD" LOGDEST="$PWD" BUILDDIR="$PWD"
				exec /usr/bin/makepkg --force --install
			' || die 'Pinned paru build/install failed; Cargo.lock must not be updated to work around failure.'
	)
}
