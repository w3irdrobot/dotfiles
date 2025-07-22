#!/usr/bin/env bash

# Check if device type is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 [laptop|desktop]"
    exit 1
fi

DEVICE_TYPE="$1"
WALLPAPER_DIR="$HOME/Pictures/Wallpapers"

# Get the current wallpaper to avoid repeating it
CURRENT_WALL=$(hyprctl hyprpaper listloaded 2>/dev/null || true)

# Find a random wallpaper matching the device type
WALLPAPER=$(find "$WALLPAPER_DIR" -type f -name "*-${DEVICE_TYPE}.jpg" ! -path "*/.*" | \
    grep -v "$(basename "$CURRENT_WALL" 2>/dev/null || echo "")" | \
    shuf -n 1)

# If no matching wallpaper found, try without the device type filter
if [ -z "$WALLPAPER" ]; then
    WALLPAPER=$(find "$WALLPAPER_DIR" -type f \( -name '*.jpg' -o -name '*.jpeg' -o -name '*.png' \) \
        ! -path "*/.*" | \
        grep -v "$(basename "$CURRENT_WALL" 2>/dev/null || echo "")" | \
        shuf -n 1)
fi

if [ -n "$WALLPAPER" ]; then
    hyprctl hyprpaper reload ",$WALLPAPER"

    echo "Changed wallpaper to: $WALLPAPER"
else
    echo "No wallpapers found in $WALLPAPER_DIR"
    exit 1
fi
