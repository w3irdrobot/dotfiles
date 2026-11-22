# shellcheck shell=bash
# shellcheck source-path=SCRIPTDIR

# Sourced by the Home Manager .bashrc.
# shellcheck source=./init.sh
source "${BASH_SOURCE[0]%/*}/init.sh" || return

# Machine-local overrides, outside the checkout.
if [[ -f "$HOME/.config/bash/variables.sh" ]]; then
	# shellcheck source=/dev/null
	source "$HOME/.config/bash/variables.sh" || return
fi

if [[ -f /usr/share/bash-completion/bash_completion ]]; then
	# shellcheck source=/dev/null
	source /usr/share/bash-completion/bash_completion || return
fi

if command -v fzf >/dev/null 2>&1; then
	eval "$(fzf --bash)"
fi

# shellcheck source=./prompt.sh
source "${BASH_SOURCE[0]%/*}/prompt.sh" || return

if command -v zoxide >/dev/null 2>&1; then
	eval "$(zoxide init bash)"
fi
