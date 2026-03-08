#!/bin/bash

# Path to wofi
WOFI_CMD="wofi"

# Check if wofi is running
if pgrep -x "$WOFI_CMD" > /dev/null; then
    pkill -x "$WOFI_CMD"
    exit 0
fi

# Launch wofi with our theme
wofi
