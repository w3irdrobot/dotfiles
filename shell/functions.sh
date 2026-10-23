# shellcheck shell=bash

function take() {
	mkdir -p "${1}"
	cd "${1}" || return
}

function clear_history() {
	history -c
	history -w
}

function scratch() {
	local directory
	directory=$(mktemp --directory -t scratch_XXXXXX) || return
	cd "$directory" || return
}

# Are we already inside a gshell session?
_gshell_is_active() {
	[ -n "${GSHELL_ACTIVE:-}" ]
}

# Subcommand guard: bail with a helpful message if not inside gshell.
_gshell_require_active() {
	if _gshell_is_active; then return 0; fi
	echo "$1: must be run inside a gshell session" >&2
	echo "start one with: gshell <profile>" >&2
	return 1
}

# List gcloud configs from the host (excluding 'default').
_gshell_list_configs() {
	CLOUDSDK_CONFIG="$HOME/.config/gcloud" \
		gcloud config configurations list --format="value(name)" | grep -v '^default$'
}

# Verify a named gcloud config exists on the host.
_gshell_config_exists() {
	CLOUDSDK_CONFIG="$HOME/.config/gcloud" \
		gcloud config configurations describe "$1" >/dev/null 2>&1
}

# Pick a config, validating it exists. Uses fzf when no arg is supplied.
_gshell_choose_config() {
	local requested_cfg="$1"
	local chosen_cfg

	if [ -n "$requested_cfg" ]; then
		if ! _gshell_config_exists "$requested_cfg"; then
			echo "gcloud config '$requested_cfg' not found" >&2
			echo "Available configs:" >&2
			_gshell_list_configs >&2
			return 1
		fi
		printf '%s\n' "$requested_cfg"
		return 0
	fi

	if ! command -v fzf >/dev/null 2>&1; then
		echo "usage: gshell <config-name>" >&2
		echo "Available configs:" >&2
		_gshell_list_configs >&2
		return 1
	fi

	local configs
	configs="$(_gshell_list_configs)"
	if [ -z "$configs" ]; then
		echo "no gcloud configurations available" >&2
		echo "create one: gcloud config configurations create <name>" >&2
		return 1
	fi

	chosen_cfg="$(printf '%s\n' "$configs" | fzf \
		--prompt="gcloud config > " \
		--height=40% \
		--reverse \
		--border \
		--exit-0)"

	if [ -z "$chosen_cfg" ]; then
		return 1
	fi

	printf '%s\n' "$chosen_cfg"
}

# Prepare the persistent per-profile sandbox. Shared gcloud state is linked
# from the host while each profile keeps independent ADC credentials.
_gshell_ensure_sandbox() {
	local cfg="$1"
	local host="$HOME/.config/gcloud"
	local sandbox="$HOME/.config/gshell/$cfg"
	local share

	if ! mkdir -p "$sandbox"; then
		echo "failed to create sandbox: $sandbox" >&2
		return 1
	fi

	for share in configurations credentials.db access_tokens.db legacy_credentials; do
		if [ ! -e "$host/$share" ] && [ ! -L "$host/$share" ]; then
			continue
		fi
		if [ -L "$sandbox/$share" ]; then
			continue
		fi
		if [ -e "$sandbox/$share" ]; then
			echo "warning: $sandbox/$share is not a symlink; leaving as-is" >&2
			continue
		fi
		if ! ln -s "$host/$share" "$sandbox/$share"; then
			echo "failed to symlink $sandbox/$share" >&2
			return 1
		fi
	done

	printf '%s\n' "$sandbox"
}

# Activate a profile when no subcommand is given.
# shellcheck disable=SC2030 # Profile exports intentionally belong to the child shell.
_gshell_cmd_activate() {
	local cfg
	local sandbox_dir

	if ! command -v gcloud >/dev/null 2>&1; then
		echo "gcloud not found in PATH" >&2
		return 1
	fi

	if [ ! -d "$HOME/.config/gcloud" ]; then
		echo "gcloud config directory not found: $HOME/.config/gcloud" >&2
		return 1
	fi

	if _gshell_is_active; then
		echo "already inside gshell (CLOUDSDK_CONFIG=$CLOUDSDK_CONFIG)" >&2
		echo "exit this shell before starting another gshell session" >&2
		return 1
	fi

	cfg="$(_gshell_choose_config "${1:-}")" || return 1

	sandbox_dir="$(_gshell_ensure_sandbox "$cfg")" || {
		echo "failed to prepare sandbox for $cfg" >&2
		return 1
	}

	(
		export CLOUDSDK_CONFIG="$sandbox_dir"
		export CLOUDSDK_ACTIVE_CONFIG_NAME="$cfg"
		export GSHELL_ACTIVE=1
		if [ -f "$sandbox_dir/application_default_credentials.json" ]; then
			export GOOGLE_APPLICATION_CREDENTIALS="$sandbox_dir/application_default_credentials.json"
		fi

		echo "gshell started"
		echo "  profile: $cfg"
		echo "  sandbox: $sandbox_dir"

		if ! gcloud auth print-access-token >/dev/null 2>&1; then
			echo "  user auth not valid; running gshell login..."
			gcloud auth login --no-launch-browser
		fi

		if [ ! -f "$sandbox_dir/application_default_credentials.json" ]; then
			echo "  note: no ADC yet for this profile. run: gshell app-login"
		elif ! gcloud auth application-default print-access-token >/dev/null 2>&1; then
			echo "  note: ADC is not valid. run: gshell app-login"
		fi

		echo "  exit to return to normal shell"

		exec "${SHELL:-/bin/bash}" -i
	)
}

# Run gcloud user login inside an active profile.
_gshell_cmd_login() {
	_gshell_require_active "gshell login" || return 1
	gcloud auth login --no-launch-browser "$@"
}

# Run application-default login, inheriting the profile's impersonation config.
# shellcheck disable=SC2031 # This function runs inside the activated child shell.
_gshell_cmd_app_login() {
	_gshell_require_active "gshell app-login" || return 1

	local user_override=0
	local arg
	for arg in "$@"; do
		case "$arg" in
		--impersonate-service-account | --impersonate-service-account=*)
			user_override=1
			break
			;;
		esac
	done

	local -a app_login_cmd
	app_login_cmd=(gcloud auth application-default login --no-launch-browser)
	if [ "$user_override" -eq 0 ]; then
		local impersonate
		impersonate="$(gcloud config get-value auth/impersonate_service_account 2>/dev/null)"
		if [ -n "$impersonate" ] && [ "$impersonate" != "(unset)" ]; then
			app_login_cmd+=(--impersonate-service-account="$impersonate")
		fi
	fi

	"${app_login_cmd[@]}" "$@"
	local rc=$?

	if [ "$rc" -eq 0 ] && [ -f "$CLOUDSDK_CONFIG/application_default_credentials.json" ]; then
		export GOOGLE_APPLICATION_CREDENTIALS="$CLOUDSDK_CONFIG/application_default_credentials.json"
	fi
	return "$rc"
}

# Main entrypoint.
gshell() {
	local subcommand="${1:-}"
	case "$subcommand" in
	login)
		shift
		_gshell_cmd_login "$@"
		;;
	app-login)
		shift
		_gshell_cmd_app_login "$@"
		;;
	*)
		_gshell_cmd_activate "$@"
		;;
	esac
}
function ai() {
	local profile="opencode-dev"
	local -a nono_args client_args=()

	case "${1:-}" in
	base | dev | setup)
		profile="opencode-$1"
		shift
		;;
	opencode-base | opencode-dev | opencode-setup)
		profile="$1"
		shift
		;;
	esac

	case "${1:-}" in
	run | mini)
		client_args=("$1" --standalone)
		shift
		;;
	upgrade | update | uninstall | acp | api | debug | auth | mcp | plugin | models | stats | session | service | reload | pair | serve)
		;;
	*)
		client_args=(--standalone)
		;;
	esac

	nono_args=(--profile "$profile" --silent --no-diagnostics --suppress-save-prompt /)
	if [[ "$profile" == "opencode-dev" ]]; then
		nono_args+=(--allow-cwd)
	fi

	OPENCODE_DISABLE_EXTERNAL_SKILLS=1 nono run "${nono_args[@]}" -- opencode "${client_args[@]}" "$@"
}
