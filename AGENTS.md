# Dotfiles

## Layout and ownership

- Target x86_64 Fedora KDE Plasma (44+), regular RPM edition, not Atomic.
- Two layers, kept separate:
  - `bootstrap.sh` owns the system: vendor repos (`repos/`), RPMs, Flatpaks,
    pinned vendor apps, services, debloat, and Plasma tweaks. It must stay safe
    to rerun. `install.sh` only clones the repo and hands off to it.
  - `flake.nix` + `home.nix` own the user environment through Home Manager:
    CLI packages, fonts, `~/.bashrc`, and config links. Cloud/Kubernetes tools
    are a devShell (`cloud`), not installed packages.
- `files/<tool>/` is home-shaped config. `home.nix` links each file back to the
  checkout (out-of-store), so edits apply without a switch. Add a tool by adding
  its directory and listing it in `tools`.
- Prefer nixpkgs for CLI tools. GUI apps and anything needing system services
  stay on Fedora RPMs or Flatpak (Nix GUI apps break on graphics drivers here).
- Environment variables and aliases go in `home.sessionVariables` and
  `home.shellAliases` so they work in any shell. `shell/` holds only Bash-specific
  setup (prompt, functions), sourced by the Home Manager `.bashrc`. Keep the
  difference between standalone scripts and functions that must affect the
  caller's shell.
- Agent instructions and skills live in the separate `w3irdrobot/agentfiles`
  repository, which links itself. Nothing here depends on it.
- Project toolchains belong in project flakes, not global Rustup/NVM installs.

## Safety

- Run as the normal user; use `sudo` only where required. Keep DNF and Flatpak
  confirmation interactive. No unattended upgrades.
- Pin and verify standalone upstream artifacts: check both the checksum and the
  signature whenever the vendor publishes them. Third-party RPM repositories and
  COPRs are explicit trust decisions; never disable package signature checks.
  Don't use Flathub builds that the vendor doesn't publish when a vendor package
  exists.
- No automatic Docker-group membership, autologin, wallet/key import, or
  network logins. Bootstrap enables `tailscaled` and sets the operator;
  `tailscale up` stays manual.
- Keep API keys, authentication stores, private keys, wallet data, and machine
  exports out of Git. Machine environment overrides belong in
  `~/.config/bash/variables.sh`; Git overrides in `~/.gitconfig_local`. Exported
  values are inherited by AI processes; prefer credential injection.
- The tracked SSH config is generic defaults plus `Include ~/.ssh/config.local`
  only. Personal hosts travel via `dotfiles secrets export|import`.
- Do not run `bootstrap.sh` or `home-manager switch` just to validate changes.

## Checks

- `just check`: ShellCheck, nixfmt, and `nix flake check`. Build the user
  environment without activating it via
  `nix build .#homeConfigurations.$USER.activationPackage`.
- New untracked files are invisible to flakes; use `path:$PWD` or `git add -N`.
- Bash scripts use strict mode, optional `DEBUG=1` tracing, quoted expansions,
  arrays, focused helpers, and a thin `main`.

## Documentation

- Write developer-to-developer: direct and concrete, install command near the top
  of `README.md`. Keep it short; this repo is meant to stay small.
- Pages publishes `install.sh` only from `master`. Don't merge or deploy PRs
  automatically.
