# shellcheck shell=bash

# initialize base environment
export AS_DOTFILES_DIR="${HOME}/.dotfiles"

# shellcheck source=./.init
source "${AS_DOTFILES_DIR}/.init"

# initialize local specific environment
if [[ -a "${XDG_CONFIG_HOME}/bash/.init" ]]; then
    # shellcheck source=../.config/bash/.init
    source "${XDG_CONFIG_HOME}/bash/.init"
fi

if [[ -a "${XDG_CONFIG_HOME}/bash/.variables" ]]; then
    # shellcheck source=../.config/bash/.variables
    source "${XDG_CONFIG_HOME}/bash/.variables"
fi

if [[ -a "${XDG_CONFIG_HOME}/bash/.aliases" ]]; then
    # shellcheck source=../.config/bash/.aliases
    source "${XDG_CONFIG_HOME}/bash/.aliases"
fi

if [[ -a "${XDG_CONFIG_HOME}/bash/.functions" ]]; then
    # shellcheck source=../.config/bash/.functions
    source "${XDG_CONFIG_HOME}/bash/.functions"
fi

# initialize fzf
eval "$(fzf --bash)"

# initialize starship prompt
eval "$(starship init bash)"

# initialize zoxide
eval "$(zoxide init bash)"

