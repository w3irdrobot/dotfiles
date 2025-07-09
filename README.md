# My Dotfiles

## New computer setup

<!-- TODO: Add new computer explanation -->

# Steps

1. Follow [the Arch install instructions](https://wiki.archlinux.org/title/Installation_guide#Pre-installation) setting up the working environment.
1. Partition the disk using `fdisk`.
    a. The plan is to have a partition map like the following:

    ```
    /boot   1GB               fat32   Unencrypted boot partition
    [SWAP]  4GB               swap    Encrypted swap partition
    /       Everything else   ext4    LUKS encrypted partition
    ```

    b. The needed fdisk session would look like this:


    ```
    # fdisk /dev/vda
    Command: g

    Command: n
    Partition number: 1
    First sector: <Enter>
    Last sector: +1G

    Command: n
    Partition number: 2
    First sector: <Enter>
    Last sector: +4G
    Command: t
    Partition number: 2
    Partition type: swap

    Command: n
    Partition number: 3
    First sector: <Enter>
    Last sector: <Enter>

    Command: w
    ```


1. Setup encryption on the root partition and format and mount it.

```
cryptsetup -v luksFormat /dev/vda3
cryptsetup open /dev/vda3 root
mkfs.ext4 /dev/mapper/root
mount --mkdir /dev/mapper/root /mnt
```

1. Update `/etc/crypttab` to enable encrypted swap as described [here](https://wiki.archlinux.org/title/Dm-crypt/Swap_encryption#Without_suspend-to-disk_support).

1. Format the boot partition using `mkfs.fat` and mount it.

```
mkfs.fat -F 32 /dev/vda1
mount --mkdir /dev/vda1 /mnt/boot
```

1. Install the base system.

```
pacstrap -K /mnt base linux linux-firmware intel-ucode networkmanager
```

1. Generate the fstab file.

```
genfstab -U /mnt >> /mnt/etc/fstab
```

1. Update the fstab file ensuring the boot partition is mounted with `fmask=0077` and `dmask=0077`.

1. Chroot into the new system.

```
arch-chroot /mnt
```

1. Set the timezone.

```
ln -sf /usr/share/zoneinfo/US/Eastern /etc/localtime
```

1. Set hardware clock.

```
hwclock --systohc
```

1. Set locale by removing the octothorpe from the beginning of the line with `en_US.UTF-8 UTF-8` in `/etc/locale.gen`. Then run:

```
locale-gen
```

1. Set the hostname in `/etc/hostname`.

1. Configure mkinitcpio with [the needed hooks](https://wiki.archlinux.org/title/Dm-crypt/Encrypting_an_entire_system#LUKS_on_a_partition#Configuring_mkinitcpio). Then regenerate the initramfs with:

```
mkinitcpio -P
```

1. Set the root password.

```
passwd
```

1. Install systemd-boot.

```
bootctl install
```
