#!/usr/bin/env bash
# install.sh — First-run setup for Jetson Nano
# Run as the non-root user that will own the trader process:
#   bash deployment/install.sh
set -euo pipefail

REPO_URL="https://github.com/karllouiehernandez/crypto-ai-trader.git"
INSTALL_DIR="$HOME/crypto_ai_trader"
VENV_DIR="$INSTALL_DIR/.venv"
SERVICE_NAME="crypto-trader"

echo "=== Crypto AI Trader — Jetson Nano Install ==="
echo "Install dir : $INSTALL_DIR"
echo "Python venv : $VENV_DIR"
echo ""

# ── 1. Clone or update repo ───────────────────────────────────────────────────
if [ ! -d "$INSTALL_DIR/.git" ]; then
    echo "[1/6] Cloning repository..."
    git clone "$REPO_URL" "$INSTALL_DIR"
else
    echo "[1/6] Repository already cloned — pulling latest..."
    git -C "$INSTALL_DIR" pull
fi

# ── 2. Create Python venv ─────────────────────────────────────────────────────
echo "[2/6] Setting up Python virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

# ── 3. Install dependencies ───────────────────────────────────────────────────
echo "[3/6] Installing Python dependencies (this may take 15-20 min on first run)..."
pip install --upgrade pip --quiet
pip install --no-cache-dir -r "$INSTALL_DIR/requirements.txt"

# ── 4. Configure .env ────────────────────────────────────────────────────────
echo "[4/6] Configuring environment..."
if [ ! -f "$INSTALL_DIR/.env" ]; then
    cp "$INSTALL_DIR/deployment/jetson.env.example" "$INSTALL_DIR/.env"
    echo ""
    echo "  IMPORTANT: Edit $INSTALL_DIR/.env with your real credentials:"
    echo "    nano $INSTALL_DIR/.env"
    echo ""
fi

# ── 5. Install systemd service ────────────────────────────────────────────────
echo "[5/6] Installing systemd service..."
# Patch User= to the current user
sed "s/User=jetson/User=$(whoami)/g; \
     s|WorkingDirectory=.*|WorkingDirectory=$INSTALL_DIR|g; \
     s|ExecStart=.*|ExecStart=$VENV_DIR/bin/python $INSTALL_DIR/run_live.py|g; \
     s|EnvironmentFile=.*|EnvironmentFile=$INSTALL_DIR/.env|g" \
    "$INSTALL_DIR/deployment/crypto-trader.service" \
    | sudo tee /etc/systemd/system/$SERVICE_NAME.service > /dev/null

sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
echo "  Service installed and enabled (will start on boot)."

# ── 6. Verify Python environment ─────────────────────────────────────────────
echo "[6/6] Verifying installation..."
python -c "import pandas, numpy, sqlalchemy, binance; print('  Core dependencies OK')"

echo ""
echo "=== Install complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit your credentials:  nano $INSTALL_DIR/.env"
echo "  2. Start the trader:       sudo systemctl start $SERVICE_NAME"
echo "  3. Watch the logs:         journalctl -fu $SERVICE_NAME"
echo "  4. Start MCP server:       cd $INSTALL_DIR && $VENV_DIR/bin/python run_mcp_server.py --transport sse"
echo ""
echo "SSH tunnel for remote agent access (run on your dev machine):"
echo "  ssh -L 8765:localhost:8765 $(whoami)@\$(hostname -I | awk '{print \$1}')"
