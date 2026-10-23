# Tests

Run `just validate` (Bash syntax, ShellCheck, shfmt, and Python stdlib tests).
CI pins shfmt 3.14.1 from the official mvdan/sh release and verifies its SHA256
before execution. Use that version when reproducing formatter differences;
older versions can disagree on default-style spacing. Native checks do not
require an exact formatter version. CI's Arch test dependencies include
diffutils (`cmp`), also declared by the core, nono, and GnuPG module metadata.
Tests use temporary homes/repositories and an allowlisted command PATH. Package
managers, sudo, network clients, and Git network operations are mocked. Fixed
Linux host paths in **fixture copies only** are redirected to fixture os-release,
Nix, and systemd paths; production files and the real home are never changed.
Run tests as a regular user: the production CLI intentionally refuses root.

Tests cover parser rejection, unsupported hosts/distributions, dry-run home
immutability/no network/sudo, metadata-as-data, Stow conflict refusal, selected
groups, repeat linking, dirty/diverged/wrong-origin update refusal, failed
bootstrap clone/update, and checkout-local dispatch instead of PATH hijacking.
Default-off modules require additive `--modules NAME[,NAME]` opt-in. Fixtures
verify selection across groups, strict boolean metadata, selector rejection,
preservation across config-update restarts/bootstrap, dry-run exclusion of local
off-module configs, and custom provisioner failures stopping before linking.
Real GNU Stow tests clearly skip when Stow is absent; CI supplies Stow both on
Ubuntu and inside a disposable Arch container. The latter runs tests as an
unprivileged user with the source bind-mounted read-only.

SSH export fixtures cover normalized equals-form directives, inherited/repeated
identities, wildcard/negated hosts, `Match all`, unsupported-condition refusal,
missing keys, and archive basename/public-companion collisions. Encryption is
mocked and all keys are synthetic. When OpenSSH is available, `ssh -G -F` against
explicit fixture configs compares supported flattened settings with OpenSSH;
these configs contain no executable conditions or real user key/config paths.

`just check-packages` explicitly queries Arch and AUR HTTPS metadata. It checks
existence, not buildability, trust, package ownership, or Manjaro availability.
Official package lookup accepts `x86_64` and architecture-independent `any`
results; unmatched names fall back to AUR. Missing names are reported across all
lookup batches as absent from both sources, not mislabeled as AUR-only failures.
CI performs remote metadata checks only for master pushes. PR validation has
read-only checkout permissions, no persisted credentials, and no deployment.

## Linux rehearsal

Use a disposable x86_64 Arch/Manjaro VM with systemd, a snapshot, and a regular
user with sudo. Do not run these installation checks on a workstation.

- Review and perform bootstrap/install; confirm repository-packaged Nix daemon,
  new-login environment, `nix store ping --store daemon`, and a project flake.
- Review the actual paru PKGBUILD and dependencies before building as the regular
  user. Confirm AUR installation and upgrades without global language toolchains.
- Re-run install/link/update; verify optional groups, full pacman upgrades,
  ownership, desktop/login behavior, and refusal of upstream/partial Nix installs.
  Confirm native Bitwarden and an OpenCode V2 repository package; V1/V3 must stop
  the full transaction before installing packages.
- Exercise failed downloads/checksums, cancelled AUR review, and interrupted
  provisioning. Confirm failures stop subsequent phases and preserve local work.

Record the VM release, commands, results, and remaining gaps in
[the rehearsal guide](../docs/testing.md). It also records the completed Arch
checks; Manjaro KDE/Wayland and System76 hardware acceptance remain pending.
