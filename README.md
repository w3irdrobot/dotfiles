# Dotfiles

My Linux workstation setup: Bash, paru, repository-packaged Nix, and GNU Stow.
The primary target is **x86_64 Manjaro KDE Plasma on Wayland**. The installer also
supports x86_64 Arch Linux with Bash 5+; it leaves desktop, login, and networking
settings to you.

## Install

Download the bootstrap, review it, then run it as your normal user:

```bash
wget -O install.sh https://dotfiles.w3ird.tech/install.sh
less install.sh
bash install.sh
```

You need networking, sudo access, and a terminal for interactive package and AUR
review. Start with Manjaro's KDE edition rather than converting an XFCE install.
Manjaro can lag Arch: check dependency conflicts against your branch instead of
forcing a partial upgrade.

The bootstrap clones `master` over HTTPS, so a fresh machine needs no GitHub SSH
keys. It uses `~/projects/github.com/w3irdrobot/dotfiles`. Keep that checkout in
place: your configuration symlinks point into it. Existing destination files,
including a distribution's `.bashrc`, stop installation. Back them up and move
them yourself before rerunning; the installer does not adopt or overwrite them.
Links into this checkout can be reused; unrelated or dangling links and
conflicting parent paths stop setup too.
Custom `XDG_CONFIG_HOME` paths are rejected because configs deploy to `~/.config`.

To test another branch, download that branch's `install.sh` from GitHub, review
it, and pass `--ref BRANCH`. The public URL follows `master`.

## Choose what to install

The default groups are `core`, `ai`, and `desktop`. Cloud/container tools,
Bitcoin applications, and hardware-security tools are opt-in through `cloud`,
`bitcoin`, and `hardware`. Group selection replaces the defaults; explicit
modules add to the selected groups, including tools disabled by default.

From the checkout:

```bash
bash bin/dotfiles install --dry-run
bash bin/dotfiles install
bash bin/dotfiles link
bash bin/dotfiles install --groups core,ai,desktop,cloud
bash bin/dotfiles install --modules slack
```

`link` only prepares configuration links; it does not install packages. Repeat
your `--groups` and `--modules` choices on later commands: selections are not saved.
Successful install/link runs also provide a `~/.local/bin/dotfiles` launcher.

Dry-runs print a plan without applying it. Normal runs log phases and commands,
then print selection-specific next steps after success. `DEBUG=1` enables shell
tracing, which can expose data processed by external commands: avoid it around
credentials and redact traces before sharing them.

Packages come from official repositories first, then reviewed AUR builds through
paru. Bitwarden, OpenCode V2, and Nix use native repository packages. Brave uses
AUR's `brave-bin`. Nono is a checksum-pinned upstream binary. If repository paru
is unavailable, the installer builds the [frozen fallback](modules/paru-recipe/README.md)
with a Nix-supplied Rust toolchain and native libraries.

Nix supplies project development environments rather than global Rust/Node
toolchains. Its module enables the packaged daemon and user-level flakes support,
while preserving global settings. Existing upstream Nix installations require
manual resolution before setup. See [project environments](docs/nix-projects.md).

The Bitcoin group installs native Bitcoin Core and Sparrow. Review Tor, storage
paths, and service configuration before using the supplied configs; electrs
installation and wallet/key migration remain manual. Mullvad login, connection,
and daemon setup are also manual. Docker-group membership requires an explicit
`install --docker-group` and grants root-equivalent access.

## Desktop and hardware

Select **Plasma (Wayland)** at login and check that `echo "$XDG_SESSION_TYPE"`
prints `wayland`. TTY installation works too; an X11 session receives guidance
rather than an automatic switch. The KDE edition supplies Plasma, KWin,
PowerDevil, and login/session management. The desktop group adds KDE portal
support. Clipboard helpers prefer Wayland with an X11 fallback, and XWayland
apps can run without global Electron/Ozone flags.

Test portal file pickers, screen sharing, and an unlocked Secret Service provider
for apps such as Signal. Use KWallet if its installed version supports your setup,
or choose another provider. Wallet configuration and autostart are yours to manage.

On confirmed System76 hardware, `core` or `hardware` selects the driver, firmware,
power, and firmware-manager packages. DMI detection gates explicit
`--modules system76` too. Service activation, competing power backends, permissions,
and firmware updates need manual review. See [System76 setup](docs/system76.md).
Manjaro KDE/Wayland and Lemur Pro lemp14 hardware acceptance remain pending;
[the testing guide](docs/testing.md) records the verified Arch scope.

## Local settings and credentials

Bash deploys only `~/.bashrc`, which loads helpers directly from this checkout's
`shell/` directory. Keep your distribution's login profile; a custom profile
should source `~/.bashrc` for interactive Bash sessions.

Put machine-specific environment overrides in **`~/.config/bash/variables.sh`**.
Interactive Bash loads it last, after repository defaults, the Bitwarden helper,
and optional non-secret `local/bash/{init,aliases,functions}.sh` hooks. Use
[`examples/local-variables.sh`](examples/local-variables.sh) as a template, with
mode `0600` and ideally a `0700` parent directory. Setup never creates, reads, or
changes the private file. Move legacy `local/bash/variables.sh` settings yourself;
that file and old home-level helper files are no longer sourced.

Managed nono profiles deny `~/.config/bash`, but **exported secrets can still
reach AI child processes**. Prefer credential injection where available; Bitwarden
injection is not configured automatically. Bash suppresses xtrace/verbose output
while sourcing private overrides. Keep tracing and debug traps out of that file.
Unsandboxed tools are outside these file-access protections.

Keep Git identity/signing overrides in `~/.gitconfig_local` and imported SSH host
definitions in `~/.ssh/config.local`, not the symlinked repository configs. Sign
in to Bitwarden and enable its SSH agent manually. Bash defaults to
`~/.bitwarden-ssh-agent.sock` only when `SSH_AUTH_SOCK` is unset.

Keys, tokens, authentication stores, and wallet data stay outside Git. The
[`secrets_export` / `secrets_import` guide](docs/secrets.md) covers the separate
migration workflow and its SSH limitations. For disposable localhost certificates,
run `generate_local_cert` in an empty directory; it uses a private umask and
refuses existing outputs or symlinks.

## Updates

Symlinks follow your local checkout, not new GitHub commits. Update configs,
packages, or both explicitly:

```bash
bash bin/dotfiles update configs
bash bin/dotfiles update system
bash bin/dotfiles update all
```

Config updates verify the repository origin and require a clean, non-diverged
checkout before fast-forwarding and linking. They preserve local work and do not
install new dependencies. Rerun `install` with the same selections when a config
change adds a package or setup action, and restart affected apps afterward.

System updates perform a full native upgrade and AUR upgrade through paru.
Repository OpenCode must stay on major V2; incompatible versions stop the
transaction before package installation rather than freezing one package during
a partial upgrade. Unmanaged OpenCode executables on `PATH` are refused without
running them; aliases must resolve to native `/usr/bin/opencode`. Inspect and move
conflicts manually. AUR upgrades exclude paru so the frozen fallback cannot be
replaced by an unreviewed recipe. Native paru still
updates in the full repository transaction.

Nix itself updates through pacman/paru. Each project owns its `flake.lock` updates;
Nix garbage collection is separate maintenance. Nono version/digest changes need
a reviewed repository change and another install run. Resolve conflicting older
links manually rather than replacing unmanaged or dangling destinations.

### Sandboxed AI sessions

AI setup installs nono and pins its `nolabs-ai/opencode@0.4.0` runtime pack. The
pack supplies the base sandbox integration inherited by the custom profiles;
registry-managed conflicts stop setup instead of forcing replacement.

Run `ai` from a project directory. Its dev profile grants that directory;
`ai setup` grants the dotfiles checkout. Broad `$HOME` access conflicts with
credential protections. Sessions allowed to edit dotfiles can also change shell
code that later runs outside the sandbox: review those edits before opening a
new shell. Application, provider, and MCP sign-ins are separate manual steps.
Configure only the services you use.

## Repository layout

```text
install.sh             downloadable bootstrap
bin/dotfiles           local install/link/update command
lib/                   shared installer helpers
modules/<tool>.conf    group and package metadata (data, not shell)
modules/<tool>.sh      custom setup beyond package installation
stow/<tool>/           home-shaped configuration
shell/                 helpers sourced directly from this checkout
examples/              templates for machine-local settings
tests/                 disposable fixtures and VM drivers
```

## Validation and publishing

Run `just validate` for shell lint and fixture tests. See [test coverage](tests/README.md)
and [the Linux rehearsal guide](docs/testing.md) for what those checks establish
and what still needs a real machine. Provisioning is Linux-only; syntax checks
and disposable fixtures are safe on macOS.

The Pages workflow publishes the bootstrap from `master` only. The public
endpoint is `dotfiles.w3ird.tech`; Pages settings need that domain, valid DNS,
and HTTPS enforcement. A `CNAME` artifact alone does not configure an Actions
deployment. Moving to `install.w3ird.tech` would be a separate DNS/Pages change.
