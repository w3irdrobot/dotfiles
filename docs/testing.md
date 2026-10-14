# Installer rehearsal

Fixture tests and shell lint do not prove that a new workstation can install.
They exercise argument handling, conflict safety, repeated runs, and failure paths
without changing the developer's machine. Real package resolution, AUR builds,
the Nix daemon, and desktop integration require Linux validation.

## Disposable Linux VM

[Lima](https://lima-vm.io/docs/) supports an Arch Linux template. On an ARM Mac,
use an x86_64 QEMU guest for the initial x86_64-only installer, not Arch Linux ARM.
Foreign-architecture emulation is slow. Install Lima, QEMU, and additional guest
agents separately; the dotfiles installer must never install them on macOS.

The checked-in Lima 2.2.1 configuration pins the Arch image and its checksum,
uses QEMU x86_64 emulation, 6 GiB RAM, and a 40 GiB virtual disk. It disables host
mounts, personal public-key loading, agent forwarding, and containerd. Its guest
SSH connection uses localhost port 60022. Use a dedicated state directory:

```bash
export LIMA_HOME="$HOME/.lima-dotfiles-test"
# Create once; do not overwrite an existing instance.
limactl create --name=dotfiles-arch --yes tests/vm/arch-x86_64.yaml
limactl start --yes --timeout=30m dotfiles-arch
limactl shell dotfiles-arch
```

Tart cannot substitute for this x86_64 rehearsal on an ARM Mac: its guest
architecture must match the host. Rosetta translates applications inside ARM
guests, not an x86_64 kernel. See [Tart's architecture check](https://github.com/openai/tart/blob/main/Sources/tart/VM.swift).

Plain mode disables shared host mounts, dynamic port forwarding, and containerd.
Explicit static port forwards can remain; this configuration adds none beyond
the guest SSH transport. Clone the migration branch inside the guest; never use a writable host home mount as
the install target. Confirm the guest has a normal non-root user, sudo access,
networking, systemd, and sufficient disk space before installing. An Arch guest
tests Arch provisioning; it does **not** validate Manjaro package availability or
XFCE integration. Use a disposable Manjaro XFCE x86_64 VM or the eventual target
machine for that final rehearsal.

## Acceptance checklist

1. Read the bootstrap and module plan; confirm the checkout branch/commit.
2. Run the dry-run as a normal user. No files, network requests, or privileged
   commands should be triggered by a local dry-run.
3. Test an existing `.bashrc`, a dangling config symlink, and a conflicting parent
   path. Each must stop safely, leaving the original path untouched.
4. Resolve conflicts manually after backing up files. Run the core installation,
   then run it again. Verify repository-first package ownership and links remain
   correct; Bitwarden, OpenCode V2, and Nix must be native packages.
5. Open a fresh login shell. Verify Nix daemon access, `nix --version`, and flakes
   support; exercise a project's locked dev shell without global Rust/Node tools.
6. Install the default AI/desktop groups. Verify Ghostty, VSCodium, clipboard
   behavior under XFCE/X11, Bitwarden's SSH agent, and OpenCode/nono integration.
7. Interrupt a package install, then rerun. Confirm a partial checkout or Nix
   installation is diagnosed rather than overwritten or falsely marked complete.
   Test an existing upstream Nix install: the installer must not mix installation
   methods. Check that a repository OpenCode V1/V3 blocks upgrades before package
   installation rather than holding just OpenCode during a partial system upgrade.
8. Test config updates with clean, dirty, and diverged Git histories. Test adding
   a new config whose destination already exists. Updates must fail safely.
9. Run explicit system updates and verify no partial Arch repository upgrade.
10. Verify no changes to XFCE settings, autologin, networking, Docker-group
    membership, wallets, private keys, or local environment credentials.

Keep the VM until review is complete. Do not automatically destroy it or treat a
passing container test as equivalent to this rehearsal.

## Observed Arch rehearsal (2026-10-14)

The isolated `dotfiles-arch` guest booted as x86_64 Arch with systemd running,
passwordless guest sudo, and no shared host mounts. Published commit
`7fd2b09e2dde6166ab87138407351cba8960bc8c` was used for these checks:

- Public bootstrap dry-run passed without cloning or installing packages.
- Real bootstrap completed its official-repository Git prerequisite full upgrade
  and cloned the migration branch. It then exited 1 at the unmanaged `.bashrc`
  preflight, before workstation provisioning or config linking.
- The refused `.bashrc` still matched `/etc/skel/.bashrc`. It was manually moved
  to `~/.dotfiles-rehearsal-backup/bashrc` in the guest, preserving SHA256
  `959bc596166c9758fdd68836581f6b8f1d6fdb947d580bf24dce607998a077b8`.
- The subsequent full core installation dry-run passed. It resolved 47 official
  targets and `vscodium-bin` from AUR, but installed none of them or their links.

The VM-only `tests/vm/run-bootstrap.py --expect-conflict` driver was used for the
Git bootstrap confirmations. It verifies the isolated guest and bootstrap hash,
answers each of the two known pacman prompts once, and refuses other questions.
It is not a general installer approval driver. Noninteractive SSH and pre-fed
answers stopped at pacman prompts; those aborted attempts were not successes.

Full installation, the revised frozen paru build, native Nix daemon/flakes,
OpenCode V2, repeat runs, Manjaro, and XFCE GUI behavior remain unverified.
The guest's separate review-only VSCodium checkout matched audited AUR commit
`d04471d2fba90dc9fc16d52be8e6f957061b5ab3`; its binary-package VM test was
explicitly approved. This checkout has not built or installed the package.

References: [foreign architectures](https://lima-vm.io/docs/config/multi-arch/),
[plain mode](https://lima-vm.io/docs/config/plain/),
[Arch template](https://github.com/lima-vm/lima/blob/master/templates/archlinux.yaml).
