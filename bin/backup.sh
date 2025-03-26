#!/usr/bin/env bash

if ! grep -qs '/mnt/backups ' /proc/mounts
then
    echo "the backup disk isn't mounted at /mnt/backups. run 'sudo mount /dev/sda1 /mnt/backups'."
    exit 1
fi

restic -r /mnt/backups/ backup ~
