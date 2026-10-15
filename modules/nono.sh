#!/usr/bin/env bash
set -euo pipefail
if [[ "${DEBUG:-0}" == "1" ]]; then set -x; fi

ROOT=$(cd -- "$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")/.." && pwd -P)
readonly ROOT
# shellcheck source=lib/dotfiles.sh
source "$ROOT/lib/dotfiles.sh"

check_destination() {
	local target=$1 parent
	parent=$(dirname "$target")
	while [[ $parent != "$HOME" && $parent != / ]]; do
		[[ ! -L $parent && (! -e $parent || -d $parent) ]] || die "Conflicting parent: $parent"
		parent=$(dirname "$parent")
	done
}

preflight_nono() {
	NONO_TARGET=$HOME/.local/share/dotfiles/nono/0.80.0/nono
	NONO_LINK=$HOME/.local/bin/nono
	local target=$NONO_TARGET link=$NONO_LINK expected actual
	check_destination "$target"
	check_destination "$link"
	if [[ -L $link ]]; then
		expected=$(realpath -m "$target")
		actual=$(realpath -m "$link")
		[[ $actual == "$expected" && -e $link ]] || die "Conflicting or dangling nono link: $link"
	elif [[ -e $link ]]; then
		die "Unmanaged nono binary: $link; inspect and move it yourself first."
	fi
	[[ ! -L $target && (! -e $target || -f $target) ]] || die "Conflicting nono binary destination: $target"
	check_nono_pack
}

# v0.80.0 package_cmd.rs returns early for equal versions without integrity
# checks, and removes final_root on install. Never ask pull to adopt local state.
# These immutable 0.4.0 digests are from the production registry pull metadata.
# Nono itself verifies Sigstore/Rekor and namespace assertions on first pull.
# Source: https://github.com/nolabs-ai/nono/blob/v0.80.0/crates/nono-cli/src/package_cmd.rs
# Metadata: https://registry.nono.sh/api/v1/packages/nolabs-ai/opencode/versions/0.4.0/pull
check_nono_pack() {
	local config=${XDG_CONFIG_HOME:-$HOME/.config} path occupied=0
	NONO_PACK_PINNED=0
	[[ $config == /* ]] || die 'XDG_CONFIG_HOME must be absolute for nono setup.'
	for path in "$config/nono/packages/nolabs-ai/opencode" "$config/nono/packages/lockfile.json" "$config/nono/packages/lockfile.json.tmp" "$config/nono/packages/.staging/nolabs-ai" "$config/nono/profile-drafts/.nono-opencode-pack-marker" "$config/nono/profile-drafts/.nono-opencode-pack-marker.nono-tmp" "$config/opencode/plugins/nono-sandbox.ts" "$config/opencode/skills/nono-sandbox"; do
		check_destination "$path"
		if [[ -e $path || -L $path ]]; then occupied=1; fi
	done
	path=$config/nono/packages/.staging/nolabs-ai
	[[ ! -L $path && (! -e $path || -d $path) ]] || die "Conflicting nono staging directory: $path"
	path=$config/nono/profile-drafts/.nono-opencode-pack-marker.nono-tmp
	[[ ! -e $path && ! -L $path ]] || die "Conflicting nono marker temporary path: $path"
	# Fresh hosts can preflight before the package transaction provides Python.
	((occupied)) || return 0
	command -v python3 >/dev/null || die 'Python is required to inspect existing nono pack state; install the native python package first.'
	NONO_PACK_PINNED=$(
		python3 - "$config" <<'PY'
import hashlib
import json
from pathlib import Path
import sys

config = Path(sys.argv[1])
store = config / 'nono/packages'
root = store / 'nolabs-ai/opencode'
lock = store / 'lockfile.json'
registry = 'https://registry.nono.sh'
hashes = {
    'profiles/opencode.json': 'bbcb549e57df8c86c261018071943c1da239ce0be036a83132af8a24b82fc40b',
    'README.md': '82d3a1966458d1f18f7e60fd3a83dcf6b75aa7d8c9dc638cbce9227653083f39',
    'plugin/nono-sandbox.ts': '710a41a06a8c92d781724583abd6ca557300408058c8043e07977843cff79b91',
    'bin/ensure-dirs.sh': '1bb7d5a89fe98b2113da9fd8e1ee865cf21c098be9bf6e621d38b699369d4441',
    'assets/logo.png': '133ebc3baa697b38bfb4e64a2aa463b067cfc40ec9f03ca593a1564080c644f2',
    'skills/nono-sandbox/SKILL.md': '3711f3b5f7efa0773cb1ef4679e6cbec850a5300a5f4713d93e9a179244f22a5',
    'wiring/profile-drafts-dir-marker': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
}
manifest_hash = 'b7896fef6756c558379b314e95158a0cd15b28eb0ca0e4fe8099e26e618b14f5'
# Canonical JSON digest of the production 0.4.0 Sigstore bundle. This also
# protects the supporting trust metadata that is not covered by lock hashes.
bundle_hash = 'a9369d8e7bb75e134b924767f1d6e6c4fc95a02596b82d40f78e8095ed730f72'

def require(ok, message):
    if not ok:
        raise ValueError(message + '; inspect and resolve manually (nothing replaced)')

def occupied(path):
    return path.exists() or path.is_symlink()

def regular(path):
    # Reject interior symlinks too, including dangling ones.
    require(not path.is_symlink() and path.is_file(), f'Conflicting or missing nono pack file: {path}')
    parent = path.parent
    while parent != config:
        require(not parent.is_symlink() and parent.is_dir(), f'Conflicting nono pack parent: {parent}')
        parent = parent.parent

try:
    require(not occupied(store / 'lockfile.json.tmp'), 'Conflicting nono lockfile temporary path')
    if occupied(lock):
        regular(lock)
        data = json.loads(lock.read_text())
        require(data.get('lockfile_version') == 4, 'Unsupported nono lockfile schema')
        require(data.get('registry') == registry, 'Existing nono registry origin differs from the official registry')
        packages = data['packages']
        require(isinstance(packages, dict), 'Invalid nono packages metadata')
    else:
        packages = {}
    package = packages.get('nolabs-ai/opencode')
    if package is None:
        require(not occupied(root), f'Unmanaged nono pack directory: {root}')
    else:
        require(package['version'] == '0.4.0', 'Existing nono OpenCode pack is not pinned version 0.4.0')
        provenance = package.get('provenance') or {}
        for key, expected in {
            'signer_identity': 'https://github.com/nolabs-ai/nono-packs/.github/workflows/publish-opencode.yml@refs/tags/opencode-v0.4.0',
            'repository': 'nolabs-ai/nono-packs',
            'workflow': '.github/workflows/publish-opencode.yml',
            'ref': 'refs/tags/opencode-v0.4.0',
        }.items():
            require(provenance.get(key) == expected, 'Unexpected nono pack signing provenance')
        require(set(package['artifacts']) == set(hashes), 'Unexpected nono pack artifact metadata')
        for relative, digest in {**hashes, 'package.json': manifest_hash}.items():
            path = root / relative
            regular(path)
            require(hashlib.sha256(path.read_bytes()).hexdigest() == digest, f'Edited nono pack file: {path}')
            if relative in hashes:
                require(package['artifacts'][relative]['sha256'] == digest, 'Unexpected nono pack digest metadata')
                expected_type = 'profile' if relative.startswith('profiles/') else 'plugin'
                require(package['artifacts'][relative]['type'] == expected_type, 'Unexpected nono pack artifact type')
        for path in root.rglob('*'):
            require(not path.is_symlink(), f'Conflicting nono pack symlink: {path}')
            if not path.is_dir():
                require(str(path.relative_to(root)) in {*hashes, 'package.json', '.nono-trust.bundle'}, f'Unmanaged nono pack file: {path}')
        trust = root / '.nono-trust.bundle'
        regular(trust)
        bundles = json.loads(trust.read_text())
        expected = {**hashes, 'package.json': manifest_hash}
        require(isinstance(bundles, list) and len(bundles) == len(expected), 'Edited nono trust metadata')
        seen = set()
        for entry in bundles:
            relative = entry['installed_path']
            require(relative in expected and relative not in seen and entry['digest'] == expected[relative], 'Edited nono trust artifact metadata')
            seen.add(relative)
            digest = hashlib.sha256(json.dumps(entry['bundle'], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            require(digest == bundle_hash, 'Edited nono signing bundle')
    marker = config / 'nono/profile-drafts/.nono-opencode-pack-marker'
    links = {
        config / 'opencode/plugins/nono-sandbox.ts': root / 'plugin/nono-sandbox.ts',
        config / 'opencode/skills/nono-sandbox': root / 'skills/nono-sandbox',
    }
    if package is None:
        for path in [marker, *links]:
            require(not occupied(path), f'Conflicting nono pack wiring destination: {path}')
    else:
        records = [{'type': 'write_file', 'dest': str(marker), 'sha256': hashes['wiring/profile-drafts-dir-marker']}]
        records.extend({'type': 'symlink', 'link': str(path)} for path in links)
        require(package.get('wiring_record') == records, 'Edited nono pack wiring metadata')
        regular(marker)
        require(marker.read_bytes() == b'', 'Edited nono pack marker')
        for path, target in links.items():
            require(path.is_symlink() and path.readlink() == target and path.exists(), f'Conflicting or missing nono pack wiring: {path}')
    print(int(package is not None and package.get('pinned') is True))
except (ValueError, KeyError, TypeError, AttributeError, OSError) as error:
    print(f'dotfiles: {error}', file=sys.stderr)
    sys.exit(1)
PY
	) || return $?
}

install_nono_pack() {
	check_nono_pack || return $?
	log 'Preparing signed OpenCode pack nolabs-ai/opencode@0.4.0 from the official nono registry.'
	# Explicit --registry takes precedence over NONO_REGISTRY in v0.80.0.
	# Same-version pull is deliberately skipped: it does not verify local files.
	if [[ -d ${XDG_CONFIG_HOME:-$HOME/.config}/nono/packages/nolabs-ai/opencode ]]; then
		log 'OpenCode pack 0.4.0 is already installed; original provenance and file integrity checked.'
	else
		# Nono canonicalizes XDG_CONFIG_HOME and otherwise falls back to ~/.config.
		mkdir -p "${XDG_CONFIG_HOME:-$HOME/.config}" || return $?
		"$NONO_TARGET" pull nolabs-ai/opencode@0.4.0 --registry https://registry.nono.sh || return $?
		check_nono_pack || return $?
		[[ -d ${XDG_CONFIG_HOME:-$HOME/.config}/nono/packages/nolabs-ai/opencode ]] || die 'Nono pull did not install the pinned OpenCode pack.'
	fi
	# v0.80.0 pull @version does not persist a pin; pin only after validation.
	if [[ $NONO_PACK_PINNED != 1 ]]; then
		"$NONO_TARGET" pin nolabs-ai/opencode || return $?
		check_nono_pack || return $?
		[[ $NONO_PACK_PINNED == 1 ]] || die 'Nono did not persist the OpenCode pack pin.'
	fi
}

install_nono() (
	local scratch archive binary target=$NONO_TARGET link=$NONO_LINK
	scratch=$(mktemp -d)
	trap 'rm -rf -- "$scratch"' EXIT
	archive=$scratch/nono.tar.gz
	wget --https-only --output-document="$archive" \
		https://github.com/nolabs-ai/nono/releases/download/v0.80.0/nono-v0.80.0-x86_64-unknown-linux-gnu.tar.gz
	# Immutable release asset digest published by GitHub's release API.
	printf '%s  %s\n' 6da665b61999570c10dffc7da78828fe1fb7f3cac53319e505cebecaef17037f "$archive" | sha256sum --check --strict -
	# Extract only the expected member, never arbitrary archive paths.
	binary=$scratch/nono
	tar --extract --gzip --to-stdout --file="$archive" nono >"$binary"
	[[ -s $binary ]] || die 'Verified nono archive contained no executable.'
	if [[ -e $target ]]; then
		cmp --silent "$binary" "$target" || die "Existing nono binary differs from the pinned release: $target"
		[[ -x $target ]] || die "Existing managed nono binary is not executable: $target; repair its executable permissions before continuing."
	else
		mkdir -p "$(dirname "$target")"
		install -m 0755 "$binary" "$target"
	fi
	if [[ ! -L $link ]]; then
		mkdir -p "$(dirname "$link")"
		ln -s "$target" "$link"
	fi
)

main() {
	DRY_RUN=0
	[[ $# == 0 || ($# == 1 && $1 == --check) ]] || die 'Usage: nono.sh [--check]'
	check_platform
	preflight_nono
	[[ ${1:-} != --check ]] || return 0
	install_nono
	install_nono_pack || die 'OpenCode pack setup failed; stopping before configuration links. Resolve the reported conflict manually; no force replacement was requested.'
	log 'nono and its pinned OpenCode pack are ready. Sign in only to services you use; authentication is manual.'
	log 'Existing nono profiles/packages are never overwritten by dotfiles setup.'
}
main "$@"
