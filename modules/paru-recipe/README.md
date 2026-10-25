# Frozen paru fallback

Repository paru takes priority. Otherwise, the reviewed local `PKGBUILD` builds
[upstream commit 7830fac148f8cd2143307386ead67d7ffd2efa33](https://github.com/Morganamilo/paru/commit/7830fac148f8cd2143307386ead67d7ffd2efa33),
the upstream HEAD inspected on 2026-10-14. At that review, the latest release was
v2.1.0; the fallback uses a post-release commit with a committed libalpm-16 lock instead
of the AUR 2.1.0-2 recipe's dependency updates.

Verified by downloading the commit archive and hashing its unmodified bytes:

- Source archive SHA256: `94869ec2dac20d3d34b5aa6cb32ffa6e2f1f434e79201287729a6028266e248a`
- Committed `Cargo.lock` SHA256: `10137b6b653655e5069618f1ca9071e4c104286d2a1deb7b7ea25a3eda2ea2e7`
- Locked `alpm` 5.0.2, `alpm-utils` 5.0.0, `alpm-sys` 5.0.1.
  The latter's published build script requires libalpm >=16.0.0; its generated
  bindings target ABI 16. This recipe rejects any native ABI other than 16.

Compatibility evidence: the [committed manifest](https://github.com/Morganamilo/paru/blob/7830fac148f8cd2143307386ead67d7ffd2efa33/Cargo.toml)
and [committed lock](https://github.com/Morganamilo/paru/blob/7830fac148f8cd2143307386ead67d7ffd2efa33/Cargo.lock),
plus the published [alpm-sys 5.0.1 crate](https://static.crates.io/crates/alpm-sys/alpm-sys-5.0.1.crate).
The crate download's SHA256 was also verified against the committed lock:
`2802ef5d74e47cceda08d0d583c69be2595a5d25e2d6eef349b5e5b5ed4560e9`.
Its `build.rs` probes libalpm with `atleast_version("16.0.0")`; default features
use published bindings, not bindgen (no new Clang dependency).

Cargo fetch uses `--locked`; compilation uses `--frozen`. Each stage verifies
the original lock hash, including after failed Cargo commands. Never regenerate,
patch, or update the lock to fix a build. A future ABI requires explicitly
reviewing another upstream commit and verifying both new hashes.

Installer AUR upgrades always use `--ignore paru`, so they cannot replace this
helper with a mutable AUR build. This is not a partial native upgrade: the full
pacman transaction still upgrades repository-owned paru normally. To replace a
foreign helper, manually review a new compatible upstream commit, verify the
archive and committed-lock hashes, update this owned recipe, and rehearse its
frozen build in Arch. Then explicitly remove the old foreign paru with pacman
and rerun the installer from a terminal to review and rebuild the owned recipe.
Do not regenerate the lock or delegate the helper rebuild to AUR.

The existing nixpkgs commit `7fd4004d0511991fff3a0524856a9be09e28c5f0`
supplies rustc 1.98.1 and Cargo 1.98.0 only for this build. Both Nix derivations
are named/versioned 1.98.1, but the bundled Cargo executable reports 1.98.0;
these executable versions were verified in the Arch VM, including with only
native `/usr/bin` on PATH. The recipe checks each executable version separately.
Native `base-devel`, `git`, `pacman`, and `openssl` must already satisfy makepkg's
normal dependency checks. The build uses no global Rust/Cargo packages,
`--nodeps`, or automatic dependency installs.
The recipe enforces native compiler/linker flags inside `build()`, after makepkg
configuration/drop-ins have loaded, and clears encoded Cargo flags there too.
The launcher isolates makepkg's package, source, source-package, log, and build
destinations in its fresh scratch directory, and uses `--force --install` so
a matching package in a configured global cache cannot skip the verified build.
The compiler/linker and pkg-config search use native `/usr` paths; the recipe
rejects ELF Nix-store runtime references before makepkg installs the package.
The [Arch rehearsal](../../docs/testing.md#recorded-results) verified the frozen
build and native runtime linkage with `ldd`. New source, lock, or toolchain pins
need another VM build; fixture tests alone cannot establish that compatibility.
