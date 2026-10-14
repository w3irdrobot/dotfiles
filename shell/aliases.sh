# shellcheck shell=bash

alias c="clear"
alias ..="cd .."
alias ls="eza"
alias find="fd"
alias ll="eza -alhF --group-directories-first --color auto"
alias lg="lazygit"
alias cat="bat"

# XFCE uses X11; support an explicitly selected Wayland session too.
if [[ -n "${WAYLAND_DISPLAY:-}" ]] && command -v wl-copy >/dev/null 2>&1; then
	alias clip="wl-copy"
else
	alias clip="xclip -selection clipboard"
fi
