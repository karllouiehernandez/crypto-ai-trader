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
git pull
sudo systemctl restart crypto-trader
```
