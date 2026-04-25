#!/usr/bin/env bash
# bootstrap_python310_install.sh — Jetson Nano fallback installer when apt lacks Python 3.10
# Usage:
#   bash deployment/bootstrap_python310_install.sh
#   PYTHON_VERSION=3.10.14 bash deployment/bootstrap_python310_install.sh
set -euo pipefail

PYTHON_VERSION="${PYTHON_VERSION:-3.10.14}"
PYTHON_PREFIX="${PYTHON_PREFIX:-/usr/local}"
PYTHON_BIN="$PYTHON_PREFIX/bin/python3.10"
PYTHON_TARBALL="Python-${PYTHON_VERSION}.tgz"
PYTHON_SRC_DIR="/tmp/Python-${PYTHON_VERSION}"
INSTALL_DIR="${INSTALL_DIR:-$HOME/crypto_ai_trader}"
VENV_DIR="$INSTALL_DIR/.venv"
SERVICE_NAME="crypto-trader"
DASHBOARD_SERVICE_NAME="crypto-trader-dashboard"
FAN_SERVICE_NAME="crypto-trader-fan"
MAKE_JOBS="${MAKE_JOBS:-2}"

echo "=== Crypto AI Trader — Jetson Python 3.10 Bootstrap ==="
echo "Python version : $PYTHON_VERSION"
echo "Python prefix  : $PYTHON_PREFIX"
echo "Install dir    : $INSTALL_DIR"
echo "Venv dir       : $VENV_DIR"
echo ""

if [[ ! -f "$INSTALL_DIR/requirements.txt" ]]; then
    echo "Missing requirements.txt in $INSTALL_DIR"
    echo "Run this script from a copied bundle install or after the repo is in place."
    exit 1
fi

echo "[1/8] Installing build dependencies..."
sudo apt update
sudo apt install -y \
    build-essential wget curl rsync ca-certificates \
    libssl-dev zlib1g-dev libbz2-dev libreadline-dev \
    libsqlite3-dev libffi-dev libncursesw5-dev xz-utils \
    tk-dev libxml2-dev libxmlsec1-dev liblzma-dev uuid-dev

echo "[2/8] Building Python $PYTHON_VERSION if needed..."
if [[ ! -x "$PYTHON_BIN" ]]; then
    cd /tmp
    rm -rf "$PYTHON_SRC_DIR" "/tmp/$PYTHON_TARBALL"
    wget "https://www.python.org/ftp/python/${PYTHON_VERSION}/${PYTHON_TARBALL}"
    tar -xzf "$PYTHON_TARBALL"
    cd "$PYTHON_SRC_DIR"
    ./configure --prefix="$PYTHON_PREFIX" --with-ensurepip=install
    make -j"$MAKE_JOBS"
    sudo make altinstall
else
    echo "  Python 3.10 already installed at $PYTHON_BIN"
fi

echo "[3/8] Verifying Python 3.10..."
"$PYTHON_BIN" --version

echo "[4/8] Recreating virtual environment..."
rm -rf "$VENV_DIR"
"$PYTHON_BIN" -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
cd "$INSTALL_DIR"

echo "[5/8] Installing Python requirements..."
pip install --upgrade pip
pip install --no-cache-dir -r "$INSTALL_DIR/requirements.txt"

echo "[6/8] Preparing environment file..."
if [[ ! -f "$INSTALL_DIR/.env" ]]; then
    cp "$INSTALL_DIR/deployment/jetson.env.example" "$INSTALL_DIR/.env"
    echo "  Created $INSTALL_DIR/.env from deployment/jetson.env.example"
fi

echo "[7/8] Installing systemd services..."
mkdir -p "$INSTALL_DIR/logs"
sed "s/User=jetson/User=$(whoami)/g; \
     s|WorkingDirectory=.*|WorkingDirectory=$INSTALL_DIR|g; \
     s|ExecStart=.*|ExecStart=$VENV_DIR/bin/python $INSTALL_DIR/run_live.py|g; \
     s|EnvironmentFile=.*|EnvironmentFile=$INSTALL_DIR/.env|g" \
    "$INSTALL_DIR/deployment/crypto-trader.service" \
    | sudo tee /etc/systemd/system/$SERVICE_NAME.service > /dev/null

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"

sed "s/User=jetson/User=$(whoami)/g; \
     s|WorkingDirectory=.*|WorkingDirectory=$INSTALL_DIR|g; \
     s|ExecStart=.*|ExecStart=$VENV_DIR/bin/python -m streamlit run $INSTALL_DIR/dashboard/streamlit_app.py --server.address 0.0.0.0 --server.port 8501 --browser.gatherUsageStats false|g; \
     s|EnvironmentFile=.*|EnvironmentFile=$INSTALL_DIR/.env|g" \
    "$INSTALL_DIR/deployment/crypto-trader-dashboard.service" \
    | sudo tee /etc/systemd/system/$DASHBOARD_SERVICE_NAME.service > /dev/null

sudo systemctl enable "$DASHBOARD_SERVICE_NAME"
sudo cp "$INSTALL_DIR/deployment/crypto-trader-fan.service" /etc/systemd/system/$FAN_SERVICE_NAME.service
sudo systemctl enable "$FAN_SERVICE_NAME"
if [[ -f "$INSTALL_DIR/deployment/crypto-trader.logrotate" ]]; then
    sudo cp "$INSTALL_DIR/deployment/crypto-trader.logrotate" /etc/logrotate.d/crypto-trader
fi

echo "[8/8] Verifying application environment..."
python -c "import pandas, numpy, sqlalchemy, binance; print('  Core dependencies OK')"
python -c "from database.models import init_db; init_db(); print('  Database initialized')"
python -m deployment.jetson_ops health

echo ""
echo "=== Bootstrap complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit credentials:  nano $INSTALL_DIR/.env"
echo "  2. Start service:     sudo systemctl start $SERVICE_NAME"
echo "  3. Start dashboard:   sudo systemctl start $DASHBOARD_SERVICE_NAME"
echo "  4. Check trader:      sudo systemctl status $SERVICE_NAME --no-pager"
echo "  5. Check dashboard:   sudo systemctl status $DASHBOARD_SERVICE_NAME --no-pager"
echo "  6. Check fan:         sudo systemctl status $FAN_SERVICE_NAME --no-pager"
echo "  7. Follow trader:     journalctl -fu $SERVICE_NAME"
echo "  8. Follow dashboard:  journalctl -fu $DASHBOARD_SERVICE_NAME"
echo "  9. Follow fan:        journalctl -fu $FAN_SERVICE_NAME"
echo " 10. Visit dashboard:   http://$(hostname -I | awk '{print $1}'):8501"
