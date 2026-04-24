# Jetson Nano Deployment

Runs the crypto AI trader as a persistent systemd service on Jetson Nano 4GB.

## Prerequisites

- Jetson Nano 4GB (original, not Orin) with Ubuntu 18.04 or 20.04
- Python 3.10+ (`sudo apt install python3.10 python3.10-venv`)
- Internet access to Binance API

## First-time Setup

```bash
# 1. Set up swap (as root) — required for stability
sudo bash deployment/setup_swap.sh

# 2. Install the trader (as your normal user)
bash deployment/install.sh

# 3. Edit credentials
nano .env

# 4. Start the service
sudo systemctl start crypto-trader

# 5. Watch logs
journalctl -fu crypto-trader
```

The installer is intentionally non-destructive:
- it does not overwrite an existing `.env`
- it does not reset the SQLite database
- it does not change active paper/live artifact settings
- it installs a systemd unit, an optional logrotate template, initializes missing DB tables, and prints a deployment health report

## Flash-Drive Deployment

If you already have the repo on a Windows machine and want to move it to Jetson Nano by USB instead of `git clone`, use the repo-root bundle script:

```bat
prepare_jetson_flash_drive.bat E:\
```

That creates:

```text
E:\crypto_ai_trader_bundle
```

The bundle excludes local-only state such as:
- `.env`
- `.venv`
- `reports/`
- `backups/`
- runtime eval files
- `knowledge/experiment_log.md`

On the Jetson:

```bash
# after inserting the flash drive and finding the mount path
bash /media/$USER/<usb_name>/crypto_ai_trader_bundle/deployment/install_from_bundle.sh /media/$USER/<usb_name>/crypto_ai_trader_bundle
```

This installs from the copied bundle instead of cloning from GitHub and preserves the same non-destructive guarantees as `deployment/install.sh`.

## One-Time SSH + SFTP Setup From Windows

If you want direct remote access to the Jetson aside from CI/CD, use the repo-root batch helper:

```bat
setup_jetson_remote_access.bat 192.168.1.50 jetson 22
```

What it does:
- creates a local `ed25519` SSH key if you do not already have one
- copies a Jetson-side helper script to `/tmp`
- installs/enables `openssh-server` on the Jetson
- prepares `~/.ssh/authorized_keys`
- appends your Windows public key to the Jetson
- verifies passwordless SSH access

What it does not do:
- change the trader runtime
- modify `.env`
- start live trading
- change paper/live artifact settings

After it completes:

```bash
ssh -p 22 jetson@192.168.1.50
sftp -P 22 jetson@192.168.1.50
```

SFTP rides on the same OpenSSH service, so no separate SFTP server is required.

## Health Check

Run this after install, after every update, and before leaving the Jetson unattended:

```bash
cd ~/crypto_ai_trader
.venv/bin/python -m deployment.jetson_ops health
```

For automation:

```bash
.venv/bin/python -m deployment.jetson_ops health --json
.venv/bin/python -m deployment.jetson_ops health --strict
```

`--strict` exits non-zero when required readiness checks fail.

If health reports a reviewed artifact hash mismatch after an intentional code
review/update, acknowledge the exact artifact explicitly:

```bash
.venv/bin/python -m deployment.jetson_ops repin-artifact <artifact_id>
.venv/bin/python -m deployment.jetson_ops repin-artifact <artifact_id> --apply
```

Do not repin unknown strategy changes. Review the file first.

## Windows One-Time Bootstrap

For a Windows dev machine, run the repo-root batch installer once:

```bat
install_once.bat
```

What it does:
- creates `.venv` if missing
- installs `requirements.txt` and `requirements-dev.txt`
- copies `.env.example` to `.env` only if `.env` does not already exist
- initializes database tables without resetting existing data
- installs the Playwright Chromium browser used by the UI agent

What it does not do:
- overwrite `.env`
- clear the database
- change active paper/live artifact settings

After it finishes, use `run_all.ps1` or launch the dashboard/runtime manually from `.venv`.

## Daily Operations

```bash
sudo systemctl status crypto-trader    # health check
sudo systemctl restart crypto-trader   # restart
sudo systemctl stop crypto-trader      # stop
journalctl -fu crypto-trader           # follow live logs
journalctl -u crypto-trader --since "1 hour ago"  # recent logs
```

## Backups And Restore

Create a non-destructive state backup before upgrades or experiments:

```bash
cd ~/crypto_ai_trader
.venv/bin/python -m deployment.jetson_ops backup
```

This copies the current SQLite DB and registered strategy files into `backups/`.
It does not copy `.env` unless you explicitly add `--include-env`.

Dry-run a restore first:

```bash
.venv/bin/python -m deployment.jetson_ops restore backups/<backup_dir>/manifest.json
```

Apply a restore only after reading the dry-run operation list:

```bash
.venv/bin/python -m deployment.jetson_ops restore backups/<backup_dir>/manifest.json --apply
```

Applying a restore first creates a fresh pre-restore backup, then copies the DB and backed-up strategy files into place.

## Log Retention

The default service logs to journald:

```bash
journalctl -fu crypto-trader
sudo journalctl --vacuum-time=14d
```

The installer also places `deployment/crypto-trader.logrotate` at `/etc/logrotate.d/crypto-trader` for optional file logs under `~/crypto_ai_trader/logs/`.

## Memory Monitoring

```bash
free -h                                # RAM + swap usage
systemctl show crypto-trader -p MemoryCurrent  # current RSS
```

If RSS consistently exceeds 700MB, reduce `MAX_SYMBOLS=1` and restart.

## LLM on Jetson

LLM is **off by default** (`LLM_ENABLED=false`). To enable:

1. Subscribe to [OpenRouter](https://openrouter.ai) (pay-per-use, no GPU required)
2. In `.env`:
   ```
   LLM_ENABLED=true
   LLM_PROVIDER=openrouter
   OPENROUTER_API_KEY=your_key_here
   ```
3. `sudo systemctl restart crypto-trader`

The self-learning loop (trade critiquer + 24h backtest analysis) activates automatically.
All inference is remote — no extra RAM on device.

## Remote Agent Access (MCP Server)

The MCP server lets Claude Code and Codex query live trading data from your dev machine.

**On Jetson (start MCP server):**
```bash
cd ~/crypto_ai_trader
MCP_TRANSPORT=sse MCP_PORT=8765 .venv/bin/python run_mcp_server.py
```

Or as a background service — add to `.env`:
```
MCP_TRANSPORT=sse
MCP_PORT=8765
```
Then run: `nohup .venv/bin/python run_mcp_server.py &`

**On your dev machine (SSH tunnel):**
```bash
ssh -L 8765:localhost:8765 your_user@<jetson_ip>
```

**In your dev machine `.mcp.json`** (update to SSE transport):
```json
{
  "mcpServers": {
    "crypto-trader-jetson": {
      "transport": "sse",
      "url": "http://localhost:8765/sse"
    }
  }
}
```

Claude Code will now list live Jetson data as MCP tools.

## Telegram Commands

Once the trader is running, send commands to your bot:

| Command | Description |
|---------|-------------|
| `/status` | Portfolio equity, active strategy, halt state |
| `/trades 5` | Last 5 trades with P&L |
| `/equity` | Return % and drawdown |
| `/halt` | Stop trading remotely |
| `/resume` | Resume trading |
| `/backtest BTCUSDT 2024-01-01 2024-03-31` | Run backtest |
| `/focus` | Latest market focus candidates |
| `/help` | All commands |

## Updating

```bash
cd ~/crypto_ai_trader
.venv/bin/python -m deployment.jetson_ops backup
git pull
.venv/bin/python -m deployment.jetson_ops health
sudo systemctl restart crypto-trader
```
