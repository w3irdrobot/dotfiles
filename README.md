# Dotfiles

My Linux workstation setup: Bash, DNF5, Fedora-packaged Nix, and GNU Stow.
The only supported target is **Fedora KDE Plasma Desktop 44, x86_64**, with Bash
5+ and Wayland. Use the regular RPM-based edition, not Kinoite/Atomic. Desktop,
login, SELinux, and networking settings stay yours to manage.

## Install

Run the bootstrap from a terminal as your normal user:

```bash
set -o pipefail
wget -O- https://dotfiles.w3ird.tech/install.sh | bash
```

You need `wget`, networking, sudo access, and a terminal for interactive RPM package and
signing-key confirmation. Start with Fedora's KDE edition. Test the live USB on
the laptop before installing. This Fedora port has local fixture coverage, not
yet a completed Fedora VM or Lemur Pro hardware rehearsal.

The public bootstrap is published from `master`; local edits are not published
automatically. Piping executes the downloaded code immediately. To inspect it
first, use `wget -O install.sh https://dotfiles.w3ird.tech/install.sh`, review the
file, then run `bash install.sh`.

To preview without applying changes, pass arguments through `bash -s --`:

```bash
wget -O- https://dotfiles.w3ird.tech/install.sh | bash -s -- --dry-run
```

Real installs read confirmation prompts from the terminal, not the download
pipe. Without a controlling terminal, only help/dry-run modes are supported.

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

For shared instructions and skills across Maple, Codex, Claude Code, and OpenCode
on local/remote nodes, see [agent configuration](docs/agent-config.md).
`agent-config/` owns that content; tool-specific paths link to it. The `ai` group
deploys shared links for all four tools during normal workstation setup. An agent
can follow [node setup](agent-config/SETUP.md) for standalone deployment without
workstation provisioning, credentials, or personal knowledge-base replication.

The workstation's [OpenCode configuration](docs/opencode.md) includes the MCP
setup, optional Proxmox prerequisites, and the boundary for machine-local values.

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
With the managed Bash config, open a new terminal and use `dotfiles` from any
directory. This is a per-user command, not a system-wide installation for other
users. Keep the checkout in place because the launcher and config links use it.

| Command | What it manages |
| --- | --- |
| `dotfiles install` | Update Fedora RPMs, install selected tools, run setup, and link configs |
| `dotfiles link` | Link selected configs and create/reuse the launcher; no package installation |
| `dotfiles update configs` | Safely fast-forward the checkout and relink configs |
| `dotfiles update system` | Update Fedora RPMs, selected tool setup, and installed user Flatpaks; no Git update |
| `dotfiles update all` | Update the checkout, Fedora RPMs, selected tool setup, user Flatpaks, and config links |
| `dotfiles check-updates` | Report installed/pinned/published Bitwarden and Discord RPM versions; no installation |
| `dotfiles secrets export` | Interactively export selected GPG/SSH/Sparrow material to an encrypted archive |
| `dotfiles secrets import` | Interactively restore an archive with the existing conflict protections |
| `dotfiles --help` | Show usage and options |

Add `--dry-run` to preview any lifecycle command. Secrets previews describe the
operation without reading keys, wallets, or archives; their selections are
interactive, not controlled by `--groups` or `--modules`. `--groups` replaces the default
groups; `--modules` adds explicit tools. Repeat these selections on subsequent
commands. `install --docker-group` is a separate, explicit root-equivalent
permission opt-in. There is no uninstall, automatic rollback, Fedora release
upgrade, or manual-application updater command.

Dry-runs print a plan without applying it. Normal runs log phases and commands,
then print selection-specific next steps after success. `DEBUG=1` enables shell
tracing, which can expose data processed by external commands: avoid it around
credentials and redact traces before sharing them. `dotfiles secrets` suppresses
DEBUG/xtrace/verbose tracing before dispatching the migration helper.

Packages come from Fedora first, with narrowly scoped vendor RPM repositories
for Brave/Mullvad and documented community RPM sources for Ghostty, VSCodium,
System76, and lazygit. Definitions in `repos/` require package signatures and
are added only for selected modules. Existing conflicting definitions stop setup.
OpenCode V2 and nono use pinned, checksum-verified upstream binaries. Arch,
pacman, paru, and AUR are no longer supported.

Bitwarden uses a pinned, checksum-verified native upstream RPM. Run
`dotfiles check-updates` for new desktop-release notices; system/all updates
also check when it is selected or installed. New pins require review, not an
automatic latest-version install. Sign-in and SSH-agent activation stay manual.

Discord uses a reviewed vendor RPM bootstrapper; its first launch downloads the
client separately. Signal uses the official signature-verified AppImage and then
its built-in updater. Telegram and Gear Lever (AppImage integration) use verified
user Flathub apps. System/all updates also update installed user Flatpaks;
system-wide Flatpak installations stay untouched. See [package details](docs/packages.md).

**Some selected modules currently require manual application installation**, most
notably Nerd Fonts and optional lazydocker, kubie, Google Cloud tools, and Sparrow.
Their configs still link; setup reports exactly which applications it did not
install. See [package sources and manual steps](docs/packages.md), including RPM
update responsibilities. This is not a claim that every previous app is automated.

Nix supplies project development environments rather than global Rust/Node
toolchains. Its module enables the packaged daemon and user-level flakes support,
while preserving global settings. Existing upstream Nix installations require
manual resolution before setup. See [project environments](docs/nix-projects.md).

The Bitcoin group installs Fedora Bitcoin Core; Sparrow remains manual. Review Tor, storage
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
`--modules system76` too. Install/system-update shows a service activation plan
and asks before enabling daemons or masking competing power backends. Plasma
PowerDevil stays intact; firmware flashing and privileged groups remain manual.
See [System76 setup](docs/system76.md).
Fedora KDE/Wayland and Lemur Pro lemp14 hardware acceptance remain pending;
[the testing guide](docs/testing.md) separates current checks from historical Arch results.

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
`~/.bitwarden-ssh-agent.sock` only when `SSH_AUTH_SOCK` is unset. When the agent
holds the private keys, keep only the `.pub` files in `~/.ssh`; `secrets_export`
archives those public halves instead of failing on missing private keys.

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

System updates refresh RPM metadata, verify every selected package is available,
take the Btrfs snapshot, then run interactive DNF upgrade
and install transactions against that cache. Missing packages and incompatible
OpenCode installations stop before either package transaction; there is no
arbitrary fallback. Unmanaged OpenCode executables on `PATH` are refused without
running them. The managed launcher is `~/.local/bin/opencode`, pointing to
`~/.local/share/dotfiles/opencode/2.1.4/opencode`; setup verifies its binary hash.

Nix itself updates through DNF. Each project owns its `flake.lock` updates;
Nix garbage collection is separate maintenance. OpenCode/nono version/digest changes need
a reviewed repository change and another install run. Do not use OpenCode's
self-updater to replace the pinned binary. Resolve conflicting older
links manually rather than replacing unmanaged or dangling destinations.

On Btrfs roots, system updates create a read-only pre-upgrade snapshot and refuse
the package transaction if one cannot be created. The last five `dotfiles-*`
snapshots are retained, package state is recorded under
`~/.local/state/dotfiles/upgrades/`, and boot-critical package changes print a
reboot warning. See [protected system upgrades](docs/upgrades.md) for checks and
live-media rollback steps. Separate `/boot`, `/efi`, and `/boot/efi` partitions
are not included in the root snapshot.

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
repos/                 selected, signature-checked RPM repository definitions
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
