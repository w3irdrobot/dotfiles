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
        Linux*)  OS="linux" ;;
        *)
            log_error "Unsupported operating system: $(uname -s)"
            exit 1
            ;;
    esac
    log_info "Detected OS: $OS"
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

apply_dotfiles() {
    log_info "Initializing dotfiles with chezmoi..."
    log_info "This will install packages and configure your system..."

    if [ -d "$HOME/.local/share/chezmoi" ]; then
        log_info "Dotfiles already initialized, updating..."
        chezmoi update
    else
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
