# Dotfiles

My Fedora KDE Plasma workstation. Fedora owns the system (RPMs, Flatpaks,
services); [Home Manager](https://github.com/nix-community/home-manager) owns my
user environment (CLI tools, fonts, shell, config files). Cloud and Kubernetes
tools stay off PATH until I ask for them.

## Install

On a fresh Fedora KDE (44+) install, as your normal user:

```bash
curl -fsSL https://dotfiles.w3ird.tech/install.sh | bash
```

That installs git, clones this repo to `~/projects/github.com/w3irdrobot/dotfiles`
over HTTPS, and runs `bootstrap.sh`. Expect DNF and Flatpak prompts. To review it
first, download `install.sh` and read it. To try a branch:
`... | bash -s -- --ref BRANCH`. Optional extras:

```bash
curl -fsSL https://dotfiles.w3ird.tech/install.sh | bash -s -- --docker --yubikey --bitcoin
```

Then log out and back in, run `tailscale up`, and turn on Bitwarden's SSH agent.

## What goes where

| Thing | Where | How it's installed |
| --- | --- | --- |
| CLI tools, Nerd Fonts, opencode | `home.nix` | Home Manager, nixpkgs-unstable |
| `~/.bashrc` | `home.nix` → `shell/` | Home Manager; sources `shell/startup.sh` |
| Config files | `files/<tool>/` | Linked into `$HOME` by Home Manager, pointing at this checkout |
| Agent instructions and skills | `agent-config/` | Linked by Home Manager for Claude, Codex, OpenCode, Maple |
| kubectl, helm, k9s, kubie, opentofu, aws, gcloud, lazydocker | `flake.nix` | `cloud` devShell |
| Brave, Ghostty, VSCodium, Tailscale | `repos/`, `bootstrap.sh` | Vendor RPM repos and COPRs |
| Bitwarden, Discord, Proton Mail, Signal | `bootstrap.sh` | Pinned vendor downloads, checksum (and signature where published) verified |
| Telegram, Spotify, Gear Lever | `bootstrap.sh` | User Flathub |
| System76 drivers and power | `bootstrap.sh` | COPR, only on System76 hardware |

`bootstrap.sh` also removes Fedora KDE defaults I don't use (KMail/Kontact/Akonadi,
games, niche KDE apps, Discover, Plasma Welcome, Firefox) and makes Ghostty the
Plasma terminal (Ctrl+Alt+T).

Config links point into the checkout, not the Nix store, so editing a file in
`files/` takes effect right away. Keep the checkout where it is.

## Everyday use

The `dotfiles` alias runs the `justfile` from anywhere:

```bash
dotfiles switch      # apply home.nix changes
dotfiles update      # dnf, Flatpaks, then bump flake.lock and switch
dotfiles bootstrap   # rerun the Fedora setup (safe to repeat)
dotfiles check       # shellcheck, nixfmt, nix flake check
cloud                # shell with the cloud/k8s tools
```

Roll back a bad switch with `home-manager generations` and run the older
generation's `activate`.

### Adding things

- **CLI tool:** add it to `home.packages` in `home.nix`, then `dotfiles switch`.
- **Config file:** put it under `files/<tool>/` in its home-relative path, add
  `<tool>` to `tools` in `home.nix` if it's new, then `dotfiles switch`.
- **GUI app or system service:** add it to `bootstrap.sh` (RPM, Flatpak, or a
  pinned download with checksum and signature checks).
- **Pinned app update:** bump the version and hash at the top of `bootstrap.sh`
  (Proton: copy from its `version.json`), then `dotfiles bootstrap`.

## Local settings and secrets

- Machine env overrides: `~/.config/bash/variables.sh` (template in
  [examples/local-variables.sh](examples/local-variables.sh)), mode `0600`.
- Git identity/signing: `~/.gitconfig_local`. SSH hosts: `~/.ssh/config.local`.
- Bitwarden holds SSH keys; Bash uses `~/.bitwarden-ssh-agent.sock` when
  `SSH_AUTH_SOCK` is unset.
- Moving keys between machines: [docs/secrets.md](docs/secrets.md).

## Other bits

- `tailscale-exit-node` picks a random online US Mullvad exit node via Tailscale
  (needs a connected client with the Mullvad add-on).
- Shared agent config for remote nodes: [docs/agent-config.md](docs/agent-config.md).
- Execution-node tooling: [docs/cargo-metrics.md](docs/cargo-metrics.md),
  [docs/node-build-metrics.md](docs/node-build-metrics.md), `scripts/node-cleanup.py`.
