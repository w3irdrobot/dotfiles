# Installer rehearsal

Fixture tests and shell lint do not prove that a new workstation can install.
They exercise argument handling, conflict safety, repeated runs, and failure paths
without changing the developer's machine. Real package resolution, AUR builds,
the Nix daemon, and desktop integration require Linux validation.

## Disposable Linux VM

[Lima](https://lima-vm.io/docs/) supports an Arch Linux template. On an ARM Mac,
use an x86_64 QEMU guest for the initial x86_64-only installer, not Arch Linux ARM.
Foreign-architecture emulation is slow. Install Lima, QEMU, and additional guest
agents separately; the dotfiles installer must never install them on macOS.

The checked-in Lima 2.2.1 configuration pins the Arch image and its checksum,
uses QEMU x86_64 emulation, 6 GiB RAM, and a 40 GiB virtual disk. It disables host
mounts, personal public-key loading, agent forwarding, and containerd. Its guest
SSH connection uses localhost port 60022. Use a dedicated state directory:

```bash
export LIMA_HOME="$HOME/.lima-dotfiles-test"
# Create once; do not overwrite an existing instance.
limactl create --name=dotfiles-arch --yes tests/vm/arch-x86_64.yaml
limactl start --yes --timeout=30m dotfiles-arch
limactl shell dotfiles-arch
```

Tart cannot substitute for this x86_64 rehearsal on an ARM Mac: its guest
architecture must match the host. Rosetta translates applications inside ARM
guests, not an x86_64 kernel. See [Tart's architecture check](https://github.com/openai/tart/blob/main/Sources/tart/VM.swift).

Plain mode disables shared host mounts, dynamic port forwarding, and containerd.
Explicit static port forwards can remain; this configuration adds none beyond
the guest SSH transport. Clone the migration branch inside the guest; never use a writable host home mount as
the install target. Confirm the guest has a normal non-root user, sudo access,
networking, systemd, and sufficient disk space before installing. An Arch guest
tests Arch provisioning; it does **not** validate Manjaro package availability or
XFCE integration. Use a disposable Manjaro XFCE x86_64 VM or the eventual target
machine for that final rehearsal.

## Acceptance checklist

1. Read the bootstrap and module plan; confirm the checkout branch/commit.
2. Run the dry-run as a normal user. No files, network requests, or privileged
   commands should be triggered by a local dry-run.
3. Test an existing `.bashrc`, a dangling config symlink, and a conflicting parent
   path. Each must stop safely, leaving the original path untouched.
4. Resolve conflicts manually after backing up files. Run the core installation,
   then run it again. Verify repository-first package ownership and links remain
   correct; Bitwarden, OpenCode V2, and Nix must be native packages.
5. Open a fresh login shell. Verify Nix daemon access, `nix --version`, and flakes
   support; exercise a project's locked dev shell without global Rust/Node tools.
6. Install the default AI/desktop groups. Verify Ghostty, VSCodium, clipboard
   behavior under XFCE/X11, Bitwarden's SSH agent, and OpenCode/nono integration.
7. Interrupt a package install, then rerun. Confirm a partial checkout or Nix
   installation is diagnosed rather than overwritten or falsely marked complete.
   Test an existing upstream Nix install: the installer must not mix installation
   methods. Check that a repository OpenCode V1/V3 blocks upgrades before package
   installation rather than holding just OpenCode during a partial system upgrade.
8. Test config updates with clean, dirty, and diverged Git histories. Test adding
   a new config whose destination already exists. Updates must fail safely.
9. Run explicit system updates and verify no partial Arch repository upgrade.
10. Verify no changes to XFCE settings, autologin, networking, Docker-group
    membership, wallets, private keys, or local environment credentials.

Keep the VM until review is complete. Do not automatically destroy it or treat a
passing container test as equivalent to this rehearsal.

## Observed Arch rehearsal (2026-10-14–15)

Current verified scope: core plus the explicit native-module subset
`opencode,nono,bitwarden,discord,mullvad,signal,telegram,thunderbird,wallpaper`.
Installation, core repeat installation, link/config/system/update-all commands,
locked Nix development, local OpenCode API startup, and reboot persistence passed.
This is not acceptance of the complete default set: Spotify and Brave remain
pending, Claude Code is opt-in, and Manjaro/XFCE GUI checks and personal sign-ins
remain manual. The progress below is chronological; later results supersede the
earlier checkpoints' pending states.

The isolated `dotfiles-arch` guest booted as x86_64 Arch with systemd running,
passwordless guest sudo, and no shared host mounts. Published commit
`7fd2b09e2dde6166ab87138407351cba8960bc8c` was used for these checks:

- Public bootstrap dry-run passed without cloning or installing packages.
- Real bootstrap completed its official-repository Git prerequisite full upgrade
  and cloned the migration branch. It then exited 1 at the unmanaged `.bashrc`
  preflight, before workstation provisioning or config linking.
- The refused `.bashrc` still matched `/etc/skel/.bashrc`. It was manually moved
  to `~/.dotfiles-rehearsal-backup/bashrc` in the guest, preserving SHA256
  `959bc596166c9758fdd68836581f6b8f1d6fdb947d580bf24dce607998a077b8`.
- The subsequent full core installation dry-run passed. It resolved 47 official
  targets and `vscodium-bin` from AUR, but installed none of them or their links.

The VM-only `tests/vm/run-bootstrap.py --expect-conflict` driver was used for the
Git bootstrap confirmations. It verifies the isolated guest and bootstrap hash,
answers each of the two known pacman prompts once, and refuses other questions.
It is not a general installer approval driver. Noninteractive SSH and pre-fed
answers stopped at pacman prompts; those aborted attempts were not successes.

For a controlled core run, `tests/vm/run-install.py` requires explicit published
commit and reviewed local recipe SHA256 pins:

```bash
LIMA_HOME="$HOME/.lima-dotfiles-test" python3 -B tests/vm/run-install.py \
  --commit FULL40SHA --recipe-sha256 RECIPE_SHA256
```

This host-specific driver validates the isolated guest and clean checkout, caps
official transaction and frozen-helper approvals, and stops at AUR package review.
It handles no-op native transactions without pre-feeding answers. The driver is
test infrastructure, not a replacement for production review safeguards. A review
stop or partial package installation is not a completed workstation setup.

Full installation, the revised frozen paru build, native Nix daemon/flakes,
OpenCode V2, repeat runs, Manjaro, and XFCE GUI behavior remain unverified.
The guest's separate review-only VSCodium checkout matched audited AUR commit
`d04471d2fba90dc9fc16d52be8e6f957061b5ab3`; its binary-package VM test was
explicitly approved. This checkout has not built or installed the package.

The subsequent real core run at `dbebbdab2302100b49d9fbc8917c56d019b626c6`
completed the official transaction (263 packages, including dependencies) but
stopped before paru at the immediate Nix socket check. The native service was
active; its socket appeared one second after systemd reported the service started.
This exposed a startup-readiness race, not a failed package installation. After
the run exited, no package/build process or pacman lock remained. A regular-user
daemon store ping succeeded with explicit bootstrap feature flags; `/usr/bin/nix`
was package-owned, version 2.35.3. Global Rust/Rustup/Cargo/Node/npm packages were
absent, and neither `.bashrc` nor user `nix.conf` had been linked. Full installation
and repeated runs remain pending the bounded readiness fix and retry.

The next `dbebbda` run correctly treated both native package transactions as
no-ops and reached the owned paru recipe. Archive and committed-lock checks
passed, but `prepare()` stopped at an incorrect Cargo version expectation, before
fetching dependencies or compiling. The unchanged pinned Nix bundle actually
reports Rust 1.98.1 and Cargo 1.98.0, despite both derivation names ending in
1.98.1. Published `7949583` corrects the exact executable-version guard; no lock
update or alternate toolchain was used.

A cold-daemon test of published readiness code `09179cd` exposed a second
startup state: the socket existed before it accepted connections, and the first
probe returned `Connection refused`. The helper stopped rather than retrying that
known transient failure. A later regular-user daemon ping succeeded. Readiness
validation remains pending a narrowly scoped retry for this exact native socket
error; unrelated configuration/permission errors must still stop promptly.

The frozen build at `7949583` subsequently passed: `cargo fetch --locked`,
`cargo build --release --frozen`, and the before/after lock checks completed.
Compilation took 17m45s under x86_64 emulation. Pacman installed
`paru 2.1.0.r7830fac-1` (and its generated debug package). The helper reports
libalpm 16.0.1, is owned by `paru`, uses the native ELF interpreter, and `ldd`
resolves all runtime libraries to `/usr`; no Nix-store RPATH/RUNPATH was found.
The installer then stopped intentionally at VSCodium's review prompt, before
its recipe was fetched, installed, or configs linked.

Cold daemon setup with published `18d13b4` passed in three seconds after an
explicit stop of the idle service. The revised readiness helper and subsequent
strict daemon validation both completed; the service remained active. This
verifies the real cold-start path in this guest, not every failure mode or
Manjaro compatibility. VSCodium installation and complete/repeated workstation
runs remain pending.

The fixture suite at `18d13b4` also ran inside the guest as its regular user:
229 tests passed in 143s with real GNU Stow 2.4.1, no failures or skips. This
confirms Linux fixture behavior; it does not stand in for the remaining live
installation, user configuration, or desktop checks.

VSCodium's approved local-build rehearsal then exited 0: paru built and installed
`vscodium-bin 1.140.06880-1` from the exact audited AUR checkout, with all recipe
sources and the x86_64 archive checksum passing. Its seven missing official
dependencies were installed through pacman. The sandbox helper is package-owned,
root:root, mode 4755 as reviewed. This used `paru --build --install --needed`,
not mutable AUR synchronization; the original installer is being resumed to test
its already-installed AUR path, module preparation, and links. This result is
not an XFCE launch or extension-configuration test.

Core installation at `e118831` then exited 0, including all 17 declared editor
extensions, module setup, real Stow links, launcher creation, and native Nix
validation using the linked user features. A fresh login Bash loaded `take`,
`scratch`, `gshell`, and `ai` directly from repo `shell/functions.sh`; the launcher
resolved through `~/.local/bin`. The original distribution `.bashrc` backup hash
was unchanged, and the checkout remained clean.

The real core repeat run also exited 0. Refreshed Arch indexes supplied four
upgrades (curl, Hugo, Just, pacman), which completed as a full transaction. The
installed package-name set was unchanged; five sampled managed links retained
both targets and inodes. Stow produced no new link operations, and the launcher
was recognized as already correct. VSCodium did not reinstall its extensions.
These are repeat-install results, not yet explicit config/system/update-all
command results. The user explicitly left Spotify's testing/beta AUR build
pending; do not interpret that as approval or a production package-policy change.

Explicit `link --groups core` passed without changing existing links. A real
`update configs --groups core` fast-forwarded `e118831` to `431b98e`, restarted
from the updated entrypoint, linked safely, validated Nix, and left a clean
checkout. With a newly created untracked probe present, config update exited 1
before changing HEAD and preserved the probe. Only that test-created file was
removed afterward; no user work was discarded.

The user subsequently made OpenCode the default harness and left Claude Code
opt-in (`default=false`); no Claude package was installed in the guest. Spotify
remains explicitly pending, and Brave has not received VM-install approval.
The remaining rehearsal uses additive native modules rather than changing the
production desktop package policy to silently omit either application.

The first native AI/desktop subset run stopped safely during pacman's Secret
Service provider selection, before new applications were installed. The user
selected `gnome-keyring` for this guest. The VM driver requires explicit
`--secret-service-provider gnome-keyring` approval, validates the displayed
`org.freedesktop.secrets` menu, and chooses its current index once. Without that
flag it still refuses. This test approval does not pin a provider or alter XFCE
settings in the production installer.

Pacman next requested a `jack` provider because Telegram depends on FFmpeg,
whose Arch package requires JACK-compatible libraries. After that explanation,
the user approved `pipewire-jack`, matching the guest's existing PipeWire stack.
This is a VM dependency choice, not an OpenCode requirement or an XFCE preference
change. The transaction still had not installed the pending native applications.
The next unresolved dependency was `ttf-font`: the installed coding fonts do not
satisfy that virtual package. The rehearsal uses conventional `noto-fonts` for
general UI fallback without editing font selections or XFCE preferences; the
driver still requires its exact opt-in flag rather than accepting menu defaults.

A separate guest project also verified the linked Nix workflow: an initially
locked flake pinned to the same reviewed nixpkgs revision supplied `hello` through
`mkShellNoCC`. `nix develop --no-update-lock-file --command hello` printed
`Hello, world!`, and the before/after `flake.lock` SHA256 matched. No project
tool was installed globally, and no extra experimental-feature flags were needed.

The native AI/desktop subset at `4700ad7` exited 0 after the three provider
selections. Its full native transaction handled 148 packages/dependencies and
upgrades; the pinned nono archive checksum passed, and new config links completed.
Verified package-owned OpenCode reports `opencode v2.0.29`; the managed user-local
nono link reports `nono 0.80.0`. Native Bitwarden, Discord, Mullvad, Signal,
Telegram, Thunderbird, gnome-keyring, pipewire-jack, and Noto packages are installed.
OpenCode/nono profiles, Signal's launcher, and the wallpaper are repo symlinks;
the checkout is clean and systemd reports running. Claude Code, Spotify, Brave,
Rust/Rustup/Cargo, Node.js, and npm packages remain absent. App sign-ins, Mullvad
connection/service choices, nono's registry initialization, and GUI behavior
were not exercised by this package/link validation.

At `4c4d6e4`, both explicit `update system` and `update all` with the same
39-module selection exited 0. The latter performed config fetch/restart, full
native checks, `paru -Sua --ignore paru`, module setup, relinking, and linked Nix
validation. These update runs found no new package upgrades; earlier install
repeat runs exercised actual full native upgrades. All 275 fixture tests then
passed in the guest with real GNU Stow, no skips. From the separate Nix rehearsal
project, native OpenCode's local `/api/info` request also succeeded using the
linked configuration, without a model request or sign-in.

A final fresh-shell check exposed native Bitwarden's executable name:
the package provides `bitwarden-desktop`, not `bitwarden`. Existing startup only
checked the latter and therefore skipped the intended SSH socket default.
Published `1c30d07` detects both native and legacy names without launching the
app. All 14 startup tests passed in the guest, and a real fresh-login shell then
selected the Bitwarden socket default while resolving native OpenCode and the
managed nono executable correctly. No GUI app or credential operation was launched.

A graceful Lima stop/start then booted the updated `7.2.9-arch1-1` kernel. Systemd
reported running, Nix was active without manual restart, the locked dev shell and
unchanged `flake.lock` passed again, fresh login retained the correct managed links
and Bitwarden socket default, and OpenCode's local API responded after reboot.
Mullvad remained inactive/disabled, no pacman lock remained, and the checkout
stayed clean. The VM is preserved for further review; no credentials were imported.
The final post-reboot suite at `1c30d07` passed all 277 tests in 154 seconds with
real GNU Stow, no failures or skips. The same production checkpoint passed both
CI jobs and a final independent read-only Bash/security review. This validates
the approved Arch scope above, not Manjaro desktop operation or personal auth.

References: [foreign architectures](https://lima-vm.io/docs/config/multi-arch/),
[plain mode](https://lima-vm.io/docs/config/plain/),
[Arch template](https://github.com/lima-vm/lima/blob/master/templates/archlinux.yaml).
