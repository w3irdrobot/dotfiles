#!/usr/bin/env bash

set -euo pipefail
IFS=$'\n\t'

# Script initialization
SCRIPT_DIR=$(cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd)
DOTFILES_DIR=$(realpath "$SCRIPT_DIR/..")
LOG_FILE="$DOTFILES_DIR/setup.log"

# Logging functions
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $*" | tee -a "$LOG_FILE" >&2
}

# Error handler
error_handler() {
    local line_num=$1
    local error_code=$2
    log_error "Error occurred in script at line: ${line_num}, error code: ${error_code}"
}

trap 'error_handler ${LINENO} $?' ERR

# Check if running as root
if [[ $EUID -eq 0 ]]; then
    log_error "This script should not be run as root"
    exit 1
fi

# Create log file
touch "$LOG_FILE"
log "Starting setup script"

# Display section header
display_header() {
    log "Starting: $1"
    echo ""
    echo "###################################################"
    echo "###################################################"
    echo "## Installing and configuring $1"
    echo "###################################################"
    echo "###################################################"
}

if [[ -f "$DOTFILES_DIR/.last_run" ]]; then
    log "Last run: $(stat -c %y "$DOTFILES_DIR/.last_run")"
else
    log "First run detected"
fi

# Network setup
setup_network() {
    display_header "network tools"
    log "Installing curl"
    sudo pacman --needed -S curl

    display_header "tailscale"
    # Ensure tailscale is installed and configured
    if ! pacman -Qs --quiet tailscale >/dev/null; then
        log "Installing tailscale"
        sudo pacman -S tailscale
        log_error "Tailscale has been installed. Set it up manually to continue"
        log_error "Run: sudo tailscale up"
        exit 1
    elif ! systemctl is-active --quiet tailscaled; then
        log_error "Tailscale is installed but not running"
        log_error "Run: sudo tailscale up"
        exit 2
    elif [[ $(curl --silent ipinfo.io | jq -r .region) == "Ohio" ]]; then
        log_error "Tailscale is running but there is no exit node"
        log_error "Set an exit node before continuing"
        exit 3
    fi
    log "Network setup completed successfully"
}

# Install development tools
install_dev_tools() {
    display_header "basic build tools"
    log "Installing development tools"
    sudo pacman --needed -S \
        archlinux-contrib \
        base-devel \
        bash-completion \
        bat \
        bind \
        clang \
        diff-so-fancy \
        fakeroot \
        fzf \
        git \
        gnupg \
        go-yq \
        jq \
        just \
        pacman-contrib \
        starship \
        tree \
        vim \
        wget \
        xclip \
        zoxide
    log "Development tools installation completed"
}

# Setup dotfiles and configuration
setup_dotfiles() {
    display_header "dotfiles"
    log "Setting up dotfiles and configuration"

    MACHINE_EXPORT=${MACHINE_EXPORT:-''}
    if [[ ! -f "$DOTFILES_DIR/.last_run" ]] && [[ -d "$MACHINE_EXPORT" ]]; then
        log "First run detected with available machine export. Importing..."
        ./bin/import_for_new_machine.sh "$MACHINE_EXPORT"
    fi

    # Create necessary directories
    log "Creating required directories"
    mkdir -p "$HOME/.local/bin" "$HOME/.local/share/bash-completion/completions"

    # Link configuration files
    log "Linking configuration files"
    local config_files=(
        ".bash_profile"
        ".bashrc"
        ".gitconfig"
        ".gitignore_global"
        ".tmux.conf"
        ".vimrc"
    )

    for file in "${config_files[@]}"; do
        if [[ -f "$DOTFILES_DIR/$file" ]]; then
            ln -sf "$DOTFILES_DIR/$file" "$HOME/$file"
            log "Linked $file"
        else
            log_error "Config file $file not found in $DOTFILES_DIR"
        fi
    done

    log "Dotfiles setup completed"
}

# Install development tools and languages
install_dev_languages() {
    display_header "development languages and tools"
    log "Installing development languages and tools"

    # Install fonts
    log "Installing fonts"
    sudo pacman --needed -S ttf-firacode-nerd

    # Install Rust and tools
    log "Installing Rust and related tools"
    sudo pacman --needed -S rustup
    rustup toolchain install stable
    rustup default stable
    sudo pacman --needed -S \
        cargo-binstall \
        cargo-generate \
        cargo-outdated \
        sqlx-cli

    # Install AUR helper if not present
    if ! hash paru 2>/dev/null; then
        display_header "paru"
        log "Installing paru AUR helper"
        (
            git clone https://aur.archlinux.org/paru.git
            cd paru || exit
            makepkg -si
        )
    fi

    # Install additional development tools
    sudo paru --needed -S \
        httpie \
        python-pip-system-certs \
        openssh \
        hugo \
        nodejs-lts-iron \
        npm \
        go \
        gopls \
        delve

    # Enable services
    log "Enabling ssh-agent service"
    systemctl --user enable ssh-agent.service

    log "Development languages and tools installation completed"
}

# Configure SSH settings and permissions
setup_ssh() {
    display_header "ssh configuration"
    log "Setting up SSH configuration"

    # Check for SSH config
    if [[ ! -f $HOME/.ssh/config ]]; then
        log_error "Missing SSH config file. Please copy it before continuing"
        exit 4
    fi

    # Set SSH directory permissions
    log "Setting SSH directory permissions"
    chmod 700 "$HOME/.ssh"

    # Set file permissions for SSH files
    local ssh_files=(
        "authorized_keys"
        "config"
        "known_hosts"
    )

    for file in "${ssh_files[@]}"; do
        if [[ -f "$HOME/.ssh/$file" ]]; then
            chmod 600 "$HOME/.ssh/$file"
            log "Set permissions for $file"
        fi
    done

    # Handle SSH keys
    if [[ -f "$HOME/.ssh/id_ed25519" ]]; then
        chmod 600 "$HOME"/.ssh/id_*
        log "Set permissions for SSH keys"
    fi

    if [[ -f "$HOME/.ssh/id_ed25519.pub" ]]; then
        chmod 600 "$HOME"/.ssh/id_*.pub
        log "Set permissions for SSH public keys"
    fi

    log "SSH configuration completed"
}

# Setup Docker and related tools
setup_docker() {
    display_header "docker and friends"
    log "Setting up Docker and related tools"

    # Install Docker packages
    log "Installing Docker packages"
    if ! paru --needed -S docker docker-buildx docker-compose lazydocker; then
        log_error "Failed to install Docker packages"
        return 1
    fi

    # Enable and start Docker socket service
    log "Enabling Docker socket service"
    if ! sudo systemctl enable docker.socket; then
        log_error "Failed to enable Docker socket service"
        return 1
    fi

    log "Starting Docker socket service"
    if ! sudo systemctl start docker.socket; then
        log_error "Failed to start Docker socket service"
        return 1
    fi

    # Add user to Docker group
    log "Adding user to Docker group"
    if ! sudo usermod -a -G docker "$USER"; then
        log_error "Failed to add user to Docker group"
        return 1
    fi

    log "Docker setup completed successfully"
}

# Setup VS Code and extensions
setup_vscode() {
    display_header "vs code"
    log "Setting up VS Code and extensions"

    # Install VS Code
    log "Installing VS Code"
    if ! paru --needed -S visual-studio-code-bin; then
        log_error "Failed to install VS Code"
        return 1
    fi

    # Create VS Code config directories
    log "Creating VS Code config directories"
    mkdir -p "$HOME/.config/Code/User"

    # Install VS Code extensions
    if [[ -f vscode_extensions.txt ]]; then
        log "Installing VS Code extensions"
        while read -r extension; do
            if [[ -n "$extension" ]]; then
                log "Installing extension: $extension"
                if ! code --install-extension "$extension"; then
                    log_error "Failed to install extension: $extension"
                fi
            fi
        done < <(sed '/^$/d' vscode_extensions.txt)
    else
        log_error "vscode_extensions.txt not found"
    fi

    # Link VS Code configuration files
    local vscode_files=(
        "vscode/snippets:$HOME/.config/Code/User/snippets"
        "vscode/keybindings.json:$HOME/.config/Code/User/keybindings.json"
        "vscode/settings.json:$HOME/.config/Code/User/settings.json"
    )

    for file_pair in "${vscode_files[@]}"; do
        local source="${file_pair%%:*}"
        local target="${file_pair#*:}"

        if [[ -f "$DOTFILES_DIR/$source" ]]; then
            ln -sf "$DOTFILES_DIR/$source" "$target"
            log "Linked $source to $target"
        else
            log_error "Config file $source not found in $DOTFILES_DIR"
        fi
    done

    log "VS Code setup completed"
}

# Setup Windsurf IDE
setup_windsurf() {
    display_header "windsurf"
    log "Setting up Windsurf IDE"

    # Install Windsurf
    log "Installing Windsurf"
    if ! paru --needed -S windsurf; then
        log_error "Failed to install Windsurf"
        return 1
    fi

    # Create Windsurf config directory
    log "Creating Windsurf config directory"
    mkdir -p "$HOME/.config/Windsurf/User"

    # Link Windsurf configuration files
    local windsurf_files=(
        "windsurf/snippets:$HOME/.config/Windsurf/User/snippets"
        "windsurf/keybindings.json:$HOME/.config/Windsurf/User/keybindings.json"
        "windsurf/settings.json:$HOME/.config/Windsurf/User/settings.json"
    )

    for file_pair in "${windsurf_files[@]}"; do
        local source="${file_pair%%:*}"
        local target="${file_pair#*:}"

        if [[ -f "$DOTFILES_DIR/$source" ]]; then
            ln -sf "$DOTFILES_DIR/$source" "$target"
            log "Linked $source to $target"
        else
            log_error "Config file $source not found in $DOTFILES_DIR"
        fi
    done

    log "Windsurf setup completed"
}

# Setup GTK theme
setup_gtk_theme() {
    display_header "gtk theme"
    log "Setting up GTK theme"

    if [[ -d "$HOME/.themes/Dracula" ]]; then
        log "Dracula theme found locally. Assuming it's installed already."
    else
        log "Downloading and installing Dracula theme"

        # Download theme
        if ! wget https://github.com/dracula/gtk/archive/master.zip; then
            log_error "Failed to download Dracula theme"
            return 1
        fi

        # Extract theme
        if ! unzip master.zip; then
            log_error "Failed to extract theme archive"
            rm -f master.zip
            return 1
        fi

        # Create theme directories
        log "Creating theme directories"
        mkdir -p "$HOME/.themes" "$HOME/.config/gtk-4.0"

        # Remove old theme if exists
        rm -rf "$HOME/.themes/Dracula"

        # Install theme
        log "Installing theme files"
        if ! mv gtk-master "$HOME/.themes/Dracula"; then
            log_error "Failed to move theme files"
            rm -f master.zip
            return 1
        fi

        # Copy assets
        if ! cp -r "$HOME/.themes/Dracula/assets" "$HOME/.config/assets" || \
           ! cp -r "$HOME/.themes/Dracula/assets" "$HOME/.config/gtk-4.0/assets" || \
           ! cp -r "$HOME/.themes/Dracula/gtk-4.0/"*.css "$HOME/.config/gtk-4.0/"; then
            log_error "Failed to copy theme assets"
            return 1
        fi

        # Cleanup
        log "Cleaning up temporary files"
        rm -f master.zip
    fi

    # Enable themes
    log "Enabling Dracula theme"
    if ! gsettings set org.gnome.desktop.interface gtk-theme "Dracula" || \
       ! gsettings set org.gnome.desktop.wm.preferences theme "Dracula"; then
        log_error "Failed to enable Dracula theme"
        return 1
    fi

    log "GTK theme setup completed"
}

# Setup Espressif IDF
setup_espressif_idf() {
    display_header "espressif idf"
    log "Setting up Espressif IDF"

    if [[ -d "$HOME/.esp" ]]; then
        log "Espressif IDF found locally. Assuming it's installed already."
    else
        # Install dependencies
        log "Installing Espressif IDF dependencies"
        if ! paru --needed -S git make flex bison gperf python-pip cmake ninja ccache; then
            log_error "Failed to install Espressif IDF dependencies"
            return 1
        fi

        # Create ESP directory
        log "Creating ESP directory"
        mkdir -p "$HOME/.esp"

        # Clone and install ESP-IDF
        log "Cloning ESP-IDF repository"
        (
            cd "$HOME/.esp" || return 1
            if ! git clone -b v5.4 --recursive https://github.com/espressif/esp-idf.git; then
                log_error "Failed to clone ESP-IDF repository"
                return 1
            fi

            cd esp-idf || return 1
            log "Installing ESP-IDF"
            if ! ./install.sh; then
                log_error "Failed to install ESP-IDF"
                return 1
            fi

            log "Adding user to uucp group"
            if ! sudo usermod -a -G uucp "$USER"; then
                log_error "Failed to add user to uucp group"
                return 1
            fi
        ) || return 1
    fi

    log "Espressif IDF setup completed"
}

# Setup Espressif Rust toolchain
setup_espressif_rust() {
    display_header "espressif rust toolchain"
    log "Setting up Espressif Rust toolchain"

    # Install dependencies
    log "Installing Rust toolchain dependencies"
    if ! paru --needed -S gcc pkgconf; then
        log_error "Failed to install Rust toolchain dependencies"
        return 1
    fi

    # Install Espressif tools
    log "Installing Espressif tools"
    if ! cargo binstall espup esp-generate; then
        log_error "Failed to install Espressif tools"
        return 1
    fi

    # Setup Espressif environment
    log "Setting up Espressif environment"
    mkdir -p "$HOME/.local/bin" "$HOME/.local/share/bash-completion/completions"

    if ! espup install --export-file "$HOME/.local/bin/export-esp.sh"; then
        log_error "Failed to install Espressif environment"
        return 1
    fi

    if ! espup completions bash > "$HOME/.local/share/bash-completion/completions/espup"; then
        log_error "Failed to install Espressif completions"
        return 1
    fi

    chmod +x "$HOME/.local/bin/export-esp.sh"

    log "Espressif Rust toolchain setup completed"
}

# Setup browsers
setup_browsers() {
    display_header "browsers"
    log "Setting up web browsers"

    log "Installing browsers"
    if ! paru --needed -S brave-browser chromium; then
        log_error "Failed to install browsers"
        return 1
    fi

    log "Browsers setup completed"
}

# Setup Signal messenger
setup_signal() {
    display_header "signal"
    log "Setting up Signal messenger"

    log "Installing Signal"
    if ! paru --needed -S signal-desktop; then
        log_error "Failed to install Signal"
        return 1
    fi

    log "Signal setup completed"
}

# Setup Tor
setup_tor() {
    display_header "tor"
    log "Setting up Tor"

    log "Installing Tor and Tor Browser"
    if ! paru --needed -S tor torbrowser-launcher; then
        log_error "Failed to install Tor"
        return 1
    fi

    log "Enabling and starting Tor service"
    if ! sudo systemctl enable tor.service || ! sudo systemctl start tor.service; then
        log_error "Failed to enable or start Tor service"
        return 1
    fi

    log "Tor setup completed"
}

# Setup Bitwarden
setup_bitwarden() {
    display_header "bitwarden"
    log "Setting up Bitwarden"

    log "Installing Bitwarden"
    if ! paru --needed -S bitwarden; then
        log_error "Failed to install Bitwarden"
        return 1
    fi

    log "Bitwarden setup completed"
}

# Setup project directories
setup_project_dirs() {
    display_header "project directories"
    log "Setting up project directories"

    log "Creating project directories"
    if ! mkdir -p "$HOME/projects/github.com/w3irdrobot"; then
        log_error "Failed to create project directories"
        return 1
    fi

    log "Project directories setup completed"
}

# Setup Kitty terminal
setup_kitty() {
    display_header "kitty"
    log "Setting up Kitty terminal"

    log "Installing Kitty"
    if ! paru --needed -S kitty; then
        log_error "Failed to install Kitty"
        return 1
    fi

    log "Setting up Kitty configuration"
    rm -rf "$HOME/.config/kitty"
    mkdir -p "$HOME/.config/kitty"
    if ! ln -sf "$DOTFILES_DIR/kitty/kitty.conf" "$HOME/.config/kitty/kitty.conf"; then
        log_error "Failed to link Kitty configuration"
        return 1
    fi

    if ! ln -sf "$DOTFILES_DIR/kitty/dracula.conf" "$HOME/.config/kitty/dracula.conf"; then
        log_error "Failed to link Kitty dracula theme"
        return 1
    fi

    if ! ln -sf "$DOTFILES_DIR/kitty/diff.conf" "$HOME/.config/kitty/diff.conf"; then
        log_error "Failed to link Kitty diff configuration"
        return 1
    fi

    log "Kitty setup completed"
}

# Setup Thunderbird
setup_thunderbird() {
    display_header "thunderbird"
    log "Setting up Thunderbird"

    log "Installing Thunderbird"
    if ! paru --needed -S thunderbird; then
        log_error "Failed to install Thunderbird"
        return 1
    fi

    log "Thunderbird setup completed"
}

# Setup FileZilla
setup_filezilla() {
    display_header "filezilla"
    log "Setting up FileZilla"

    log "Installing FileZilla"
    if ! paru --needed -S filezilla; then
        log_error "Failed to install FileZilla"
        return 1
    fi

    log "FileZilla setup completed"
}

# Setup Sparrow Wallet
setup_sparrow() {
    display_header "sparrow wallet"
    log "Setting up Sparrow Wallet"

    log "Importing GPG key"
    if ! gpg --recv-keys D4D0D3202FC06849A257B38DE94618334C674B40; then
        log_error "Failed to import GPG key for Sparrow Wallet"
        return 1
    fi

    log "Installing Sparrow Wallet"
    if ! paru --needed -S sparrow-wallet; then
        log_error "Failed to install Sparrow Wallet"
        return 1
    fi

    log "Sparrow Wallet setup completed"
}

# Setup YubiKey Manager
setup_yubikey() {
    display_header "yubikey manager"
    log "Setting up YubiKey Manager"

    log "Installing YubiKey Manager"
    if ! paru --needed -S yubikey-manager; then
        log_error "Failed to install YubiKey Manager"
        return 1
    fi

    log "Starting YubiKey services"
    if ! sudo systemctl start pcscd.service pcscd.socket; then
        log_error "Failed to start YubiKey services"
        return 1
    fi

    log "YubiKey Manager setup completed"
}

# Setup LazyGit
setup_lazygit() {
    display_header "lazygit"
    log "Setting up LazyGit"

    log "Installing LazyGit"
    if ! paru --needed -S lazygit; then
        log_error "Failed to install LazyGit"
        return 1
    fi

    log "Setting up LazyGit configuration"
    mkdir -p "$HOME/.config/lazygit"
    if ! ln -sf "$DOTFILES_DIR/lazygit.yaml" "$HOME/.config/lazygit/config.yml"; then
        log_error "Failed to link LazyGit configuration"
        return 1
    fi

    log "LazyGit setup completed"
}

# Setup GParted
setup_gparted() {
    display_header "gparted"
    log "Setting up GParted"

    log "Installing GParted"
    if ! paru --needed -S gparted; then
        log_error "Failed to install GParted"
        return 1
    fi

    log "GParted setup completed"
}

# Setup Standard Notes
setup_standard_notes() {
    display_header "standard notes"
    log "Setting up Standard Notes"

    log "Installing Standard Notes"
    if ! paru --needed -S standardnotes-bin; then
        log_error "Failed to install Standard Notes"
        return 1
    fi

    log "Standard Notes setup completed"
}

# Setup Discord
setup_discord() {
    display_header "discord"
    log "Setting up Discord"

    log "Installing Discord"
    if ! paru --needed -S discord; then
        log_error "Failed to install Discord"
        return 1
    fi

    log "Discord setup completed"
}

# Setup Telegram
setup_telegram() {
    display_header "telegram"
    log "Setting up Telegram"

    log "Installing Telegram"
    if ! paru --needed -S telegram-desktop; then
        log_error "Failed to install Telegram"
        return 1
    fi

    log "Telegram setup completed"
}

# Setup Newsflash
setup_newsflash() {
    display_header "newsflash"
    log "Setting up Newsflash"

    log "Installing Newsflash"
    if ! paru --needed -S newsflash; then
        log_error "Failed to install Newsflash"
        return 1
    fi

    log "Newsflash setup completed"
}


# Setup Restic
setup_restic() {
    display_header "restic"
    log "Setting up Restic"

    log "Installing Restic"
    if ! paru --needed -S restic; then
        log_error "Failed to install Restic"
        return 1
    fi

    log "Restic setup completed"
}

# Setup GNOME tools
setup_gnome_tools() {
    display_header "gnome tools"
    log "Setting up GNOME tools"

    log "Installing GNOME tools"
    if ! paru --needed -S gnome-contacts gnome-system-monitor gnome-weather; then
        log_error "Failed to install GNOME tools"
        return 1
    fi

    log "GNOME tools setup completed"
}

# Cleanup unwanted packages
cleanup_packages() {
    display_header "clean up"
    log "Cleaning up unwanted packages"

    # List of packages to remove
    local packages=(
        baobab
        deja-dup
        endeavour
        fragments
        gnome-boxes
        gnome-calendar
        gnome-chess
        gnome-clocks
        gnome-connections
        gnome-disk-utility
        gnome-logs
        gnome-maps
        gnome-mines
        gnome-music
        gnome-remote-desktop
        gnome-terminal
        gnome-text-editor
        gnome-tour
        gnome-user-docs
        gnome-user-share
        gthumb
        iagno
        lollypop
        malcontent
        networkmanager-openconnect
        openconnect
        orca
        quadrapassel
        seahorse
        simple-scan
        snapshot
        stoken
        timeshift
        timeshift-autosnap-manjaro
        yelp
    )

    # Check if any of these packages are installed
    if paru -Qs baobab >/dev/null; then
        log "Removing unwanted packages"
        if ! paru -Rs "${packages[@]}"; then
            log_error "Failed to remove unwanted packages"
            return 1
        fi
    else
        log "No unwanted packages found"
    fi

    log "Cleanup completed"
}

# Setup GNOME tweaks
setup_gnome_tweaks() {
    display_header "tweaking gnome"
    log "Setting up GNOME tweaks"

	paru -S --needed gnome-shell-extensions \
		gnome-shell-extension-gnome-ui-tune-git \
		gnome-shell-extension-legacy-theme-auto-switcher-git

    log "Disabling all GNOME extensions"
    if ! gnome-extensions list | xargs -n 1 gnome-extensions disable; then
        log_error "Failed to disable GNOME extensions"
        return 1
    fi

    log "Enabling specific GNOME extensions"
    while read -r extension; do
        log "Enabling extension: $extension"
        if ! gnome-extensions enable "$extension"; then
            log_error "Failed to enable extension: $extension"
            return 1
        fi
    done < "$DOTFILES_DIR/gnome_extensions.txt"

    log "GNOME tweaks setup completed"
}

# Setup package cache cleanup
setup_package_cache_cleanup() {
    display_header "package cache cleanup"
    log "Setting up package cache cleanup service"

    log "Enabling paccache timer service"
    if ! sudo systemctl enable paccache.timer; then
        log_error "Failed to enable paccache timer service"
        return 1
    fi

    log "Starting paccache timer service"
    if ! sudo systemctl start paccache.timer; then
        log_error "Failed to start paccache timer service"
        return 1
    fi

    log "Package cache cleanup setup completed"
}

# Setup Bluetooth service
setup_bluetooth() {
    display_header "bluetooth"
    log "Setting up Bluetooth service"

    log "Installing Bluetooth packages"
    if ! paru --needed -S bluez bluez-utils; then
        log_error "Failed to install Bluetooth packages"
        return 1
    fi

    log "Enabling Bluetooth service"
    if ! sudo systemctl enable bluetooth.service; then
        log_error "Failed to enable Bluetooth service"
        return 1
    fi

    log "Starting Bluetooth service"
    if ! sudo systemctl start bluetooth.service; then
        log_error "Failed to start Bluetooth service"
        return 1
    fi

    log "Bluetooth setup completed"
}

# Setup network configurations
setup_network_configs() {
    display_header "network configurations"
    log "Setting up network configurations"

    # Backup and modify nsswitch.conf
    log "Backing up nsswitch.conf"
    if ! sudo cp /etc/nsswitch.conf /etc/nsswitch.conf.bak; then
        log_error "Failed to backup nsswitch.conf"
        return 1
    fi

    log "Modifying nsswitch.conf"
    if ! sudo sed -i 's/mdns_minimal \[NOTFOUND=return\] //g' /etc/nsswitch.conf; then
        log_error "Failed to modify nsswitch.conf"
        # Try to restore backup
        sudo cp /etc/nsswitch.conf.bak /etc/nsswitch.conf
        return 1
    fi

    # Add hosts to /etc/hosts
    log "Adding hosts to /etc/hosts"
    if [[ ! -f "$DOTFILES_DIR/hosts.txt" ]]; then
        log_error "hosts.txt not found in $DOTFILES_DIR"
        return 1
    fi

    while IFS= read -r host || [[ -n "$host" ]]; do
        # Skip empty lines and comments
        [[ -z "$host" || "$host" =~ ^[[:space:]]*# ]] && continue

        log "Adding host: $host"
        if ! grep -q "$host" /etc/hosts; then
            if ! echo "$host" | sudo tee -a /etc/hosts >/dev/null; then
                log_error "Failed to add host: $host"
                return 1
            fi
        else
            log "Host already exists: $host"
        fi
    done < "$DOTFILES_DIR/hosts.txt"

    log "Network configurations completed"
}

setup_hyprland() {
    display_header "hyprland"
    log "Setting up hyprland"

    log "Installing hyprland"
    if ! paru --needed -S hyprland uwsm; then
        log_error "Failed to install hyprland"
        return 1
    fi
}

# Execute all setup functions
setup_network
install_dev_tools
setup_dotfiles
install_dev_languages
setup_ssh
setup_docker || exit 1
# setup_vscode || exit 1
setup_windsurf || exit 1
setup_gtk_theme || exit 1
# setup_espressif_idf || exit 1
# setup_espressif_rust || exit 1
setup_browsers || exit 1
setup_signal || exit 1
setup_tor || exit 1
setup_bitwarden || exit 1
setup_project_dirs || exit 1
setup_kitty || exit 1
setup_thunderbird || exit 1
setup_filezilla || exit 1
setup_sparrow || exit 1
setup_yubikey || exit 1
setup_lazygit || exit 1
setup_gparted || exit 1
setup_standard_notes || exit 1
setup_discord || exit 1
setup_telegram || exit 1
setup_gnome_tools || exit 1
cleanup_packages || exit 1
setup_gnome_tweaks || exit 1
setup_package_cache_cleanup || exit 1
setup_bluetooth || exit 1
setup_network_configs || exit 1
setup_restic || exit 1
setup_newsflash || exit 1
setup_hyprland || exit 1


# Record successful completion
log "Setup completed successfully"
touch "$DOTFILES_DIR/.last_run"
