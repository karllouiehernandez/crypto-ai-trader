#!/usr/bin/env bash
# install_from_bundle.sh — Install the trader from a flash-drive or copied bundle
# Usage:
#   bash deployment/install_from_bundle.sh /path/to/crypto_ai_trader_bundle
set -euo pipefail

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" || "${1:-}" == "/?" ]]; then
    echo "Usage: bash deployment/install_from_bundle.sh /path/to/crypto_ai_trader_bundle"
    exit 0
fi

BUNDLE_DIR="${1:-}"
INSTALL_DIR="$HOME/crypto_ai_trader"
VENV_DIR="$INSTALL_DIR/.venv"
SERVICE_NAME="crypto-trader"

if [[ -z "$BUNDLE_DIR" ]]; then
    echo "Bundle path is required."
    echo "Usage: bash deployment/install_from_bundle.sh /path/to/crypto_ai_trader_bundle"
    exit 1
fi

if [[ ! -d "$BUNDLE_DIR" ]]; then
    echo "Bundle directory not found: $BUNDLE_DIR"
    exit 1
fi

if [[ ! -f "$BUNDLE_DIR/requirements.txt" ]]; then
    echo "Bundle directory does not look like crypto_ai_trader: missing requirements.txt"
    exit 1
fi

echo "=== Crypto AI Trader - Flash-Drive Install ==="
echo "Bundle dir  : $BUNDLE_DIR"
echo "Install dir : $INSTALL_DIR"
echo "Python venv : $VENV_DIR"
echo ""

mkdir -p "$INSTALL_DIR"

echo "[1/6] Copying bundle into install directory..."
if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete \
        --exclude ".env" \
        --exclude ".venv" \
        --exclude "backups" \
        --exclude "reports" \
        --exclude "knowledge/experiment_log.md" \
        --exclude ".run_live_eval.err" \
        --exclude ".run_live_eval.out" \
        --exclude ".streamlit_eval.err" \
        --exclude ".streamlit_eval.out" \
        --exclude ".streamlit_eval_phase2.err" \
        --exclude ".streamlit_eval_phase2.out" \
        --exclude ".streamlit_eval_phase47.err" \
        --exclude ".streamlit_eval_phase47.out" \
        "$BUNDLE_DIR/" "$INSTALL_DIR/"
else
    cp -a "$BUNDLE_DIR/." "$INSTALL_DIR/"
fi

echo "[2/6] Setting up Python virtual environment..."
if [[ ! -d "$VENV_DIR" ]]; then
    python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

echo "[3/6] Installing Python dependencies..."
pip install --upgrade pip --quiet
pip install --no-cache-dir -r "$INSTALL_DIR/requirements.txt"

echo "[4/6] Configuring environment..."
if [[ ! -f "$INSTALL_DIR/.env" ]]; then
    cp "$INSTALL_DIR/deployment/jetson.env.example" "$INSTALL_DIR/.env"
    echo ""
    echo "  IMPORTANT: Edit $INSTALL_DIR/.env with your real credentials:"
    echo "    nano $INSTALL_DIR/.env"
    echo ""
fi

echo "[5/6] Installing systemd service and log rotation..."
mkdir -p "$INSTALL_DIR/logs"
sed "s/User=jetson/User=$(whoami)/g; \
     s|WorkingDirectory=.*|WorkingDirectory=$INSTALL_DIR|g; \
     s|ExecStart=.*|ExecStart=$VENV_DIR/bin/python $INSTALL_DIR/run_live.py|g; \
     s|EnvironmentFile=.*|EnvironmentFile=$INSTALL_DIR/.env|g" \
    "$INSTALL_DIR/deployment/crypto-trader.service" \
    | sudo tee /etc/systemd/system/$SERVICE_NAME.service > /dev/null

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
echo "  Service installed and enabled (will start on boot)."

if [[ -f "$INSTALL_DIR/deployment/crypto-trader.logrotate" ]]; then
    sudo cp "$INSTALL_DIR/deployment/crypto-trader.logrotate" /etc/logrotate.d/crypto-trader
    echo "  Logrotate template installed at /etc/logrotate.d/crypto-trader."
fi

echo "[6/6] Verifying installation..."
python -c "import pandas, numpy, sqlalchemy, binance; print('  Core dependencies OK')"
python -c "from database.models import init_db; init_db(); print('  Database initialized')"
python -m deployment.jetson_ops health

echo ""
echo "=== Flash-drive install complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit your credentials:  nano $INSTALL_DIR/.env"
echo "  2. Start the trader:       sudo systemctl start $SERVICE_NAME"
echo "  3. Watch the logs:         journalctl -fu $SERVICE_NAME"
echo "  4. Optional MCP server:    cd $INSTALL_DIR && $VENV_DIR/bin/python run_mcp_server.py"
