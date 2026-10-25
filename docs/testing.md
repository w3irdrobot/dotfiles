# Installer rehearsal

Run `just validate` for shell checks and disposable fixture tests. They cover
argument handling, conflict safety, repeated runs, and failure paths without
provisioning the developer's machine. See [test coverage](../tests/README.md).
Real package resolution, AUR builds, Nix daemon operation, and desktop integration
need a Linux rehearsal.

## Verified scope

The preserved x86_64 Arch guest passed core installation and repeat installation,
link/config/system/update-all commands, locked Nix development, native OpenCode
API startup, and reboot persistence on 2026-10-14–15. Later checks covered the
full-default repeat install, Brave package installation, nono runtime-pack setup,
and private environment-file isolation. Details and commit checkpoints are below.

**Manjaro KDE/Wayland and System76 lemp14 hardware acceptance remain pending.**
The headless Arch guest establishes package and CLI behavior, not graphical
integration, Manjaro branch compatibility, personal sign-ins, or laptop behavior.
Earlier XFCE expectations are historical, not the current desktop target.

## Disposable Linux VM

[Lima](https://lima-vm.io/docs/) supports an Arch Linux template. On an ARM Mac,
use an x86_64 QEMU guest, not Arch Linux ARM. Emulation is slow. Install Lima,
QEMU, and guest agents separately with approval; the dotfiles installer does not
install VM software on macOS.

The checked-in Lima 2.2.1 configuration pins the Arch image and checksum, uses
6 GiB RAM and a 40 GiB disk, and disables host mounts, personal public-key
loading, agent forwarding, and containerd. Guest SSH uses localhost port 60022.
Use a dedicated state directory:

```bash
export LIMA_HOME="$HOME/.lima-dotfiles-test"
# Create once; preserve an existing instance.
limactl create --name=dotfiles-arch --yes tests/vm/arch-x86_64.yaml
limactl start --yes --timeout=30m dotfiles-arch
limactl shell dotfiles-arch
```

Tart requires the guest architecture to match the host. Rosetta translates apps
inside ARM guests, not an x86_64 kernel; it cannot replace this rehearsal on an
ARM Mac. See [Tart's architecture check](https://github.com/openai/tart/blob/main/Sources/tart/VM.swift).

Clone the branch under review inside the guest. Keep host home mounts disabled
and confirm a normal non-root user, sudo access, networking, systemd, sufficient
disk space, and a snapshot before installing. Use a separate disposable Manjaro
KDE x86_64 VM or the target machine for the desktop checks. Keep the VM until
review is complete; VM deletion is a separate, approved action.

## Acceptance checklist

1. Review the bootstrap, modules, and checkout branch/commit.
2. Run a local dry-run as a normal user. Confirm no file changes, network
   requests, or privileged commands.
3. Test an existing `.bashrc`, a dangling config link, and a conflicting parent
   path. Each must stop with the original path untouched.
4. Back up and resolve conflicts manually. Install core, then repeat it. Verify
   repository-first package ownership and stable links; Bitwarden, OpenCode V2,
   and Nix must be native packages.
5. Open a fresh login shell. Check `nix --version`, daemon access, flakes support,
   and a project's locked dev shell without global Rust/Node toolchains.
6. Install the default groups. Test Ghostty, VSCodium, clipboard behavior,
   Bitwarden's SSH agent, and OpenCode/nono. In Plasma Wayland, check session type,
   portal file pickers/screen sharing, and Signal persistence with an unlocked
   Secret Service provider. Test XWayland apps without global Electron flags and
   confirm TTY installation still works.
7. Interrupt installation and rerun. Partial checkouts and upstream/partial Nix
   installs must be diagnosed, not overwritten or marked complete. Repository
   OpenCode V1/V3 must stop upgrades before package installation.
8. Test config updates with clean, dirty, and diverged histories, plus a new
   config whose destination already exists. Confirm local work survives refusal.
9. Run system updates and verify full native upgrades rather than partial ones.
   On Btrfs, confirm the pre-upgrade snapshot exists and rollback notes name the
   correct device and subvolumes; a failed snapshot must stop before `pacman -Su`.
10. Confirm setup leaves desktop settings, autologin, networking, Docker-group
    membership (unless requested), wallets, keys, and local credentials alone.
11. On lemp14, verify DMI detection, Manjaro package resolution, repeat install,
    hotkeys, suspend/resume, and battery controls after manually reviewed service
    activation. Resolve power-backend conflicts while keeping PowerDevil.
    Confirm setup itself activates no System76 services, flashes no firmware,
    and adds no privileged groups. A generic VM cannot verify these checks.

## Controlled VM drivers

The drivers in `tests/vm/` target the isolated rehearsal guest. They validate
guest identity and reviewed inputs, cap known approvals, and stop at unexpected
prompts. They are test infrastructure, not general unattended installers.

The drivers target `master`. For a real run after merging, manually prepare a
clean guest checkout at the reviewed published commit. The bootstrap driver also
requires `~/install-dotfiles.sh` in the guest to match its checked-in
`BOOTSTRAP_SHA`; review and refresh that pin whenever `install.sh` changes.
The driver does not download or switch branches for you.

`run-bootstrap.py --expect-conflict` verifies the bootstrap hash and approves
each known Git-prerequisite pacman prompt once. It then expects the unmanaged
`.bashrc` refusal. Noninteractive SSH or pre-fed answers are not substitutes for
this controlling-terminal workflow.

For a core run, supply the published commit and reviewed local recipe hash:

```bash
LIMA_HOME="$HOME/.lima-dotfiles-test" python3 -B tests/vm/run-install.py \
  --commit FULL40SHA --recipe-sha256 RECIPE_SHA256
```

The driver checks a clean checkout, handles no-op native transactions, and stops
at AUR review. Secret Service, JACK, and font provider selections require their
explicit approval flags. The observed guest used `gnome-keyring`, `pipewire-jack`,
and `noto-fonts`; those are VM choices, not production defaults.
`run-vscodium.py` exercises a separately reviewed VSCodium build.
A review stop or partially installed transaction is not a completed setup.

## Recorded results

These checkpoints summarize observed results, not instructions to rerun old
commits. Superseded failures remain useful regression context; Git history holds
the detailed chronological log.

### Arch rehearsal, 2026-10-14–15

- At `7fd2b09`, bootstrap installed Git prerequisites and cloned the migration
  branch, then correctly refused the distribution `.bashrc` before workstation
  provisioning. The manually backed-up file retained SHA256
  `959bc596166c9758fdd68836581f6b8f1d6fdb947d580bf24dce607998a077b8`.
- The native transaction at `dbebbdab` installed 263 packages, then exposed a Nix
  readiness race: the socket could appear after service activation or exist
  before accepting connections. The bounded retry at `18d13b4` passed a real
  cold start in three seconds. Unrelated readiness errors still stop setup.
- The frozen paru build at `7949583` passed locked fetching, frozen compilation,
  and before/after lock hashes. It took 17m45s under emulation. Installed
  `paru 2.1.0.r7830fac-1` used libalpm 16.0.1, the native ELF interpreter and
  `/usr` runtime libraries, with no Nix-store RPATH/RUNPATH. Rust 1.98.1 and Cargo
  1.98.0 were verified separately despite both derivations being named 1.98.1.
- Reviewed AUR VSCodium commit `d04471d2fba90dc9fc16d52be8e6f957061b5ab3`
  built and installed `vscodium-bin 1.140.06880-1` with verified sources and
  archive checksum. Its sandbox helper was package-owned, root:root, mode 4755.
- Core installation at `e118831` configured all 17 editor extensions, real Stow
  links, the launcher, and native Nix. A fresh login loaded shell functions from
  the repo. Repeat installation preserved the package-name set and five sampled
  link targets/inodes while completing a full native upgrade.
- `link --groups core` and config update from `e118831` to `431b98e` passed.
  An untracked probe caused update refusal before HEAD changed and was preserved.
- Native AI/desktop subset installation at `4700ad7` passed with OpenCode 2.0.29
  and nono 0.80.0. At `4c4d6e4`, system/update-all commands passed with the same
  39-module selection, and a separate locked Nix shell printed `Hello, world!`
  without changing `flake.lock`. OpenCode's local API responded without sign-in
  or a model request.
- `1c30d07` corrected native Bitwarden executable detection. A fresh login chose
  its SSH socket without launching the app. After a graceful guest reboot, Nix,
  the locked dev shell, managed links, socket default, and OpenCode API still
  worked. Mullvad stayed inactive/disabled. All 277 guest fixture tests passed
  with real GNU Stow and no skips; the checkout remained clean.

### Follow-up checks

- At `691dbd6`, fresh and repeat provisioning of
  `nolabs-ai/opencode@0.4.0` passed in the guest, including signed-pack metadata,
  pinning, unchanged repeat lockfile, and profile validation. `ai --version`
  worked from a project; broad `$HOME` grants failed on credential-deny overlap.
  All 302 guest tests passed with real Stow and no skips.
- Reviewed Brave snapshot `8ede66185c519130ac3bfb423be40acbec7f8c12`
  (`brave-bin` `1:1.97.57-1`) built and installed through paru after a stalled
  download was safely resumed and its checksum verified. Package ownership,
  version, and the root-owned mode-4755 sandbox were checked without disabling
  sandboxing. The full 40-module default repeat install at `691dbd6` then passed.
  This was a provisioned, headless guest, not a fresh graphical install.
- Private environment overrides moved to `~/.config/bash/variables.sh`.
  All three managed profiles validated and denied a synthetic private file while
  allowing a project control file. Broad fixture-home grants failed closed.
  Tests used copied public pack artifacts and a dummy SSH socket, not credentials.
- Safety follow-ups covered nonstandard SSH identity names, exact USB mountpoint
  selection, standalone/library OpenCode PATH-guard parity, and certificate
  output conflicts. Real OpenSSL in a disposable directory created both outputs
  at `0600` under caller umask `022`; repeat invocation preserved their bytes.
  The local suite then ran 363 tests with three skips: two Stow checks and one
  case-sensitive-filesystem check. Bash syntax, ShellCheck, and shfmt passed.

### KDE/System76 checks, 2026-10-23

The baseline changed to Manjaro KDE/Wayland with DMI-gated System76 selection.
The local suite ran 375 tests with three skips (the same Stow/filesystem limits).
Nine hardware/session tests covered vendor normalization, lemp14 reporting,
missing DMI, explicit-selector gating, unsafe model text, repeat selection,
TTY/X11/Wayland guidance, and a mocked Manjaro dry-run. Scoped Bash syntax,
ShellCheck, shfmt, and `git diff --check` passed. Read-only Arch/AUR lookups found
all six added package names, which does not prove Manjaro dependency compatibility.

No live provisioning, graphical session, firmware operation, or hardware check
ran on the macOS host. Complete the remaining Manjaro KDE/Wayland and lemp14
acceptance checks before describing those targets as verified.

References: [foreign architectures](https://lima-vm.io/docs/config/multi-arch/),
[plain mode](https://lima-vm.io/docs/config/plain/),
[Arch template](https://github.com/lima-vm/lima/blob/master/templates/archlinux.yaml).
