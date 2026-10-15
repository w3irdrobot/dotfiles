# Non-secret machine-local exports: copy to ignored local/bash/variables.sh.
# The managed .bashrc reads this through the checkout's shell helpers.
# This checkout is AI-readable/writable. Gitignore and mode 0600 do not isolate
# secrets from an agent running as you. Use credential injection for API access;
# keep credential-manager storage outside AI filesystem grants.

# export EDITOR=vim
# export AWS_PROFILE=personal
# export SSH_AUTH_SOCK="$HOME/.bitwarden-ssh-agent.sock"
