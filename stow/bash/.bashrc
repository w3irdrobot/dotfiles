# shellcheck shell=bash
# shellcheck source-path=SCRIPTDIR

# Noninteractive shells retain their environment without loading interactive helpers.
[[ $- == *i* ]] || return 0

# Resolve the deployed symlink in a subshell: no caller variables or functions.
# Emit the complete source path only after every resolution step succeeds.
# Keep sourcing at top level so overrides' declare/typeset retain normal scope.
# shellcheck source=../../shell/startup.sh
source "$(
	_dotfiles_bashrc=$(command readlink -f -- "${BASH_SOURCE[0]}") || exit
	_dotfiles_directory=$(command dirname -- "$_dotfiles_bashrc") || exit
	builtin cd -P -- "$_dotfiles_directory/../.." || exit
	builtin printf '%s/shell/startup.sh\n' "$PWD"
)" || return
