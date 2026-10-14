# shellcheck shell=bash
# shellcheck source-path=SCRIPTDIR

# shellcheck source=./variables.sh
source "$(dirname -- "${BASH_SOURCE[0]}")/variables.sh" || return
# shellcheck source=./aliases.sh
source "$(dirname -- "${BASH_SOURCE[0]}")/aliases.sh" || return
# shellcheck source=./functions.sh
source "$(dirname -- "${BASH_SOURCE[0]}")/functions.sh"
