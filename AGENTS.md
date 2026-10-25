# Dotfiles installer

## Scope and ownership

- Target x86_64 Fedora KDE Plasma Desktop 44 with Bash 5+. Do not run provisioning on
  macOS. Leave the existing desktop, login, and networking settings alone.
- Primary desktop baseline: Fedora 44 KDE Plasma on Wayland; no Arch support.
  System76 packages are DMI-gated; service activation requires terminal
  confirmation. Firmware flashing and privileged groups remain manual.
- `install.sh` is the downloadable bootstrap; `bin/dotfiles` is the local entry
  point. Keep bootstrap logic small and machine setup in focused modules.
- `modules/<tool>.conf` describes a tool's group and package names as data, not
  executable shell. Custom setup belongs in `modules/<tool>.sh`.
- `stow/<tool>/` holds home-shaped configuration for that tool. Preserve the
  Kestrel appearance and the distinction between standalone scripts and
  interactive functions that affect the caller's shell.
- Bash deploys only `~/.bashrc`. Its loader sources helpers from repo `shell/`,
  never home-level helper symlinks. Optional machine-local shell overrides live
  in `~/.config/bash/variables.sh` for environment settings; optional non-secret
  init/alias/function hooks remain in ignored `local/bash/`. Never read or migrate
  real credentials automatically.
- Default groups are core, AI, and desktop. Cloud/container, Bitcoin, and
  hardware-security groups are optional. Project toolchains belong in project
  Nix environments, not global Rustup/NVM installations.
- Prefer Fedora repository packages, then documented vendor RPMs and selected
  COPRs. Explicitly report applications requiring manual installation.
  OpenCode V2 uses a pinned upstream binary until a verified Fedora 44 V2 RPM is
  available; Nix uses Fedora nix/nix-daemon. Keep OpenCode artifact/hash and PATH
  checks; never silently replace a conflicting executable.
  Nix daemon configuration is explicit; never mix upstream and repository Nix.
- Bitwarden uses the reviewed upstream RPM pin in `modules/bitwarden-release.json`.
  Check its SHA256 and RPM identity before protected installation; do not downgrade
  an equal/newer installed version. CLI release checks are notices, not auto-updates.

## Safety

- Run as the normal user; use narrowly scoped privilege escalation only where
  required. Keep DNF package and key confirmation interactive. No unattended upgrades.
- Refuse unmanaged destination conflicts, including dangling symlinks and
  conflicting parent paths. Never use Stow adoption, force replacement, or
  automatic deletion. Explain manual conflict resolution instead.
- Updates must verify repository identity and refuse dirty/diverged checkouts.
  Do not reset, stash, or discard user work automatically.
- No automatic Docker-group membership, autologin, wallet/key import, hardware
  provisioning, or changes to networking services.
- Keep API keys, authentication stores, private keys, wallet data, and machine
  exports out of Git and AI-readable checkouts. Machine environment overrides,
  secret or non-secret, belong in `~/.config/bash/variables.sh`, never in the
  checkout. Managed nono profiles deny `~/.config/bash`; exported values may
  still be inherited by AI processes. Prefer credential injection where available.
  Git overrides remain in `~/.gitconfig_local`.
- Log meaningful installer phases and failures, never environment/credential
  values. Print next steps only after successful runs, with dry-runs clearly
  marked as plans. Do not emit installer-style progress logs during shell startup.
- Do not modify live nono profiles/packages or execute bootstrap/setup scripts
  merely to validate syntax. Source-controlled profiles are configuration data.
- Pin and verify standalone upstream artifacts. Third-party RPM repositories and
  COPRs are explicit trust decisions; never disable package signature checks.

## Documentation

- Write developer-to-developer: direct, conversational, and concrete. Lead with
  the intended use and runnable examples; keep the install command near the top
  of `README.md`.
- Explain behavior and responsibility before constraints. State safety rules
  once near the relevant workflow, preserving their exact meaning.
- Link detailed contracts and dated validation evidence rather than repeating
  them. Keep current instructions separate from historical results and open work.

## Bash and verification

- Executable scripts use strict mode, optional `DEBUG=1` tracing, quoted
  expansions, arrays, focused helpers, and a thin `main`. Sourced libraries and
  interactive configs must not impose strict mode on their callers.
- Use Bash syntax checks, ShellCheck, and shfmt. Keep checks scoped to changed
  files; do not mask errors with blanket exclusions or `|| true`.
- Test idempotence, conflicts, argument validation, dry-run side effects,
  interrupted setup, and unsafe updates using disposable fixtures/mocks.
- Use the repository's `justfile` and CI recipes for checks. Record skipped
  checks and missing tools honestly; mocks do not validate real installation.
- Follow `docs/testing.md` for a separate Linux VM rehearsal. Do not install VM
  software, launch VMs, or change the host without approval.
- Pages publishes the standalone bootstrap only from `master`. PRs must not
  deploy or merge automatically. Search for a PR template before opening
  a PR and include verified checks plus remaining Fedora/Lemur Pro acceptance work.
