#!/usr/bin/env bash
# setup_swap.sh — Create a 4GB swap file on Jetson Nano
# Run once as root: sudo bash deployment/setup_swap.sh
set -euo pipefail

SWAP_FILE=/swapfile
SWAP_SIZE_GB=4

if swapon --show | grep -q "$SWAP_FILE"; then
    echo "Swap file $SWAP_FILE is already active. Skipping."
    exit 0
fi

if [ -f "$SWAP_FILE" ]; then
    echo "Swap file $SWAP_FILE exists but is not active. Re-enabling."
    swapon "$SWAP_FILE"
    exit 0
fi

echo "Creating ${SWAP_SIZE_GB}GB swap at $SWAP_FILE ..."
fallocate -l ${SWAP_SIZE_GB}G "$SWAP_FILE"
chmod 600 "$SWAP_FILE"
mkswap "$SWAP_FILE"
swapon "$SWAP_FILE"

if ! grep -q "$SWAP_FILE" /etc/fstab; then
    echo "$SWAP_FILE none swap sw 0 0" >> /etc/fstab
    echo "Added swap entry to /etc/fstab (persists across reboots)."
fi

# Reduce swappiness — only swap under real memory pressure
sysctl vm.swappiness=10
if ! grep -q "vm.swappiness" /etc/sysctl.d/99-swap.conf 2>/dev/null; then
    echo "vm.swappiness=10" >> /etc/sysctl.d/99-swap.conf
fi

echo ""
echo "Swap configured successfully:"
swapon --show
free -h | grep -E "Mem|Swap"
