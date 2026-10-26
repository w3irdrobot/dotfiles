# Fedora package sources

Dotfiles installs Fedora 44 RPMs first. Selected applications add the following
repository definitions from `repos/` as `/etc/yum.repos.d/dotfiles-<name>.repo`:

| Module | Source | RPMs allowed from that source |
| --- | --- | --- |
| brave | Brave vendor stable | brave-browser |
| mullvad | Mullvad vendor stable | mullvad-vpn |
| vscodium | Upstream-documented paulcarroty repository | codium |
| ghostty | Upstream-documented scottames/ghostty COPR | ghostty |
| system76 | System76-documented szydell/system76 COPR | system76-driver, system76-firmware, system76-power, firmware-manager |
| lazygit | [Upstream-documented dejan/lazygit COPR](https://github.com/jesseduffield/lazygit#fedora--amazon-linux-2023--centos-stream) | lazygit |

COPRs are community packages, not Fedora or vendor support guarantees. All
definitions require RPM signatures, restrict package names, and fail if their
source is unavailable. Review signing-key prompts. Existing destination files
must match byte-for-byte; dotfiles refuses to overwrite a modified definition.
If you already enabled one of these sources under another filename, resolve
duplicate or conflicting repository definitions manually.

Fedora supplies Nix (`nix nix-daemon`), Bitcoin Core
(`bitcoin-core-server bitcoin-core-utils`), Docker-compatible Moby
(`moby-engine docker-cli docker-compose docker-buildx`), and most CLI tools.
Docker daemon activation remains manual. No RPM Fusion repository is enabled.
See [migration sources](fedora-migration.md) for the researched upstream links.

## Pinned OpenCode V2

Fedora 44's researched `sureclaw/opencode` COPR served **1.18.30**, despite its
source recipe reporting V2. Do not enable it for this setup. OpenCode uses the
upstream installer's native Linux glibc x64 baseline artifact at pinned **2.1.4**:

`https://registry.npmjs.org/@opencode/cli-linux-x64-baseline/-/cli-linux-x64-baseline-2.1.4.tgz`

This is a standalone executable download, not a Node/npm installation. The
archive SHA256 is `bfcb5c1931063e9835179ef4f1ee35eb3598d23ec77c31f0d5beedb45419fd25`;
the binary SHA256 is `ca9b3ee262e33bb4e7aa0e1230dc61086a474c8c8016b980081d0719712fd2e7`.
The downloaded archive matched the npm registry's published SHA512 integrity
value on 2026-10-25. This is integrity pinning, not an independent vendor signature.
Both SHA256 checks must pass before the binary is executed or published.

The launcher is `~/.local/bin/opencode`; its target lives under
`~/.local/share/dotfiles/opencode/2.1.4/`. Conflicting PATH copies, symlinked
parents, dangling launchers, or edited pinned binaries stop setup without
replacement. Repeat installation verifies and reuses the exact binary.
Update the version, URL, hashes, and matching PATH guards in a reviewed repository
change; do not invoke OpenCode's self-updater on the pinned file. DNF does not
update this binary. For an AI-only selection without the managed Bash config,
ensure `~/.local/bin` is on PATH in your own shell.

## Pinned native Bitwarden

Selecting Bitwarden installs the native upstream x86_64 RPM using the version,
URL, and SHA256 in `modules/bitwarden-release.json` (currently **2026.10.1**).
The download must match both the checksum and expected RPM identity before the
protected DNF upgrade/install flow. A verified cache is reused; conflicting files
are not overwritten. Equal/newer installed versions are kept, not downgraded.

Run `dotfiles check-updates` for installed, reviewed-pin, and published stable
desktop versions. `dotfiles update system/all` also checks when Bitwarden is
selected or installed. These checks do not change pins or install releases.
Network/metadata errors report unknown status; optional notices do not fail a
completed OS update. Dry-runs make no release/download requests.

To update, review the official desktop release, update all three pin fields in
a repository change, then rerun install/update with Bitwarden selected. There is
no configured Bitwarden DNF repository or unattended updater. SHA256 pinning is
artifact integrity verification, not an independent vendor signature; the
reviewed RPM had no RSA/PGP signing tag. Dotfiles does not disable DNF signature
policy; if local policy rejects the artifact, investigate rather than bypass it.

Sign in and enable its SSH agent manually; the socket remains
`~/.bitwarden-ssh-agent.sock`. No vault/login import is performed. A Flatpak
changes that integration and is not a transparent replacement. Fedora's
`libsecret` alone is not an unlocked Secret Service provider.

## Discord's official RPM

Discord selects the reviewed version/URL/SHA256 in
`modules/discord-release.json` (initially **1.0.166**). Like Bitwarden, its cache
must pass SHA256 and exact name/version/release/architecture checks before the
protected package transactions. Equal/newer installed RPMs are kept. No DNF
signature policy is disabled; the inspected RPM has no RSA/PGP signing tag.

`dotfiles check-updates` and system/all update notices also compare Discord's
installed/reviewed bootstrap RPM against the stable vendor download redirect.
Notices do not download/install a new RPM. Review the new artifact and update
all pin fields before installing a newer bootstrap.

The vendor RPM is a **bootstrapper**, not the full client: its launcher downloads
the client into `~/.config/discord` on first launch, and Discord manages its
user-level client separately. The RPM pin does not freeze or independently
verify that later download. Dotfiles validates RPM ownership without launching
Discord or inspecting its authentication data.

## Signal AppImage and Gear Lever

Signal now publishes an [official AppImage](https://signal.org/download/linux/).
The initial installation is pinned in `modules/signal-release.json` (initially
**8.32.0**). Before package transactions, setup checks both the AppImage and public
key SHA256, then verifies the detached signature from the pinned identity
`4B16B7232DFAA439AD791002EF9F501F13EED94C` using an isolated temporary public
keyring. It never imports anything into your GPG home or launches the AppImage.
The Fedora workstation must already have `gpg`, `gpgv`, Python, and curl for this
pre-transaction check; missing tools stop setup rather than installing unchecked
prerequisites first. The selected packages retain these tools and FUSE support.

The writable AppImage lives at
`~/.local/share/dotfiles/signal/Signal.AppImage`; Stow links the `signal-desktop`
launcher into `~/.local/bin` and retains our existing desktop entry and
`--password-store=gnome-libsecret` integration. Ensure `~/.local/bin` is on PATH
if you select Signal without managed Bash. Login/linking and an unlocked Secret
Service provider remain manual; `libsecret` alone does not supply one.

After the initial install, **Signal owns its in-place updates** (configure them
in Signal). Repeat setup preserves the managed app, including self-updated bytes;
it does not reapply the initial hash, downgrade, or execute it for inspection.
An incomplete/unmanaged installation or conflicting PATH executable requires
manual resolution. Do not move this managed file through Gear Lever—the launcher
already integrates it into the menu and expects that fixed path.

Gear Lever is installed as the verified user Flatpak `it.mijorus.gearlever`.
Use its GUI to integrate/manage other AppImages; its own Flatpak sandbox does
not make the AppImages it launches sandboxed. The initial Signal pin/signature
flow remains separate from Gear Lever's GUI/update features.

## User Flatpaks

Telegram uses the verified Flathub app `org.telegram.desktop`; Gear Lever uses
`it.mijorus.gearlever`. Selecting either installs Fedora's `flatpak` package and
adds the official **user** Flathub remote if absent. A conflicting remote URL,
disabled/signature-verification-disabled remote, or app from another user remote
stops setup rather than being replaced. Existing system Flatpaks and system
remotes are left alone; no data is migrated from native or system installations.

Install is interactive and repeat runs reuse selected user apps. System/all
updates run `flatpak update --user` when Flatpak is available, updating **all
installed user Flatpaks**, even ones not selected in that command. Flatpak update
failures stop the command visibly; completed RPM updates are not rolled back.
Flatpak checks/installs/updates make no network requests during dry-runs.

## Manual applications

The first Fedora port keeps these module selections and configuration links but
does **not** install the application. The installer prints this list for selected
modules both during selection and in successful follow-up instructions.

- **Nerd Fonts:** Fedora's ordinary JetBrains Mono and Fira Code fonts are
  installed, but the configured Nerd Font family names and prompt glyphs require
  the patched fonts from [Nerd Fonts](https://www.nerdfonts.com/font-downloads).
  Install through KDE System Settings → Font Management (personal fonts), or put
  the reviewed fonts under `~/.local/share/fonts` and run `fc-cache -f`. The configs
  already reference these Nerd Font families; setup does not change Plasma's
  global font settings.
- **lazydocker, kubie:** choose a reviewed RPM source or verify upstream
  binaries from the linked project releases. No global build toolchain is added.
- **Google Cloud CLI / GKE plugin:** follow
  [Google's RPM instructions](https://cloud.google.com/sdk/docs/install), then
  install `google-cloud-cli` and `google-cloud-cli-gke-gcloud-auth-plugin`.
- **Sparrow:** verify its upstream release signature before installing. Wallets
  and keys are always migrated separately.
- Optional **1Password** and **Slack** likewise use a separately reviewed vendor
  install when explicitly selected.

Manual applications do not become DNF-repository-managed just because their
configuration is linked. `dotfiles update system` does not update standalone
downloads or unconfigured vendor repositories. No application login is automated.
