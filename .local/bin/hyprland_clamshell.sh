#!/usr/bin/env bash

monitor_count=$(hyprctl monitors all | grep -v '^[[:space:]]' | grep -cv '^$')

if [[ monitor_count -gt 1 ]]; then
    if [[ $1 == "open" ]]; then
        hyprctl keyword monitorv2[eDP-1]:disabled false
    else
        hyprctl keyword monitorv2[eDP-1]:disabled true
    fi
fi
