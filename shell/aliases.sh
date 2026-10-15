# shellcheck shell=bash

alias c="clear"
alias ..="cd .."
if command -v eza >/dev/null 2>&1; then
	alias ls="eza"
	alias ll="eza -alhF --group-directories-first --color auto"
fi
if command -v fd >/dev/null 2>&1; then alias find="fd"; fi
if command -v lazygit >/dev/null 2>&1; then alias lg="lazygit"; fi
if command -v bat >/dev/null 2>&1; then alias cat="bat"; fi

# XFCE uses X11; support an explicitly selected Wayland session too.
if [[ -n "${WAYLAND_DISPLAY:-}" ]] && command -v wl-copy >/dev/null 2>&1; then
	alias clip="wl-copy"
else
	alias clip="xclip -selection clipboard"
fi
