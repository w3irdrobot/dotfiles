#!/usr/bin/env bash
#
# Bootstrap script for setting up a new machine
# Usage: curl -fsSL https://dotfiles.w3ird.tech/install.sh | bash
#

set -euo pipefail

DOTFILES_REPO="w3irdrobot"

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

detect_os() {
    case "$(uname -s)" in
        Darwin*) OS="darwin" ;;
        Linux*)
            if [[ ! -r /etc/os-release ]]; then
                log_error "Cannot identify this Linux distribution: /etc/os-release is missing"
                exit 1
            fi

            # shellcheck source=/dev/null
            source /etc/os-release
            if [[ "${ID:-}" != "pop" || "${VERSION_ID:-}" != "24.04" ]]; then
                log_error "Unsupported Linux distribution: ${PRETTY_NAME:-unknown}"
                log_error "This installer supports Pop!_OS 24.04 LTS only."
                exit 1
            fi
            if [[ "$(uname -m)" != "x86_64" ]]; then
                log_error "Unsupported architecture: $(uname -m) (x86_64 required)"
                exit 1
            fi
            OS="linux"
            ;;
        *)
            log_error "Unsupported operating system: $(uname -s)"
            exit 1
            ;;
    esac
    log_info "Detected OS: ${PRETTY_NAME:-$OS} ($(uname -m))"
}

install_chezmoi() {
    if command -v chezmoi &> /dev/null; then
        log_info "chezmoi already installed"
        return
    fi

    log_info "Installing chezmoi..."

    # Ensure ~/.local/bin exists and is in PATH
    mkdir -p "$HOME/.local/bin"
    export PATH="$HOME/.local/bin:$PATH"

    # Use chezmoi's official installer - works on all platforms
    sh -c "$(curl -fsLS get.chezmoi.io)" -- -b "$HOME/.local/bin"

    log_success "chezmoi installed"
}

chezmoi_is_initialized() {
    local required_data='
{{ .email }}
{{ .install_slack }}
{{ .install_gcloud }}
{{ .install_nvm }}
{{ .install_kubernetes_tools }}
{{ .bitcoin_mount_choice }}
{{ .bitcoin_mount }}
{{ .bitcoin_datadir }}
{{ .electrs_mount_choice }}
{{ .electrs_mount }}
{{ .electrs_datadir }}'

    if [[ "$OS" == "linux" ]]; then
        required_data+='
{{ .linux_distribution }}
{{ .linux_version }}
{{ .linux_codename }}
{{ .linux_architecture }}
{{ .install_brave }}
{{ .install_vscodium }}
{{ .install_mullvad }}
{{ .install_signal }}
{{ .install_bitwarden }}
{{ .install_discord }}
{{ .install_spotify }}
{{ .install_telegram }}
{{ .install_thunderbird }}
{{ .install_1password }}
{{ .install_tor_browser }}'
    fi

    chezmoi execute-template "$required_data" >/dev/null 2>&1
}

apply_dotfiles() {
    log_info "Initializing dotfiles with chezmoi..."
    log_info "This will install packages and configure your system..."

    if [[ -d "$HOME/.local/share/chezmoi" ]] && chezmoi_is_initialized; then
        log_info "Dotfiles already initialized, updating..."
        chezmoi update
    else
        if [[ -d "$HOME/.local/share/chezmoi" ]]; then
            log_info "Previous initialization is incomplete, resuming prompts..."
        fi
        chezmoi init --apply "$DOTFILES_REPO"
    fi

    log_success "Dotfiles applied"
}

main() {
    echo ""
    echo "=========================================="
    echo "   w3irdrobot Dotfiles Bootstrap"
    echo "=========================================="
    echo ""

    detect_os
    install_chezmoi
    apply_dotfiles

    echo ""
    log_success "Bootstrap complete!"
    log_info "Please restart your terminal to use the new shell configuration."
    echo ""
}

main "$@"
