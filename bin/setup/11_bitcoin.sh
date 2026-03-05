#!/usr/bin/env bash

set -euo pipefail

BITCOIN_VERSION="29.2"

# shellcheck source=utils.sh
source "$SETUP_DIR/utils.sh"

log_info "Installing bitcoind"
(
    cd ~/Downloads
    wget https://bitcoincore.org/bin/bitcoin-core-$BITCOIN_VERSION/bitcoin-$BITCOIN_VERSION-x86_64-linux-gnu.tar.gz
    tar -xzf bitcoin-$BITCOIN_VERSION-x86_64-linux-gnu.tar.gz
    sudo install bitcoin-$BITCOIN_VERSION/bin/* /usr/local/bin
)

# This is used to have a consistent mount point for bitcoin external ssd
sudo mkdir -p /mnt/bitcoinssd

log_info "Adding user to bitcoin group"
# This GID is the one used on the external SSD for bitcoin data
sudo groupadd -g 30001 -f bitcoin
sudo usermod -aG bitcoin "$USER"
