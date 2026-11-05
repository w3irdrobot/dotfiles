# shellcheck shell=bash
# Node-local startup block: place before .bashrc's non-interactive return.
# BEGIN cargo-metrics PATH
case ":${PATH-}:" in
*":$HOME/.local/bin:"*) ;;
*) export PATH="$HOME/.local/bin${PATH:+:$PATH}" ;;
esac
# END cargo-metrics PATH
