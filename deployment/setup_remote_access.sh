#!/usr/bin/env bash
# setup_remote_access.sh — One-time Jetson helper for SSH/SFTP access
set -euo pipefail

echo "=== Jetson SSH/SFTP setup ==="

if ! command -v sudo >/dev/null 2>&1; then
    echo "sudo is required for this setup."
    exit 1
fi

echo "[1/4] Installing openssh-server if needed..."
if ! dpkg -s openssh-server >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y openssh-server
else
    echo "  openssh-server already installed."
fi

echo "[2/4] Enabling and restarting ssh service..."
if systemctl list-unit-files --type=service | grep -q "^ssh\.service"; then
    sudo systemctl enable ssh || true
    sudo systemctl restart ssh
elif systemctl list-unit-files --type=service | grep -q "^sshd\.service"; then
    sudo systemctl enable sshd || true
    sudo systemctl restart sshd
else
    echo "  Could not find ssh.service or sshd.service in systemd. SSH may already be managed externally."
fi

echo "[3/4] Preparing ~/.ssh directory..."
mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"
touch "$HOME/.ssh/authorized_keys"
chmod 600 "$HOME/.ssh/authorized_keys"

echo "[4/4] Opening firewall for ssh if ufw is active..."
if command -v ufw >/dev/null 2>&1; then
    if sudo ufw status | grep -qi "Status: active"; then
        sudo ufw allow ssh
    else
        echo "  ufw not active. Skipping firewall change."
    fi
else
    echo "  ufw not installed. Skipping firewall change."
fi

echo ""
echo "SSH/SFTP server is ready."
echo "Hostname: $(hostname)"
echo "IP(s):"
hostname -I || true
