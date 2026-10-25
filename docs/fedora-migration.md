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

Do not switch desktops, disable SELinux, change networking or competing power
services, add privileged hardware groups, or flash firmware. The existing user
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
