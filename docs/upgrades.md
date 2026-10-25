# Protected system upgrades

Before a full package transaction, the update path checks that the machine can
recover from a bad upgrade. On Btrfs roots it takes a read-only snapshot; when
that is not possible it refuses the transaction instead of proceeding unprotected.

## What is checked

For every real `install`, `update system`, or `update all` package transaction:

- `/` must be a Btrfs subvolume mounted below the filesystem top level.
- Btrfs tooling (`findmnt`, `btrfs`, `df`) must be available.
- `/var/lib/pacman/db.lck` must not exist.
- `pacman -Dk` must pass before the transaction and is checked again afterward.
- At least 2 GiB must be free on `/`, plus 256 MiB on `/boot` and 64 MiB on
  `/efi` or `/boot/efi` when those are separate mounts.

Non-Btrfs roots skip the snapshot with a log message and otherwise continue.

## Snapshots

The snapshot is placed outside the root subvolume so it survives a root rollback:

- If `/.snapshots` is already a separate Btrfs subvolume on the same device, it is
  used directly.
- Otherwise the Btrfs top level is mounted temporarily and an existing
  `@.snapshots` subvolume or `@snapshots` is used for `dotfiles-<timestamp>`
  snapshots.
- A `/.snapshots` that is nested inside the root subvolume is ignored because it
  would move when the root is renamed during rollback.

The last five snapshots are kept by default. Set `DOTFILES_SNAPSHOT_KEEP` to a
positive integer to change that. Only snapshots named `dotfiles-*` are pruned.

Before the transaction, the current package selection is written under
`${XDG_STATE_HOME:-~/.local/state}/dotfiles/upgrades/<snapshot>/`:

- `packages-before.txt`
- `foreign-before.txt`
- `snapshot.txt`
- `rollback.txt`

After the transaction, boot-critical package changes (`linux*`, `linux-firmware`,
`mkinitcpio`, `systemd`, `grub`, `refind`, `nvidia*`) cause a reboot warning.

## Rollback

`rollback.txt` contains the exact device and subvolume paths for the current
machine. The general procedure is:

1. Boot live Arch/Manjaro media and open any LUKS container.
2. Mount the Btrfs top level with `mount -o subvolid=5 <device> /mnt`.
3. Rename the broken root subvolume, for example `@` to `@.broken-<snapshot>`.
4. Snapshot the read-only pre-upgrade snapshot back to the root name.
5. If `/boot` or the EFI system partition is separate, restore it or reinstall
   the kernel from a chroot before rebooting.

If `/etc/fstab` or the bootloader pins a `subvolid` instead of a subvolume name,
update that id after recreating the root subvolume.

## Rebuilding the bootloader

A root rollback restores `/boot` but not the ESP. If GRUB's EFI files, Secure Boot
shim, or firmware boot entry are broken, rebuild the bootloader from live media
after restoring the root:

```bash
# UEFI. Replace ROOT and ESP with the installed partition devices; mount the
# root with the correct subvol= option first if it is not the default.
ROOT=/dev/nvme0n1p2
ESP=/dev/nvme0n1p1
mount "$ROOT" /mnt
mount "$ESP" /mnt/boot/efi
manjaro-chroot /mnt          # arch-chroot /mnt on Arch
grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=Manjaro
grub-mkconfig -o /boot/grub/grub.cfg
efibootmgr -v
```

On BIOS, use `grub-install --target=i386-pc /dev/nvme0n1` with the whole disk,
not a partition, then run `grub-mkconfig`. Reinstalling GRUB also makes the ESP
binary and the restored `/boot/grub` modules match again.

A root snapshot does not include separate `/boot`, `/efi`, or `/boot/efi`
partitions. A default Manjaro UEFI install keeps the kernel and initramfs in
`/boot` on the Btrfs root, so those are covered; the 300 MiB FAT32 ESP mounted at
`/boot/efi` is not. Keep a bootable USB and a current copy of the ESP when GRUB
or the bootloader packages are part of the upgrade.
