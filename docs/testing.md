# Installer rehearsal

Run `just validate` for shell checks and disposable fixture tests. They cover
argument handling, conflict safety, repeated runs, and failure paths without
provisioning the developer's machine. See [test coverage](../tests/README.md).
Real RPM dependency resolution, Nix daemon operation, and desktop integration
need a Linux rehearsal.

## Verified scope

**Fedora KDE Plasma Desktop 44 and System76 lemp14 hardware acceptance are
pending.** The target changed on 2026-10-25; earlier Arch/Manjaro results below
are historical evidence, not Fedora acceptance. The Arch-only VM drivers and
paru build fixtures have been removed with that backend.

## Disposable Linux VM

Use the regular Fedora KDE Plasma Desktop 44 x86_64 ISO, not Kinoite/Atomic.
Verify the ISO checksum/signature, install into a disposable VM with systemd,
Btrfs root, and a regular user with sudo, then take a hypervisor snapshot.
Keep host-home mounts, personal SSH keys, and agent forwarding disabled.
On an ARM Mac, an x86_64 guest needs an emulator; Rosetta is not an x86_64 kernel.
Install or launch VM software only with approval. No Fedora VM image or automated
prompt-approval driver is currently checked in.

Transfer or clone the reviewed Fedora branch inside the guest. Local changes
are not served by the public bootstrap until published. Run:

```bash
bash bin/dotfiles install --dry-run
bash bin/dotfiles install
```

Review package plans and signing keys interactively. Keep the VM until review is
complete; deleting it is a separate approved action.

## Acceptance checklist

1. Review the bootstrap, modules, and checkout branch/commit.
2. Run a local dry-run as a normal user. Confirm no file changes, network
   requests, or privileged commands.
3. Test an existing `.bashrc`, a dangling config link, and a conflicting parent
   path. Each must stop with the original path untouched.
4. Back up and resolve conflicts manually. Install core, then repeat it. Verify
   Fedora RPM ownership and stable links. Native Nix must belong to `nix-core`;
   OpenCode must be the pinned verified upstream V2 binary, not the V1 COPR RPM.
5. Open a fresh login shell. Check `nix --version`, daemon access, flakes support,
   and a project's locked dev shell without global Rust/Node toolchains.
6. Install the default groups. Test Ghostty, VSCodium, clipboard behavior,
   Bitwarden's RPM ownership, native launcher/SSH agent, and OpenCode/nono.
   Run `dotfiles check-updates`; verify installed/pinned/published versions,
   visible network-failure status, reviewed-pin updates, and no downgrades.
   Check lazygit's COPR/RPM ownership and Discord's bootstrap RPM without treating
   its version as the user-downloaded client version. Test Signal's AppImage/FUSE
   launch, Secret Service, self-update, and repeat install preserving the updated
   app. Confirm per-user Telegram/Gear Lever menu integration, file pickers, links,
   notifications and user-only Flatpak updates; system apps/remotes stay untouched.
   Do not move the managed Signal AppImage via Gear Lever.
   In Plasma Wayland, check session type,
   portal file pickers/screen sharing, and Signal persistence with an unlocked
   Secret Service provider. Test XWayland apps without global Electron flags and
   confirm TTY installation still works.
7. Interrupt installation and rerun. Partial checkouts and upstream/partial Nix
   installs must be diagnosed, not overwritten or marked complete. Repository
   OpenCode shadows or modified pinned binaries must stop before installation.
8. Test config updates with clean, dirty, and diverged histories, plus a new
   config whose destination already exists. Confirm local work survives refusal.
9. Run system updates and verify full native upgrades rather than partial ones.
   On Btrfs, confirm the pre-upgrade snapshot exists and rollback notes name the
   correct device and subvolumes; a failed snapshot must stop before DNF upgrade.
   Fedora normally has separate `/boot` and EFI partitions: a root-only rollback
   is not a complete kernel/boot rollback. Rehearse recovery from live media.
10. Confirm setup leaves desktop settings, autologin, networking, Docker-group
    membership (unless requested), wallets, keys, and local credentials alone.
11. On lemp14, verify DMI detection, Fedora/COPR dependency resolution, repeat install,
     hotkeys, suspend/resume, and battery controls after confirmed service
     activation. Check decline/no-terminal behavior before accepting the plan,
     daemon health and wake enablement afterward, repeat-run idempotence, and
     power-backend recovery failures. Keep PowerDevil. Confirm no firmware
     flashing, privileged groups, or user notification timer changes.
     A generic VM cannot verify the hardware behavior.

12. Verify the explicit manual application report against
    [package sources](packages.md). Configuration links alone must not be treated
    as an installed lazydocker, kubie, Sparrow, or Nerd Font.

## Fedora port local checks, 2026-10-25

On the macOS development host, `just validate` passed Bash syntax, ShellCheck,
shfmt, and **309 fixture tests (306 passed, three skipped)**. Skips were the two
real GNU Stow checks (Stow unavailable) and one case-sensitive-filename fixture
on this case-insensitive filesystem. `python3 scripts/check-packages.py` passed
offline syntax validation for all 73 RPM names; `git diff --check` passed.

New fixtures cover Fedora release rejection; shared bat/VSCodium platform
validation; full-default no-op dry-runs; DNF refresh/query/transaction ordering;
metadata-only caching with RPM downloads allowed; missing names and command
failures; selected-source conflicts and repeat setup; native Nix package policy;
and pinned OpenCode archive/binary checks, failed-download retry, no-clobber
publication, V2 reporting, and PATH shadows. Existing snapshot fixtures now use
Fedora's `root` subvolume and RPM inventories.

The review follow-up adds launcher-from-PATH coverage plus eight secrets CLI
dispatch fixtures. Those cover interactive helper selection, preserved working
directory and exit status, no PATH fallback, rejected arguments, read-free
help/previews, cross-platform dispatch without provisioning, and suppression of
DEBUG/inherited tracing. They use stub scripts and synthetic data; no real keys,
wallets, authentication stores, or secret archives were read. The longer-budget
full run completed successfully after the earlier 120-second rerun timed out.

Bitwarden/System76 follow-up fixtures cover checked native RPM preparation and
cache reuse/conflicts, no downgrades, installed ownership, public desktop-release
filtering/pagination/errors, read-free previews, terminal confirmation/decline,
unit ownership/overrides, persistent backend masking, health checks, repeat runs,
and partial activation/recovery failures. The initial expanded run exposed a
duplicate Python fixture symlink; that fixture setup was corrected before the
successful full rerun. These tests use only synthetic RPM bytes and systemd state.

Read-only inspection verified the Bitwarden 2026.10.1 RPM SHA256 against the pin
and its identity `bitwarden|2026.10.1|1|x86_64`; its header had digest tags but no
RSA/PGP signing tag. Actual System76 Fedora RPM payloads confirmed the firmware,
power, and wake unit names documented in [System76 setup](system76.md), and no
driver `system76.service`. No package scripts were executed. A live public API
check reported stable desktop 2026.10.1 and the matching reviewed digest; installed
RPM status was correctly unknown on macOS, where RPM is unavailable.

Separate read-only HTTPS metadata inspection found all 73 module RPM names for
x86_64/noarch in Fedora 44 and the selected repositories. The pinned OpenCode
2.1.4 artifact matched registry integrity and its recorded archive/binary hashes.
See [migration evidence](fedora-migration.md#read-only-package-evidence-2026-10-25).

No Fedora container/VM was launched, no real DNF dependency solve or transaction
was run, and no Linux binary was executed on the host. The updated Fedora CI
jobs have not been run here. Fedora install/reinstall, native Nix operation,
OpenCode/nono execution, KDE integration, and boot recovery still need the Linux
rehearsal above; laptop boot/suspend/power checks require the Lemur Pro.

## Desktop-source follow-up checks

The final `just validate` run passed Bash syntax, ShellCheck, shfmt, and
**331 fixture tests (328 passed, three skipped)**. The skips remain the two
GNU Stow checks and one case-sensitive-filename fixture described above.
`git diff --check` also passed.

The 22 new targeted desktop-source fixtures passed on macOS. They exercise
Discord's checked bootstrap RPM/no-downgrade flow, Signal's initial hashes and
isolated signature verification before transactions, wrong signing identities,
cache/install conflicts, preserved Signal self-updates, and user Flatpak remote
origins, repeated installs, scope, failures, and side-effect-free dry-runs.
The existing update/restart fixture now explicitly expects user Flatpak updates
for `update all`, but not `update configs`; its earlier mock rejected the new
command and was corrected rather than weakening production failure propagation.

`python3 scripts/check-packages.py` validated **76** current RPM names offline;
this does not extend the earlier 73-name remote evidence to all new dependencies.
Read-only vendor inspection verified Discord 1.0.166's RPM identity/checksum and
Signal 8.32.0's AppImage/key hashes and detached vendor signature. Live release
checks reported the reviewed Bitwarden and Discord versions with no newer stable
releases, and correctly reported unavailable RPM inventory on macOS. No Linux
application, actual Flatpak install/update, or DNF transaction was executed.
Fedora/KDE launcher, FUSE, updater, portals and notifications still need rehearsal.

## Piped bootstrap checks

`just validate` passed Bash syntax, ShellCheck, shfmt, and **335 fixture tests
(332 passed, three skipped)** with the same Stow/filesystem skips described above.
The final helper-order cleanup also passed shell checks and the four targeted
piped-bootstrap tests. Real Fedora/terminal provisioning remains unverified.

The primary install command is now `wget -O- ... | bash`, with Bash `pipefail`
enabled in the caller. The bootstrap gives interactive descendants terminal
input while restoring the parser's source stdin afterward. Without a terminal,
real installation stops before Git/package work; help and dry-runs still work.

Four new synthetic fixtures cover piped dispatch/argument preservation, separate
Git-prerequisite and setup confirmation input, restored source input, terminal
absence, and no-op help/previews. The shared fixture replaces `/dev/tty` with a
temporary input file; no real provisioning or host terminal prompts are used.
OpenCode's standalone guards remain unchanged: they protect the dependency-only
Git bootstrap, before the checkout's own guards can run.

## First Fedora install: package-query separator fix

A real installation reported `RPM package unavailable: git` before the main
package transactions. The DNF5 custom query format lacked an explicit newline,
while the shell parser expected one package name per line. The fixture used
Python `print()` for each package, accidentally supplying the missing separator.

The installer (including its Fedora Nix check) and standalone package checker
now request `%{name}\n`. The DNF fixture renders the requested format instead of
adding newlines itself, and regression assertions cover the explicit separator.
Package resolution now has its own phase label, separate from metadata refresh.
The corrected installer still needs confirmation on the user's Fedora machine.
Local `just validate` passed shell checks and **336 fixture tests (333 passed,
three skipped)**, including the corrected DNF5 formatting regression.
See [DNF5 repoquery formatting](https://dnf5.readthedocs.io/en/latest/commands/repoquery.8.html#formatting-options).

The next real-install preflight failure named `wget`: Fedora 44 ships that
command in the concrete `wget2-wget` RPM, with `wget` as a provided capability.
Base dependencies now select `wget2-wget`. The fixture models that provider/name
difference and asserts the concrete name is queried and installed. All 15 Fedora
package-flow tests, shell checks, and `git diff --check` passed for this follow-up;
the full suite was not rerun locally. Source:
[Fedora 44 wget2-wget files/provides](https://packages.fedoraproject.org/pkgs/wget2/wget2-wget/fedora-44.html).

The first selected-application transaction then failed on Brave's required
`brave-keyring` RPM: our `includepkgs` filter allowed only `brave-browser`.
The filter now permits exactly both names, with package signature checking
unchanged. The DNF fixture models that dependency being filtered out, and tests
also preserve refusal to overwrite an older installed repository definition.
All 17 Fedora package-flow tests, shell checks, and diff whitespace checks passed;
the full suite was not rerun locally for this filter-only fix. Existing installs
need the manual repository-line update documented in [package sources](packages.md).

After RPM installation, Bitwarden validation incorrectly required RPM ownership
of `/usr/bin/bitwarden`. Re-downloading the reviewed 2026.10.1 RPM and matching its
SHA256 confirmed the owned executable is `/opt/Bitwarden/bitwarden`; the RPM's
post-install script creates the launcher through alternatives or a direct symlink.
No package script was executed during this inspection. Validation/preflight now
check the resolved native target and its RPM ownership. Fixtures reproduce an
unowned launcher with both link layouts and reject arbitrary/dangling targets.
The final `just validate` passed shell checks and **341 fixture tests (338 passed,
three skipped)**; the original Stow/filesystem skips remain. Confirmation on the
user's Fedora installation is still needed.

The next System76 activation stop was a false positive for Fedora's global
`service.d/10-timeout-abort.conf`. A photo of `systemctl cat/show` on the user's
laptop showed this packaged default and its sole `TimeoutStopFailureMode=abort`
setting, not a machine-local service override. The guard now accepts that exact
path only when it is a regular `systemd`-owned file with the reviewed settings;
it leaves the file unchanged. Unknown/additional drop-ins, changed directives,
missing/symlinked files, and ownership/query failures remain refusals before any
service changes. All 17 System76 service fixtures, shell checks, and diff checks
passed; the full suite was not rerun locally for this follow-up. The laptop's
activation after this fix still needs user confirmation.

Signal subsequently launched from the terminal but KDE's application menu could
not find `signal-desktop`: the menu did not inherit Bash's user-bin PATH. The
desktop entry now uses an explicit home-directory launcher path through `/bin/sh`,
with URL arguments passed separately rather than interpolated into shell code.
It also no longer adds a different password-store override from a plain terminal
launch, preserving the user's currently working behavior after their profile
reset. This aligns entry points; it does not select/migrate keyrings or establish
that a particular Secret Service provider remains stable across reboots.
Two fake-HOME launcher tests passed (missing user-bin PATH, spaces in HOME,
quoted/shell-like URI forwarding, menu/terminal argument equivalence), along with
all 22 desktop-source tests, shell checks, and diff checks. No real Signal profile
or keyring was read, and the full suite/KDE launcher was not run locally for this
follow-up. After pulling, refresh KDE's menu cache with `kbuildsycoca6 --noincremental`.

## SSH template privacy correction

The tracked SSH template previously contained stale personal host blocks despite
the intended secrets-only migration contract. It now contains only the local
include and generic defaults; personal hosts/identity paths are not reconstructed
or moved from the stale template. The source machine's cleaned current config is
the migration input. No live SSH configs, keys, archives, or authentication stores
were inspected or changed during this correction, and Git history was not rewritten.

Regression checks enforce the generic-only template and no exported concrete hosts
when a synthetic HOME has no local fragment. Import duplicate-protection fixtures
now create their own synthetic existing host rather than depending on a personal
host embedded in Git. The final `just validate` passed shell checks and **348 tests
(345 passed, three expected skips)**, including the synthetic secrets round trips;
`git diff --check` passed. Machine-local files under the Stow SSH directory are
ignored except for the generic template, as a staging guard.

## Explicit-only secrets export selection

Export pickers now require marked rows: Enter with no marks skips a category
instead of accepting fzf's focused row, and an all-empty selection creates no
archive. Personal fzf auto-selection/output overrides are disabled for these
pickers. Picker errors/forged output fail closed, and selected GPG records must
contain a nonempty hexadecimal key ID before any secret-key export call. This
prevents an empty GPG selector from accidentally exporting every secret key.

Five new synthetic tests cover unmarked focused rows, one-key-only export,
skipping GPG while exporting SSH, invalid/empty/option-like IDs, and picker
failures/forged selections. They exercise the actual Enter action shell with a
fake selection count and stub GPG; no real keys, vaults, or archives were read.
The USB discovery fixture's placeholder key ID was updated to valid synthetic
hex so it continues reaching its intended discovery-failure check.
The final `just validate` passed shell checks and **353 tests (350 passed, three
expected skips)**; diff whitespace checks passed. Real interactive fzf export
with the user's secrets was not run by the agent.

## Historical results (unsupported Arch/Manjaro backend)

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
