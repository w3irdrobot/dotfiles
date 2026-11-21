# Machine-local exports: manually copy to ~/.config/bash/variables.sh.
# The managed .bashrc reads this through the checkout's shell helpers.
# Keep the real file outside this checkout and owner-only (mode 0600).
# Exported secrets are inherited by child processes, including AI. Prefer credential injection when
# available. Never enable tracing inside this file or print secret values.

# export EDITOR=vim
# export AWS_PROFILE=personal
# export SSH_AUTH_SOCK="$HOME/.bitwarden-ssh-agent.sock"
