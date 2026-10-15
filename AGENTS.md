# Dotfiles installer

## Scope and ownership

- Target x86_64 Arch Linux and Manjaro with Bash 5+. Do not run provisioning on
  macOS. Leave the existing desktop, login, and networking settings alone.
- `install.sh` is the downloadable bootstrap; `bin/dotfiles` is the local entry
  point. Keep bootstrap logic small and machine setup in focused modules.
- `modules/<tool>.conf` describes a tool's group and package names as data, not
  executable shell. Custom setup belongs in `modules/<tool>.sh`.
- `stow/<tool>/` holds home-shaped configuration for that tool. Preserve the
  Kestrel appearance and the distinction between standalone scripts and
  interactive functions that affect the caller's shell.
- Bash deploys only `~/.bashrc`. Its loader sources helpers from repo `shell/`,
  never home-level helper symlinks. Optional machine-local shell overrides live
  in ignored `local/bash/`; do not read or migrate real credentials automatically.
- Default groups are core, AI, and desktop. Cloud/container, Bitcoin, and
  hardware-security groups are optional. Project toolchains belong in project
  Nix environments, not global Rustup/NVM installations.
- Prefer official repository packages over AUR and upstream installers for the
  same application. Bitwarden, OpenCode V2, and Nix use repository packages.
  Keep the OpenCode V2 guard; do not freeze one package during a partial upgrade.
  Nix daemon configuration is explicit; never mix upstream and repository Nix.

## Safety

- Run as the normal user; use narrowly scoped privilege escalation only where
  required. AUR builds must not run as root. No unattended upgrades.
- Refuse unmanaged destination conflicts, including dangling symlinks and
  conflicting parent paths. Never use Stow adoption, force replacement, or
  automatic deletion. Explain manual conflict resolution instead.
- Updates must verify repository identity and refuse dirty/diverged checkouts.
  Do not reset, stash, or discard user work automatically.
- No automatic Docker-group membership, autologin, wallet/key import, hardware
  provisioning, or changes to networking services.
- Keep API keys, authentication stores, private keys, wallet data, and machine
  exports out of Git and AI-readable checkouts. Non-secret shell environment
  overrides belong in ignored `local/bash/variables.sh`; prefer credential
  injection for API access. Git overrides remain in `~/.gitconfig_local`.
- Log meaningful installer phases and failures, never environment/credential
  values. Print next steps only after successful runs, with dry-runs clearly
  marked as plans. Do not emit installer-style progress logs during shell startup.
- Do not modify live nono profiles/packages or execute bootstrap/setup scripts
  merely to validate syntax. Source-controlled profiles are configuration data.
- Pin and verify standalone upstream artifacts. Treat AUR PKGBUILDs as executable
  third-party code requiring review, not trusted data.

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
- Pages publishes the standalone bootstrap only from `master`. Migration PRs
  must not deploy or merge automatically. Search for a PR template before opening
  a PR and include verified checks plus remaining Linux/Manjaro acceptance work.
