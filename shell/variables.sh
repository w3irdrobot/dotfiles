# shellcheck shell=bash

# terminal colors and language
export CLICOLOR=1
export TERM="${TERM:-xterm-256color}"
export LS_COLORS="\
ln=38;5;152:\
di=38;5;110:\
ex=38;5;152:\
so=38;5;223:\
pi=38;5;223:\
bd=38;5;110:\
cd=38;5;110:\
*.txt=38;5;255:\
*.md=38;5;255:\
*.json=38;5;255:\
*.yaml=38;5;255:\
*.yml=38;5;255:\
*.toml=38;5;255:\
*.conf=38;5;255:\
*.py=38;5;110:\
*.sh=38;5;110:\
*.js=38;5;110:\
*.ts=38;5;110:\
*.rs=38;5;110:\
*.go=38;5;110:\
*.jpg=38;5;223:\
*.jpeg=38;5;223:\
*.png=38;5;223:\
*.gif=38;5;223:\
*.webp=38;5;223:\
*.svg=38;5;223:\
*.zip=38;5;173:\
*.tar=38;5;173:\
*.gz=38;5;173:\
*.xz=38;5;173:\
*.bz2=38;5;173:\
*.7z=38;5;173:\
*.deb=38;5;173:\
*.rpm=38;5;173"
export LANG="en_US.UTF-8"
export HISTCONTROL=ignoreboth

# terminal editor and configs
if command -v codium >/dev/null 2>&1; then
	export EDITOR="codium --wait"
else
	export EDITOR="vim"
fi
export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-${HOME}/.config}"

# Keep the login environment (including Nix profiles and project tooling).
# Only add our helpers once; never replace the inherited PATH.
case ":${PATH:-}:" in
*":${HOME}/.local/bin:"*) ;;
*) export PATH="${HOME}/.local/bin${PATH:+:${PATH}}" ;;
esac

# Gnupg
if [[ -t 0 ]]; then
	GPG_TTY=$(tty)
	export GPG_TTY
fi

# Docker
export DOCKER_BUILDKIT=1

# Google Cloud SDK
if [[ -d "${HOME}/google-cloud-sdk/bin" ]]; then
	case ":${PATH:-}:" in
	*":${HOME}/google-cloud-sdk/bin:"*) ;;
	*) export PATH="${HOME}/google-cloud-sdk/bin:${PATH}" ;;
	esac
fi

# Default browser
if command -v brave-browser >/dev/null 2>&1; then
	export BROWSER="brave-browser"
elif command -v brave >/dev/null 2>&1; then
	export BROWSER="brave"
elif command -v xdg-open >/dev/null 2>&1; then
	export BROWSER="xdg-open"
fi
