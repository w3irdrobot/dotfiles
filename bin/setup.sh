#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd)
DOTFILES_DIR=$(realpath "$SCRIPT_DIR/..")

function display_header() {
	echo ""
	echo "###################################################"
	echo "###################################################"
	echo "## Installing and configuring $1"
	echo "###################################################"
	echo "###################################################"
}

if [[ -f "$DOTFILES_DIR/.last_run" ]]
then
	echo "Last run: $(stat -c %y "$DOTFILES_DIR/.last_run")"
else
	echo "First run detected."
fi

display_header "tailscale"
sudo pacman --needed -S curl

# ensure tailscale is installed before doing anything else.
if ! pacman -Qs --quiet tailscale >/dev/null
then
	# install tailscale and exit so we can set it up manually
	sudo pacman -S tailscale
	echo "tailscale has been installed. set it up manually to continue"
	echo "run: sudo tailscale up"
	exit 1
elif ! systemctl is-active --quiet tailscaled
then
	echo "tailscale is installed but not running."
	echo "run: sudo tailscale up"
	exit 2
elif [[ $(curl --silent ipinfo.io | jq -r .region) == "Ohio" ]]
then
	echo "tailscale is running but there is no exit node"
	echo "set an exit node before continuing"
	exit 3
fi

display_header "basic build tools"
sudo pacman --needed -S \
	archlinux-contrib \
	base-devel \
	bash-completion \
	bat \
	bind \
	diff-so-fancy \
	fakeroot \
	fzf \
	git \
	gnupg \
	jq \
	just \
	pacman-contrib \
	starship \
	tree \
	vim \
	wget \
	xclip \
	zoxide

if [[ ! -f "$DOTFILES_DIR/.last_run" ]] && [[ -d "$MACHINE_EXPORT" ]]
then
	echo "First run detected with available machine export. Immporting..."
	./bin/import_for_new_machine.sh "$MACHINE_EXPORT"
fi

ln -sf "$DOTFILES_DIR/.bash_profile" "$HOME/.bash_profile"
ln -sf "$DOTFILES_DIR/.bashrc" "$HOME/.bashrc"
ln -sf "$DOTFILES_DIR/.gitconfig" "$HOME/.gitconfig"
ln -sf "$DOTFILES_DIR/.gitignore_global" "$HOME/.gitignore"
ln -sf "$DOTFILES_DIR/.tmux.conf" "$HOME/.tmux.conf"
ln -sf "$DOTFILES_DIR/.vimrc" "$HOME/.vimrc"

mkdir -p "$HOME/.local/bin" "$HOME/.local/share/bash-completion/completions"

display_header "fonts"
sudo pacman --needed -S ttf-firacode-nerd

display_header "rust and friends"
sudo pacman --needed -S rustup
rustup toolchain install stable
sudo pacman --needed -S \
    cargo-binstall \
    cargo-generate \
    cargo-outdated \
    sqlx-cli

if ! hash paru 2>/dev/null
then
	display_header "paru"
	(
		git clone https://aur.archlinux.org/paru.git
	 	cd paru || exit
	  	makepkg -si
	)
fi

display_header "httpie"
paru --needed -S httpie python-pip-system-certs

display_header "ssh"
paru --needed -S openssh
systemctl --user enable ssh-agent.service

display_header "hugo"
paru --needed -S hugo

display_header "nodejs and friends"
paru --needed -S nodejs-lts-iron npm

if [[ ! -f $HOME/.ssh/config ]]
then
	echo "missing ssh config. make sure to copy that over before continuing"
	exit 4
fi

chmod 700 "$HOME/.ssh"
[[ -f "$HOME/.ssh/authorized_keys" ]] && chmod 600 "$HOME/.ssh/authorized_keys"
[[ -f "$HOME/.ssh/config" ]] && chmod 600 "$HOME/.ssh/config"
[[ -f "$HOME/.ssh/known_hosts" ]] && chmod 600 "$HOME/.ssh/known_hosts"
[[ -f "$HOME/.ssh/id_ed25519" ]] && chmod 600 "$HOME"/.ssh/id_*
[[ -f "$HOME/.ssh/id_ed25519.pub" ]] && chmod 600 "$HOME"/.ssh/id_*.pub

display_header "docker and friends"
paru --needed -S docker docker-buildx docker-compose
# the socket service starts the daemon the first time the socket is accessed,
# aka the first time `docker` is invoked
sudo systemctl enable docker.socket
sudo systemctl start docker.socket
sudo usermod -a -G docker "$USER"

display_header "vs code"
paru --needed -S visual-studio-code-bin

while read -r extension
do
	code --install-extension "$extension"
done < <(sed '/^$/d' vscode_extensions.txt)

mkdir -p "$HOME/.config/Code/User"

ln -sf "$DOTFILES_DIR/vscode/snippets" "$HOME/.config/Code/User/snippets"
ln -sf "$DOTFILES_DIR/vscode/keybindings.json" "$HOME/.config/Code/User/keybindings.json"
ln -sf "$DOTFILES_DIR/vscode/settings.json" "$HOME/.config/Code/User/settings.json"

display_header "windsurf"
paru --needed -S windsurf

mkdir -p "$HOME/.config/Windsurf/User"

ln -sf "$DOTFILES_DIR/windsurf/snippets" "$HOME/.config/Windsurf/User/snippets"
ln -sf "$DOTFILES_DIR/windsurf/keybindings.json" "$HOME/.config/Windsurf/User/keybindings.json"
ln -sf "$DOTFILES_DIR/windsurf/settings.json" "$HOME/.config/Windsurf/User/settings.json"

display_header "gtk theme"
if [[ -d "$HOME/.themes/Dracula" ]]
then
	echo "Dracula theme found locally. Assuming it's installed already."
else
	# download and install the theme
	wget https://github.com/dracula/gtk/archive/master.zip
	unzip master.zip
	mkdir -p "$HOME/.themes" "$HOME/.config/gtk-4.0"
	rm -rf "$HOME/.themes/Dracula"
	mv gtk-master "$HOME/.themes/Dracula"
	cp -r "$HOME/.themes/Dracula/assets" "$HOME/.config/assets"
	cp -r "$HOME/.themes/Dracula/assets" "$HOME/.config/gtk-4.0/assets"
	cp -r "$HOME"/.themes/Dracula/gtk-4.0/*.css "$HOME/.config/gtk-4.0/"
	# cleanup
	rm master.zip
	# enable
	gsettings set org.gnome.desktop.interface gtk-theme "Dracula"
	gsettings set org.gnome.desktop.wm.preferences theme "Dracula"
fi

display_header "espressif idf"
if [[ -d "$HOME/.esp" ]]
then
	echo "Espressif IDF found locally. Assuming it's installed already."
else
	# from espressif idf docs
	# https://espressif-docs.readthedocs-hosted.com/projects/esp-idf/en/stable/get-started/linux-setup.html
	paru --needed -S git make flex bison gperf python-pip cmake ninja ccache
	mkdir "$HOME/.esp"
	(
		cd "$HOME/.esp"
		git clone -b v5.4 --recursive https://github.com/espressif/esp-idf.git
		cd esp-idf
		./install.sh
		sudo usermod -a -G uucp "$USER"
	)
fi

display_header "espressif rust toolchain"
paru --needed -S gcc pkgconf
cargo binstall espup esp-generate
espup install --export-file "$HOME/.local/bin/export-esp.sh"
espup completions bash > "$HOME/.local/share/bash-completion/completions/espup"
chmod +x "$HOME/.local/bin/export-esp.sh"

display_header "terminal file browser"
paru --needed -S yazi ffmpeg p7zip poppler fd ripgrep imagemagick

display_header "browsers"
paru --needed -S brave-browser chromium

display_header "signal"
paru --needed -S signal-desktop

display_header "tor"
paru --needed -S tor torbrowser-launcher
sudo systemctl enable tor.service
sudo systemctl start tor.service

display_header "bitwarden"
paru --needed -S bitwarden

display_header "project directories"
mkdir -p "$HOME/projects/github.com/w3irdrobot"

display_header "kitty"
paru --needed -S kitty
rm -rf "$HOME/.config/kitty"
mkdir -p "$HOME/.config/kitty"
ln -sf "$DOTFILES_DIR/kitty/kitty.conf" "$HOME/.config/kitty/kitty.conf"
ln -sf "$DOTFILES_DIR/kitty/dracula.conf" "$HOME/.config/kitty/dracula.conf"
ln -sf "$DOTFILES_DIR/kitty/diff.conf" "$HOME/.config/kitty/diff.conf"

display_header "thunderbird"
paru --needed -S thunderbird

display_header "filezilla"
paru --needed -S filezilla

display_header "sparrow wallet"
gpg --recv-keys D4D0D3202FC06849A257B38DE94618334C674B40
paru --needed -S sparrow-wallet

display_header "yubikey manager"
paru --needed -S yubikey-manager
sudo systemctl start pcscd.service pcscd.socket

display_header "yubikey manager"
paru --needed -S lazygit
mkdir -p "$HOME/.config/lazygit"
ln -sf "$DOTFILES_DIR/lazygit.yaml" "$HOME/.config/lazygit/config.yml"

display_header "gparted"
paru --needed -S gparted

display_header "standard notes"
paru --needed -S standardnotes-bin

display_header "discord"
paru --needed -S discord

display_header "telegram"
paru --needed -S telegram-desktop

display_header "newsflash"
paru --needed -S newsflash

display_header "restic"
paru --needed -S restic

display_header "gnome tools"
paru --needed -S gnome-contacts gnome-system-monitor gnome-weather

display_header "clean up"
if paru -Qs baobab >/dev/null
then
	paru -Rs baobab \
		deja-dup \
		endeavour \
		fragments \
		gnome-boxes \
		gnome-calendar \
		gnome-chess \
		gnome-clocks \
		gnome-connections \
		gnome-connections \
		gnome-disk-utility \
		gnome-logs \
		gnome-maps \
		gnome-mines \
		gnome-music \
		gnome-remote-desktop \
		gnome-terminal \
		gnome-text-editor \
		gnome-tour \
		gnome-user-docs \
		gnome-user-share \
		gthumb \
		iagno \
		lollypop \
		malcontent \
		networkmanager-openconnect \
		openconnect \
		orca \
		quadrapassel \
		seahorse \
		simple-scan \
		snapshot \
		stoken \
		timeshift \
		timeshift-autosnap-manjaro \
		yelp
fi

display_header "tweaking gnome"
# disable all before enabling specific ones
gnome-extensions list | xargs -n 1 gnome-extensions disable
# enable specific extensions from file
while read -r extensions
do
	gnome-extensions enable "$extensions"
done < gnome_extensions.txt

# enable service to cleanup package cache
# https://wiki.archlinux.org/title/Pacman#Cleaning_the_package_cache
sudo systemctl enable paccache.timer
sudo systemctl start paccache.timer

touch "$DOTFILES_DIR/.last_run"
