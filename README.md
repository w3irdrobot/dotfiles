# Dotfiles

Linux workstation setup using Bash, paru, repository-packaged Nix,
and GNU Stow. The initial target is **x86_64 Arch Linux or Manjaro with XFCE**.
macOS and Pop!_OS/COSMIC provisioning have been removed; earlier setups remain in
Git history. The installer does not change your desktop session settings.

## Installation

Run as your normal user, not root. You need networking and sudo access. Package
installation and upstream/AUR code execution deserve review before running.
Package transactions remain interactive. Paru's initial PKGBUILD build requires
a controlling terminal and explicit approval. Manjaro can lag Arch repositories;
AUR package existence does not guarantee compatibility with your Manjaro branch.
Stop and investigate a dependency conflict rather than forcing a partial upgrade.

The published bootstrap remains at
`https://dotfiles.w3ird.tech/install.sh`. **Until this branch is reviewed and
merged, that URL still serves the old installer.** For branch testing, download
the migration version instead:

```bash
wget -O install.sh https://raw.githubusercontent.com/w3irdrobot/dotfiles/rewrite/arch-bash/install.sh
less install.sh
bash install.sh --ref rewrite/arch-bash
```

Do not pipe an unreviewed download directly into a root shell. The bootstrap
clones the public repository over HTTPS; a fresh machine does not need GitHub SSH
keys. A normal checkout lives at
`~/projects/github.com/w3irdrobot/dotfiles`. Keep that directory: your config
symlinks point into it. Do not delete or move it after installation.

## Layout

```text
install.sh             downloadable bootstrap
bin/dotfiles           local install/link/update command
lib/                   shared installer helpers
modules/<tool>.conf    tool group and package dependencies
modules/<tool>.sh      custom setup where packages are insufficient
stow/<tool>/           that tool's home-shaped configuration
shell/                 shell helpers sourced directly from this checkout
examples/              safe templates for machine-local settings
tests/                 disposable fixtures, not live-machine setup
```

Core workstation, AI tools, and desktop applications are the default groups.
OpenCode is the AI harness.
Cloud/container, Bitcoin, and hardware-security tools are opt-in groups. Nix
provides project environments; language toolchains and native build dependencies
should live in project flakes instead of being installed globally. AUR's own
build prerequisites are still system packages.

Package ownership prefers official Arch/Manjaro repositories, then suitable AUR
packages. Bitwarden, OpenCode, and Nix use native repository packages, not
Flatpak/npm/upstream installers. Nono is currently an explicit, checksum-verified
upstream exception. The Nix module enables its packaged daemon and supplies
user-level flakes configuration; it does not overwrite global Nix settings or
mix a pre-existing upstream installation with the repository package.
Brave is included in the desktop group via AUR's `brave-bin`, built/installed
through paru and then tracked by pacman. It is not an official-repository target.

From the checkout, use:

```bash
bash bin/dotfiles install --dry-run
bash bin/dotfiles install
bash bin/dotfiles link
# Group selection replaces the defaults; include core/ai/desktop if desired.
bash bin/dotfiles install --groups core,ai,desktop,cloud
```

Some applications retain their previous off-by-default choices. Explicit module
selection enables them without enabling an entire additional group:

```bash
bash bin/dotfiles install --modules slack
```

The optional Bitcoin group installs native Bitcoin Core and Sparrow. Bitcoin's
package hooks create standard system users/directories, but this installer does
not start its service or configure mounted storage. Electrs installation, Tor,
custom storage paths, and service management remain manual. Do not start those
configs until their prerequisites and storage settings have been reviewed.
Mullvad uses Extra;
logging in, connecting, and daemon/service setup remain manual.

## Conflicts and local settings

Existing destination files are **not adopted, overwritten, or deleted**. This
includes the `.bashrc` a distribution may create for you. Read the conflict
report, back up the conflicting file yourself, then rerun. Existing symlinks
belonging to this checkout may be reused; unrelated or dangling links must not
be replaced silently.

Only `~/.bashrc` is deployed for Bash. It resolves its symlink back to this repo
and loads `shell/startup.sh`, which sources init, variables, aliases, functions,
prompt, and the Bitwarden helper at top level. No `.init`, `.functions`,
`.variables`, `.aliases`,
`.prompt`, `.bash_profile`, or `.hushlogin` links are created in home. Your
distribution's existing login profile stays untouched; if you have a custom
login profile, make sure it loads `~/.bashrc` for interactive Bash sessions.
The installer requires unset/default `XDG_CONFIG_HOME` (`$HOME/.config`) and
rejects a custom path before changing the machine; Stow's home-shaped tree does
not relocate application configs.

Put machine-local shell settings in this checkout's ignored `local/bash/`
directory: `init.sh`, `variables.sh`, `aliases.sh`, and `functions.sh` are optional
overrides. **Non-secret** environment settings belong in
`local/bash/variables.sh`; see `examples/local-variables.sh` for a commented
template. Do not store API credentials there: the checkout is AI-readable and
writable, even when files are ignored by Git or mode `0600`. Prefer nono
credential injection; keep credential-manager storage outside AI filesystem
grants and do not export secrets globally into agent processes. Existing local
files are not inspected or migrated: move any credentials manually.
Local overrides run after the repo defaults, including Bitwarden.
The installer does not copy or read your old `~/.config/bash/` overrides: migrate
them manually if needed. Keep personal Git identity/signing overrides in
`~/.gitconfig_local`. Never commit keys, tokens, wallet data, or authentication
stores. Sign in to your password manager and configure SSH signing manually.
Wallet/key migration remains manual and separate from workstation installation.
Imported SSH host definitions belong in the machine-local `~/.ssh/config.local`,
not the symlinked repository config.
`secrets_export` follows that supported include and includes selected hosts'
explicit identity files. Other/nested includes are refused rather than silently
omitted; flatten and review those configs manually before backup. Review the
archive selection and verify a restore before wiping the source machine.
Bitwarden's native Linux SSH-agent socket is `~/.bitwarden-ssh-agent.sock`.
Enable the agent in the desktop app after signing in. An existing `SSH_AUTH_SOCK`
is preserved; use your local shell override if you want Bitwarden to replace it.
Its Secret Service provider is selected through package dependencies, without
forcing session-service configuration.

The installer logs each phase and command, then prints selection-specific next
steps after successful completion. Dry-runs are labelled as plans, not successful
installations. Normal progress logs do not dump your environment or credential
values. Optional `DEBUG=1` command tracing can expose data processed by external
commands; avoid it around credentials and redact traces before sharing them.

## Updates

When no native paru package is available, bootstrap uses the reviewed local
`modules/paru-recipe/PKGBUILD`, not the mutable AUR recipe. Its upstream source
and committed `Cargo.lock` are checksum-pinned: fetching uses `--locked`, building
uses `--frozen`, and lockfile changes stop the build. Rust/Cargo are build-only
Nix tools; paru links against native libraries. The fallback currently requires
libalpm 16. Supporting another ABI requires a reviewed source/lock pin change,
not an installation-time dependency update.
Installer AUR upgrades exclude paru; native repository upgrades still include
it. See [the frozen fallback notes](modules/paru-recipe/README.md) for the
explicitly reviewed helper replacement workflow.

Symlinks reflect your **local checkout**, not new GitHub commits. Config updates
must fetch a clean, non-diverged checkout and link any new configs; system updates
run a full pacman/AUR upgrade through paru. Neither action should run unattended
or discard your local changes. Update-all is an explicit combination, not an
automatic login hook.

```bash
bash bin/dotfiles update configs
bash bin/dotfiles update system
bash bin/dotfiles update all
```

Config-only updates do not install new dependency modules. Rerun `install` when a
config change introduces a new package or setup action. Use the same `--groups`
and `--modules` choices on subsequent runs; selections are explicit, not saved as
hidden machine state. Updating symlinked config content can still require
restarting the affected application.

AI setup installs and pins nono's `nolabs-ai/opencode@0.4.0` runtime pack.
Existing package/profile conflicts stop setup; the installer never uses force
to replace registry-managed assets.
This downloads nono's OpenCode integration pack, including the base sandbox
profile inherited by the repo's custom profiles. It is separate from installing
the nono executable and is required before using the sandboxed `ai` helper.
Run `ai` from a project directory. Its dev profile grants the current directory;
granting all of `$HOME` would conflict with Linux credential protections.
`ai setup` grants the dotfiles checkout, not the entire owner namespace. Both
setup and dev sessions that can edit dotfiles can change shell startup code that
will later run outside the sandbox. Treat those edits as trusted code and review
them before opening a new shell; sandboxing cannot remove that persistence risk.
Application, model-provider, and MCP sign-ins are separate personal authentication
steps, not installer failures. Configure only the services you actually use.

Nix's executable updates through pacman/paru; garbage collection remains an
explicit maintenance action. Each project's
`flake.lock` controls its dependency updates; see [project Nix environments](docs/nix-projects.md).
OpenCode stays on V2: repository versions outside major 2 stop installation or
system updates rather than being silently accepted. A newer patch/minor V2
release is allowed. A future V3 transition requires a deliberate policy change.

Nono is a pinned upstream binary, not an AUR package. Upgrade its
version/digest through a reviewed repo change, then rerun setup. If a changed
pin conflicts with an older managed link, inspect and resolve that link manually;
the installer must not silently replace an unmanaged or dangling destination.

## Validation

See the `justfile` for local lint/test recipes and
[the VM rehearsal guide](docs/testing.md) for actual Linux installation checks.
Fixture tests cannot establish AUR build success, Nix daemon operation, Manjaro
package availability, or desktop integration. Do not run operational installers
on macOS merely to test syntax.

The Pages workflow publishes only from `master`; migration pull requests do not
deploy. Moving the public endpoint to `install.w3ird.tech` requires a separate
DNS/Pages change. Nothing in this migration changes DNS automatically.
The repository's Pages settings must retain `dotfiles.w3ird.tech`, valid DNS,
and HTTPS enforcement; a `CNAME` artifact does not configure an Actions deployment.
