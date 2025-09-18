#!/usr/bin/env bash

set -euo pipefail

# --- Logging utilities -----------------------------------------------------
# Usage:
#   source "$(dirname "$0")/utils.sh"
#   log_info "Installing packages"
#   log_error "Failed to install foo"

# Respect NO_COLOR and only enable colors when outputting to a TTY
if { [[ -t 1 ]] || [[ -t 2 ]] ; } && [[ -z "${NO_COLOR:-}" ]]; then
  _COLOR_RESET='\033[0m'
  _COLOR_RED='\033[31m'
  _COLOR_BLUE='\033[34m'
else
  _COLOR_RESET=''
  _COLOR_RED=''
  _COLOR_BLUE=''
fi

# Print an informational message to stdout
log_info() {
  # shellcheck disable=SC2059 # intentional use of printf formatting for colors
  printf "%b\n" "${_COLOR_BLUE}[INFO]${_COLOR_RESET} $*"
}

# Print an error message to stderr (in red)
log_error() {
  # shellcheck disable=SC2059 # intentional use of printf formatting for colors
  printf "%b\n" "${_COLOR_RED}[ERROR]${_COLOR_RESET} $*" >&2
}
