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
