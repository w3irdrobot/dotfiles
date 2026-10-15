# shellcheck shell=bash
# shellcheck source-path=SCRIPTDIR

# .bashrc supplies this file's absolute checkout path. Expansion keeps all
# sources relative to it without caller bookkeeping or extra path commands.
# shellcheck source=./init.sh
source "${BASH_SOURCE[0]%/*}/init.sh" || return

# App-specific defaults, before machine-local overrides. No app execution.
if command -v bitwarden-desktop >/dev/null 2>&1 || command -v bitwarden >/dev/null 2>&1; then
	# shellcheck source=./bitwarden.sh
	source "${BASH_SOURCE[0]%/*}/bitwarden.sh" || return
fi

# Explicit optional sources keep declarations at top level without a loop var.
if [[ -f "${BASH_SOURCE[0]%/*}/../local/bash/init.sh" ]]; then
	# shellcheck source=/dev/null
	source "${BASH_SOURCE[0]%/*}/../local/bash/init.sh" || return
fi
if [[ -f "${BASH_SOURCE[0]%/*}/../local/bash/aliases.sh" ]]; then
	# shellcheck source=/dev/null
	source "${BASH_SOURCE[0]%/*}/../local/bash/aliases.sh" || return
fi
if [[ -f "${BASH_SOURCE[0]%/*}/../local/bash/functions.sh" ]]; then
	# shellcheck source=/dev/null
	source "${BASH_SOURCE[0]%/*}/../local/bash/functions.sh" || return
fi

# Private variables are optional, outside the checkout, and last among overrides.
# Keep source at top level for declare/typeset. Explicit branches avoid caller
# bookkeeping variables; eval only restores literal options and a numeric status.
# Suppress both command tracing and verbose source-line output before reading.
if [[ -f "$HOME/.config/bash/variables.sh" ]]; then
	case $- in
	*x*v* | *v*x*)
		set +xv
		# shellcheck source=/dev/null
		source "$HOME/.config/bash/variables.sh" || eval "set -xv; return $?"
		set -xv
		;;
	*x*)
		set +x
		# shellcheck source=/dev/null
		source "$HOME/.config/bash/variables.sh" || eval "set -x; return $?"
		set -x
		;;
	*v*)
		set +v
		# shellcheck source=/dev/null
		source "$HOME/.config/bash/variables.sh" || eval "set -v; return $?"
		set -v
		;;
	*)
		# shellcheck source=/dev/null
		source "$HOME/.config/bash/variables.sh" || return
		;;
	esac
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
