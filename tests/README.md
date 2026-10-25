# Tests

Run `just validate` (Bash syntax, ShellCheck, shfmt, and Python stdlib tests).
CI pins shfmt 3.14.1 from the official mvdan/sh release and verifies its SHA256
before execution. Use that version when reproducing formatter differences;
older versions can disagree on default-style spacing. Native checks do not
require an exact formatter version. CI's Fedora test dependencies include
diffutils (`cmp`), also declared by the core, nono, and GnuPG module metadata.
Tests use temporary homes/repositories and an allowlisted command PATH. Package
managers, sudo, network clients, and Git network operations are mocked. Fixed
Linux host paths in **fixture copies only** are redirected to fixture os-release,
Nix, and systemd paths; production files and the real home are never changed.
Run tests as a regular user: the production CLI intentionally refuses root.

Upgrade snapshot fixtures model Btrfs devices, top-level mounts, snapshot
pruning, low disk space, failure-before-transaction, and boot-package reporting
without touching the host filesystem.

Tests cover parser rejection, unsupported hosts/distributions, dry-run home
immutability/no network/sudo, metadata-as-data, Stow conflict refusal, selected
groups, repeat linking, dirty/diverged/wrong-origin update refusal, failed
bootstrap clone/update, and checkout-local dispatch instead of PATH hijacking.
Default-off modules require additive `--modules NAME[,NAME]` opt-in. Fixtures
verify selection across groups, strict boolean metadata, selector rejection,
preservation across config-update restarts/bootstrap, dry-run exclusion of local
off-module configs, and custom provisioner failures stopping before linking.
Real GNU Stow tests clearly skip when Stow is absent; CI supplies Stow both on
Ubuntu and inside a disposable Fedora 44 container. The latter runs tests as an
unprivileged user with the source bind-mounted read-only.

SSH export fixtures cover normalized equals-form directives, inherited/repeated
identities, wildcard/negated hosts, `Match all`, unsupported-condition refusal,
missing keys, and archive basename/public-companion collisions. Encryption is
mocked and all keys are synthetic. When OpenSSH is available, `ssh -G -F` against
explicit fixture configs compares supported flattened settings with OpenSSH;
these configs contain no executable conditions or real user key/config paths.

`just check-packages` explicitly queries configured Fedora RPM sources through
DNF5. Run it on Fedora 44 after configuring the documented repositories. It
refreshes metadata, but installs no applications. Missing names are reported;
there is no arbitrary source fallback. This checks existence, not dependency
solving, trust, or real installation. The offline command works on macOS.
CI performs remote metadata checks only for master pushes. PR validation has
read-only checkout permissions, no persisted credentials, and no deployment.

## Linux rehearsal

Use a disposable x86_64 Fedora KDE Plasma Desktop 44 VM with systemd, a snapshot, and a regular
user with sudo. Do not run these installation checks on a workstation.

- Review and perform bootstrap/install; confirm Fedora-packaged Nix daemon,
  new-login environment, `nix store ping --store daemon`, and a project flake.
- Confirm pinned OpenCode archive/binary integrity and repeat installation without
  a new download or global language toolchain. Review third-party signing keys.
- Re-run install/link/update; verify optional groups, full DNF upgrades,
  ownership, desktop/login behavior, and refusal of upstream/partial Nix installs.
  Confirm the explicit manual Bitwarden RPM setup and pinned OpenCode V2; modified
  binaries and unmanaged shadows must stop setup before installing packages.
- Exercise failed downloads/checksums, cancelled RPM confirmation, and interrupted
  provisioning. Confirm failures stop subsequent phases and preserve local work.

Record the VM release, commands, results, and remaining gaps in
[the rehearsal guide](../docs/testing.md). Historical Arch results do not validate
Fedora. Fedora KDE/Wayland and System76 hardware acceptance remain pending.
