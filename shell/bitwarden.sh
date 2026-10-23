# shellcheck shell=bash
# Native Bitwarden owns this agent socket. Enable its SSH agent in the app.
# Keep an explicitly selected agent; ~/.config/bash/variables.sh can override this.
if [[ ! -v SSH_AUTH_SOCK ]]; then
	export SSH_AUTH_SOCK="$HOME/.bitwarden-ssh-agent.sock"
fi
