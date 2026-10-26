# Fedora 44 migration

The target is a fresh **Fedora KDE Plasma Desktop 44, x86_64** installation.
Arch/Manjaro support is being removed, not retained as another backend. The
existing Stow configuration, module selections, project Nix environments, and
unmanaged-file protections stay in place.

Accepted on 2026-10-25: use Fedora RPMs first, vendor RPM repositories next, and
selected documented COPRs where needed. Keep host-integrated applications native.
Applications without a verified automated Fedora source must be reported as
manual work, not installed from an arbitrary fallback or silently substituted.

## First implementation slice: a usable Fedora install

Port bootstrap/platform validation, package metadata and DNF transactions, native
Nix ownership/readiness, pinned upstream OpenCode V2, and RPM package inventories for
Btrfs upgrade protection. Configure only selected application repositories;
System76 remains DMI-gated. Preserve interactive package/key confirmation.

Do not switch desktops, disable SELinux, change networking, add privileged
hardware groups, or flash firmware. Competing power services were initially
untouched; the accepted follow-up below adds confirmed backend changes.
The existing user
change in `shell/functions.sh` was initially excluded; the review follow-up
explicitly includes it in the PR. It adds the `ai rust` selector and the user's
nono quiet/diagnostic options without creating another managed profile.

The review follow-up also exposes the existing interactive migration tools as
`dotfiles secrets export` and `dotfiles secrets import`. They bypass Fedora
provisioning, retain the helpers' Linux/macOS behavior and current-directory
fallback, and never run from install/update. Help/dry-run are read-free dispatch
previews; real invocations suppress tracing and use checkout-owned scripts rather
than similarly named PATH commands. See [secrets migration](secrets.md).

Acceptance: fixture tests cover Fedora/version rejection, no-op dry-runs, DNF
failure propagation, missing packages, V2 policy, source selection, conflicts,
and repeat linking. Shell lint and the full fixture suite must be reported
separately from real installation testing. Fedora VM and Lemur Pro boot,
suspend, networking, audio, portal, and power testing require a real Linux host.

## Sources and remaining work

### Accepted follow-up: Bitwarden and hardware activation

Accepted on 2026-10-25: install Bitwarden's native upstream RPM with a reviewed
version/URL/SHA256 pin. Check official stable **desktop** releases via
`dotfiles check-updates` and during `update system/all`, rather than introducing
a scheduled job or silently installing an unreviewed latest release. Report
installed, pinned, and published versions separately. A release-check failure
must be visible, not reported as up-to-date; optional notices must not prevent
normal OS security updates. Dry-runs make no network requests.

Also accepted: on detected System76 hardware, show the planned service/power
backend changes and ask for confirmation before activation. Inspect actual
packaged units and competing backends, preserve Plasma PowerDevil, and do not
silently alter unknown setups. Firmware flashing, graphics/boot changes, and
privileged group membership remain manual.

Implementation slices (both authorized):

1. **Native Bitwarden and release notices:** download/verify the RPM before any
   package transaction, include it in the protected install flow, refuse unsafe
   ownership/downgrades, and provide read-only release checks. Fixture tests must
   cover exact artifact/metadata matching, failures before transactions, repeated
   installation, newer installed releases, desktop filtering, pagination/network
   failures, and read-free dry-runs. No vault or authentication data is accessed.
2. **Confirmed System76 activation:** discover/validate packaged service units,
   show conflicting power backends, obtain terminal confirmation, activate the
   selected services, and check health. Tests must cover missing units, other
   vendors, decline/EOF, partial failures, repeat runs, no-op dry-runs, and keeping
   PowerDevil/firmware/groups untouched. Actual RPM/service behavior still needs
   Fedora/Lemur Pro acceptance.

Status: implemented with synthetic artifact/release/systemd fixtures; Fedora
installation and hardware acceptance remain pending. These choices supersede
the manual Bitwarden installation and entirely manual System76 activation in
the first Fedora slice. See [package sources](packages.md) and
[System76 setup](system76.md) for the current behavior and recovery boundaries.

- [Fedora KDE 44](https://fedoraproject.org/kde/download/).
- [Native Fedora Nix setup](https://fedoraproject.org/wiki/Changes/Nix_package_tool):
  `nix nix-daemon`; `/usr/bin/nix` belongs to `nix-core`.
- [System76 Fedora guide](https://system76.com/support/system76-software/#fedora)
  and [driver repository](https://system76.com/support/system76-driver/#fedora):
  community `szydell/system76` COPR. Install specific laptop packages, not the
  wildcard bundle of desktop/OLED/DKMS drivers.
- [Ghostty Fedora source](https://ghostty.org/docs/install/binary#fedora):
  `scottames/ghostty` COPR.
- [OpenCode V2 downloads](https://opencode.ai/v2/docs/#cli) and
  [installer artifact source](https://opencode.ai/v2/install): pinned standalone
  native artifact, without executing the upstream installer or installing Node.
  The researched `sureclaw/opencode` COPR recipe reported V2, but its live Fedora
  44 RPM metadata served 1.18.30-1.fc44. Accepted on 2026-10-25: use a pinned
  upstream V2 artifact for now instead of enabling that COPR. See
  [artifact evidence](packages.md#pinned-opencode-v2).
- [Brave RPM repository](https://brave.com/linux/#fedora-41-dnf5).
- [VSCodium RPM repository](https://vscodium.com/#install-on-fedora-rhel-centos-rockylinux-opensuse-rpm-package).

## Read-only package evidence, 2026-10-25

### Accepted desktop-source follow-up

Accepted after the Bitwarden/System76 follow-up: use the upstream-recommended
`dejan/lazygit` COPR, Signal's official signed AppImage, Discord's official stable
RPM, and per-user verified Flathub apps for Telegram and Gear Lever. Include
interactive user Flatpak updates during system/all updates. Leave Nerd Font
download/installation and Plasma global font choices manual.

Implementation scope: selection-scoped COPR metadata; reviewed Discord bootstrap
pin/identity checks and update notices; isolated-keyring Signal verification before
transactions with a fixed native launcher and preserved app-owned updates; user
Flathub remote/origin checks, idempotent app installs, and explicit user-only
updates. No app launch, login, data migration, global font changes, or automatic
adoption of existing unmanaged installations. Synthetic tests cover corrupt
artifacts/signatures, wrong signing identity, conflicts, repeat runs/self-updates,
dry-runs, Flatpak scope/origin/errors, and transaction ordering. Fedora/KDE runtime
acceptance is still required. Implementation/check results are in
[testing](testing.md); operational contracts are in [packages](packages.md).

Read-only research found lazygit **0.66.2-1.fc44.x86_64** in the selected COPR.
Discord's standard RPM redirect resolved to **1.0.166**; the downloaded RPM
matched the recorded SHA256 and header identity. Its payload contains a launcher
and `updater_bootstrap`, not the full client. Signal **8.32.0** matched its recorded
SHA256 and a valid vendor signature from the pinned fingerprint. Public-key
conversion plus `gpgv` avoided an agent/socket-length problem encountered with an
initial GPG import attempt in a temporary directory; no personal keyring was used.
No Linux application or RPM script was executed during inspection.

### Earlier Fedora port evidence

HTTPS `repomd.xml`/primary metadata lookups found all **73** module RPM names
for `x86_64` or `noarch`: 65 in Fedora 44's release repository and eight across
the five selected external repositories. This was an ad hoc read-only metadata
inspection on macOS, not `just check-packages` through DNF, a dependency solve,
signature verification, or an installation. The external repository definitions
remain signature-checked by DNF during real installation.

The OpenCode artifact was downloaded into process memory, matched to its
published registry SHA512 integrity, and inspected for both pinned SHA256 hashes.
It was not executed on macOS. Actual Fedora execution and nono integration remain
part of the Linux rehearsal.

Status: implementation is ready for Linux rehearsal; local validation results
are recorded in [testing](testing.md). Fedora VM and Lemur Pro acceptance remain
pending. Check the README and package-source guide for the runnable path and
explicit manual applications. The public bootstrap remains on `master` until the
Fedora PR is reviewed and merged; pushing a review branch does not deploy it.
