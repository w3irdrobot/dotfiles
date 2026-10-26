# Protected Fedora upgrades

Before a real `install`, `update system`, or `update all` package transaction,
dotfiles takes a read-only snapshot of a Btrfs root. If snapshot preparation
fails, the package transaction does not start. Non-Btrfs roots log that snapshots
are unavailable and continue without this protection.

The bootstrap's narrow Git/CA prerequisite installation occurs before the
checkout's snapshot machinery is available and is not covered by it.

## Checks and snapshots

For a Btrfs root:

- `/` must be a subvolume below the filesystem top level.
- `findmnt`, `btrfs`, and `df` must be available; `rpm --verifydb` must pass.
- At least 2 GiB must be free on `/`, plus 256 MiB on `/boot` and 64 MiB on
  `/efi` or `/boot/efi` when present.

DNF owns transaction locking. Never delete lockfiles to bypass a concurrent or
interrupted transaction. Package availability and selected-source metadata are
checked before the snapshot; RPM installation still requires interactive review.

Snapshots live outside the root subvolume so they survive a root rollback.
An existing, separately mounted `/.snapshots` subvolume on the same device is
reused. Otherwise setup temporarily mounts the Btrfs top level and reuses
`@.snapshots` or creates/reuses `@snapshots`. A snapshot directory nested inside
the root is not used for rollback protection. The root name itself is discovered,
not assumed to be Arch's `@`; Fedora commonly uses `root`.

The last five `dotfiles-*` snapshots are retained. Set `DOTFILES_SNAPSHOT_KEEP`
to a positive integer to change retention. Only this installer's named snapshots
are pruned. This is not a backup against disk failure.

State is recorded under
`~/.local/state/dotfiles/upgrades/<snapshot>/` (or `XDG_STATE_HOME`):

- `packages-before.txt`: RPM names and epoch/version/release/architecture.
- `snapshot.txt`: device and root/snapshot subvolume paths.
- `rollback.txt`: machine-specific live-media root recovery instructions.

One snapshot covers the full DNF upgrade and the following selected-package
install. Either transaction can be cancelled or fail independently; the snapshot
remains available. `rpm --verifydb` is checked afterward. Changes to `kernel*`,
`linux-firmware`, `dracut`, `systemd`, `grub2*`, `shim*`, `akmod*`, `kmod*`, or
`nvidia*` print a reboot warning when a pre-upgrade inventory is available.

Transactions use DNF5's `cacheonly=metadata`: checked metadata stays cached while
RPM payloads can still download. Fully offline `--cacheonly` mode would not work
for uncached packages on a fresh machine. Root snapshots also exclude separate
or nested subvolumes such as `/home` and `/nix`.

## Root rollback and boot recovery

Read the generated `rollback.txt` for the exact device/subvolumes. Generally:

1. Boot Fedora live media and open any LUKS container.
2. Mount the Btrfs top level with `mount -o subvolid=5 <device> /mnt`.
3. Rename the broken root, for example `root` to `root.broken-<snapshot>`.
4. Snapshot the read-only pre-upgrade snapshot back to the original root name.
5. Reconcile boot artifacts before rebooting when `/boot` or EFI is separate.

If fstab or the bootloader pins a `subvolid` instead of a subvolume name, update
that id after recreating the root.

**Fedora normally has separate `/boot` and EFI partitions.** A root snapshot
does not roll back their kernels, initramfs, BLS entries, bootloader, or firmware
boot entries. Keep a bootable Fedora USB and a separate boot backup. The
generated notes warn about these mounts but do not back them up automatically.

After restoring root, mount the real root, boot, and EFI filesystems in the
rescue environment. Reconcile installed kernel RPMs with `/boot` and
`/usr/lib/modules`; Fedora's kernel package scripts and `dracut` must produce
matching boot artifacts. An RPM database rollback alone is not a boot recovery.

For UEFI/Secure Boot, use Fedora's documented signed GRUB/shim package recovery.
Do not copy the former Manjaro `grub-install` procedure or overwrite the EFI stub
with a generated configuration. Fedora's generated GRUB config belongs at
`/boot/grub2/grub.cfg`. See [Fedora GRUB2 guidance](https://docs.fedoraproject.org/en-US/quick-docs/grub2-bootloader/).
Recovery remains unverified until rehearsed against the target's partitioning.
