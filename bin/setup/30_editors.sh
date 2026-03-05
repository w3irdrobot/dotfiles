#!/usr/bin/env bash

set -euo pipefail

# shellcheck source=utils.sh
source "$SETUP_DIR/utils.sh"

log_info "Installing editors"
yay -Syu --needed \
    vim \
    vscodium-bin

log_info "Installing VSCodium plugins"
while read -r line; do
    codium --install-extension "$line"
done <<EOF
adamhartford.vscode-base64
catppuccin.catppuccin-vsc
eamodio.gitlens
editorconfig.editorconfig
emmanuelbeziat.vscode-great-icons
hashicorp.terraform
ms-azuretools.vscode-containers
ms-azuretools.vscode-docker
ms-vscode.hexeditor
nefrob.vscode-just-syntax
redhat.vscode-yaml
rust-lang.rust-analyzer
silofy.hackthebox
tamasfe.even-better-toml
timonwong.shellcheck
usernamehw.errorlens
vadimcn.vscode-lldb
yzhang.markdown-all-in-one
EOF
