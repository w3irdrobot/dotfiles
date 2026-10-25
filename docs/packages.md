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

## Manual applications

The first Fedora port keeps these module selections and configuration links but
does **not** install the application. The installer prints this list for selected
modules both during selection and in successful follow-up instructions.

- **Bitwarden:** download the native Linux x86_64 RPM from
  [Bitwarden](https://bitwarden.com/download/). Review/verify the release and
  install the local RPM with `sudo dnf install ./<downloaded-file>.rpm`.
  Enable its SSH agent after signing in; the existing socket is
  `~/.bitwarden-ssh-agent.sock`. There is no official DNF repository, so later
  native RPM releases require a separate manual update. A Flatpak changes the
  socket location and is not a transparent replacement. Fedora's `libsecret`
  library alone is not an unlocked Secret Service provider.
- **Nerd Fonts:** Fedora's ordinary JetBrains Mono and Fira Code fonts are
  installed, but the configured Nerd Font family names and prompt glyphs require
  the patched fonts from [Nerd Fonts](https://www.nerdfonts.com/font-downloads).
  Install the reviewed fonts under `~/.local/share/fonts` and run `fc-cache -f`.
- **lazygit, lazydocker, kubie:** choose a reviewed RPM source or verify upstream
  binaries from the linked project releases. No global build toolchain is added.
- **Signal:** upstream distributes Debian packages, not an official Fedora RPM.
  Choose a maintained source explicitly. The existing native desktop launcher
  expects `signal-desktop`; a Flatpak needs a deliberate launcher change too.
- **Discord and Telegram:** choose a reviewed Fedora-compatible distribution or
  their upstream Linux downloads. They are not installed from an arbitrary COPR.
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
