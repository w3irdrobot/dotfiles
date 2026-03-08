# Dotfiles

Cross-platform dotfiles managed with [chezmoi](https://www.chezmoi.io/).

## Quick Start

Bootstrap a new machine with a single command:

```bash
curl -fsSL https://dotfiles.w3ird.tech/install.sh | bash
```

Or if you prefer to inspect the script first:

```bash
curl -fsSL https://dotfiles.w3ird.tech/install.sh | less
# Then run it
curl -fsSL https://dotfiles.w3ird.tech/install.sh | bash
```

This will:
1. Detect your OS (macOS or Linux)
2. Install chezmoi
3. Clone this repo and apply all dotfiles
4. Install packages (Homebrew on macOS, yay/pacman on Arch Linux)
5. Configure system settings

## Manual Installation

If you prefer manual installation:

```bash
# Install chezmoi
sh -c "$(curl -fsLS get.chezmoi.io)" -- -b ~/.local/bin

# Initialize and apply dotfiles
chezmoi init --apply w3irdrobot
```

## What's Included

### Shell
- **Bash** with modern configuration
- **Starship** prompt (Dracula theme)
- **zoxide** for smart directory jumping
- **fzf** for fuzzy finding

### CLI Tools
- `bat` - better `cat`
- `eza` - better `ls`
- `fd` - better `find`
- `ripgrep` - better `grep`
- `delta` - better git diffs (side-by-side, syntax highlighting)
- `lazygit` - terminal UI for git

### Editors
- **Vim**
- **VSCodium** with extensions

### Development
- **Rust** (via rustup) with cargo tools
- **Docker** with lazydocker

### Terminal
- **Kitty** terminal emulator

### macOS-specific
- Homebrew packages via `Brewfile`
- System preferences (Finder, Dock, keyboard, trackpad, etc.)
- Dark mode enabled
- Modern Bash as default shell

### Linux-specific (Arch)
- Hyprland window manager with waybar, hypridle, hyprlock
- Bluetooth configuration
- Network configuration with Tor
- Auto-login and clamshell mode for laptops

## Directory Structure

```
.
├── .chezmoi.toml.tmpl      # chezmoi configuration
├── .chezmoiignore          # OS-specific file ignoring
├── .chezmoiscripts/        # Setup scripts (run by chezmoi)
│   ├── darwin/             # macOS-specific scripts
│   └── linux/              # Linux-specific scripts
├── .chezmoitemplates/      # Shared templates (VSCodium config)
├── Brewfile                # macOS Homebrew packages
├── install.sh              # Bootstrap script
├── system/                 # System-level configs (installed via scripts)
│   └── linux/
├── dot_*                   # Dotfiles (chezmoi naming convention)
├── dot_config/             # ~/.config/ contents
└── Library/                # macOS ~/Library/ contents
```

## Updating

To pull the latest changes and apply them:

```bash
chezmoi update
```

## Customization

### Local overrides

Create local configuration files that won't be tracked:
- `~/.config/bash/.variables` - Local environment variables
- `~/.config/bash/.aliases` - Local aliases
- `~/.config/bash/.functions` - Local functions
- `~/.gitconfig_local` - Local git configuration (e.g., work email)

### Editing dotfiles

```bash
# Edit a managed file
chezmoi edit ~/.bashrc

# See what would change
chezmoi diff

# Apply changes
chezmoi apply
```

## DNS Setup (for custom domain)

To host the install script at `dotfiles.w3ird.tech`:

1. Add a CNAME record: `dotfiles.w3ird.tech` → `w3irdrobot.github.io`
2. In GitHub repo settings → Pages:
   - Source: GitHub Actions
   - Custom domain: `dotfiles.w3ird.tech`
   - Enforce HTTPS: enabled

---

## Arch Linux Installation

For a fresh Arch Linux install with LUKS encryption, see the detailed steps below.

### Partitioning

```
/boot   1GB               fat32   Unencrypted boot partition
[SWAP]  4GB               swap    Encrypted swap partition
/       Everything else   ext4    LUKS encrypted partition
```

### Setup Steps

1. Follow [the Arch install instructions](https://wiki.archlinux.org/title/Installation_guide#Pre-installation)

2. Partition the disk using `fdisk`:
   ```
   fdisk /dev/vda
   g           # Create GPT table
   n, 1, +1G   # Boot partition
   n, 2, +4G   # Swap partition (type: swap)
   n, 3        # Root partition (rest of disk)
   w           # Write changes
   ```

3. Setup LUKS encryption:
   ```bash
   cryptsetup -v luksFormat /dev/vda3
   cryptsetup open /dev/vda3 root
   mkfs.ext4 /dev/mapper/root
   mount --mkdir /dev/mapper/root /mnt
   ```

4. Update `/etc/crypttab` to enable encrypted swap as described [here](https://wiki.archlinux.org/title/Dm-crypt/Swap_encryption#Without_suspend-to-disk_support).

5. Format and mount boot:
   ```bash
   mkfs.fat -F 32 /dev/vda1
   mount --mkdir /dev/vda1 /mnt/boot
   ```

6. Install base system:
   ```bash
   pacstrap -K /mnt base linux linux-firmware intel-ucode networkmanager
   ```

7. Generate fstab:
   ```bash
   genfstab -U /mnt >> /mnt/etc/fstab
   ```

8. Update the fstab file ensuring the boot partition is mounted with `fmask=0077` and `dmask=0077`.

9. Chroot and configure:
   ```bash
   arch-chroot /mnt
   ln -sf /usr/share/zoneinfo/US/Eastern /etc/localtime
   hwclock --systohc
   # Edit /etc/locale.gen, uncomment en_US.UTF-8
   locale-gen
   # Set hostname in /etc/hostname
   # Configure mkinitcpio with encrypt hook
   mkinitcpio -P
   passwd
   bootctl install
   ```

10. After reboot, run the dotfiles bootstrap:
    ```bash
    curl -fsSL https://dotfiles.w3ird.tech/install.sh | bash
    ```
