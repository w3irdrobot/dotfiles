#!/usr/bin/env bash

set -euo pipefail

# shellcheck source=utils.sh
source "$SETUP_DIR/utils.sh"

has_yazi_plugin() {
    local plugin_name
    plugin_name="$1"

    ya pkg list | grep "$plugin_name" &> /dev/null
}

log_info "Installing yazi and friends"
yay -Syu --needed \
    yazi \
    udisks2

if ! has_yazi_plugin "mount"
then
    ya pkg add yazi-rs/plugins:mount
fi

if ! has_yazi_plugin "chmod"
then
    ya pkg add yazi-rs/plugins:chmod
fi

if ! has_yazi_plugin "compress"
then
    ya pkg add KKV9/compress
fi
