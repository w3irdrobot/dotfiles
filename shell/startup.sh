# shellcheck shell=bash
# shellcheck source-path=SCRIPTDIR

# Sourced by the Home Manager .bashrc after its session variables and aliases.
# Only Bash-specific setup belongs here; the rest lives in home.nix.

# Machine-local overrides, outside the checkout.
if [[ -f "$HOME/.config/bash/variables.sh" ]]; then
	# shellcheck source=/dev/null
	source "$HOME/.config/bash/variables.sh" || return
fi

if [[ -t 0 ]]; then
	GPG_TTY=$(tty)
	export GPG_TTY
fi

# shellcheck source=./functions.sh
source "${BASH_SOURCE[0]%/*}/functions.sh" || return
# shellcheck source=./prompt.sh
source "${BASH_SOURCE[0]%/*}/prompt.sh" || return
