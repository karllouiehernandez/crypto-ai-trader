# Jetson VNC + Chromium Playwright Access

This note records the working remote-GUI approach validated on the Jetson Nano at `192.168.100.30`.

## Working Setup

- SSH remains the primary admin path:
  - `ssh jetson@192.168.100.30`
- Streamlit dashboard remains available directly from the LAN:
  - `http://192.168.100.30:8501`
- Reliable remote desktop uses TigerVNC, not GNOME Vino:
  - VNC address: `192.168.100.30:5901`
  - VNC password: same operator-provided VNC password used during setup
  - systemd service: `tigervnc-jetson.service`
- The old GNOME/Vino session may listen on `5900`, but it showed only the broken NVIDIA root surface in headless mode. Use `5901`.

## Why TigerVNC

GNOME Vino on the Jetson connected, but with no physical HDMI display it rendered a non-controllable NVIDIA splash/root surface. A separate TigerVNC virtual desktop on display `:1` provided a controllable Openbox desktop with `LXTerminal`.

## Useful Commands

Check VNC and trader services:

```bash
systemctl is-active tigervnc-jetson crypto-trader crypto-trader-dashboard crypto-trader-fan
ss -ltnp | egrep ':5901|:8501|:22'
```

Restart the VNC desktop:

```bash
sudo systemctl restart tigervnc-jetson
```

View the VNC desktop log:

```bash
tail -n 100 ~/.vnc/nano:1.log
```

## Chromium / Playwright

Playwright Chromium was installed on the Jetson and validated against the local Streamlit dashboard.

Chromium binary:

```bash
/home/jetson/.cache/ms-playwright/chromium-1208/chrome-linux/chrome
```

For headed browser execution inside VNC:

```bash
export DISPLAY=:1
/home/jetson/.cache/ms-playwright/chromium-1208/chrome-linux/chrome \
  --no-sandbox \
  --disable-gpu \
  --disable-dev-shm-usage \
  http://127.0.0.1:8501
```

For Playwright scripts, use Chromium with these launch args on Jetson:

```python
browser = p.chromium.launch(
    headless=False,
    args=["--no-sandbox", "--disable-dev-shm-usage"],
)
```

Set `DISPLAY=:1` before running headed Playwright:

```bash
DISPLAY=:1 python your_playwright_script.py
```

Headless Playwright was also validated:

```bash
cd ~/crypto_ai_trader
.venv/bin/python - <<'PY'
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
    page = browser.new_page()
    page.goto("http://127.0.0.1:8501", wait_until="domcontentloaded", timeout=30000)
    print(page.title())
    browser.close()
PY
```

Expected output includes:

```text
Streamlit
```

## Desktop Shortcut

A desktop launcher was created in the TigerVNC desktop:

```text
Crypto Trader Dashboard
```

It opens Chromium to:

```text
http://127.0.0.1:8501
```

## Operational Notes

- Use `192.168.100.30:5901` in RealVNC Viewer.
- Do not use `5900` for operator control unless GNOME/Vino is later fixed separately.
- This VNC setup does not replace the Streamlit LAN URL; it is for browser-based GUI access and headed Playwright/debug sessions directly on the Jetson.
- Keep `crypto-trader`, `crypto-trader-dashboard`, and `crypto-trader-fan` active during 30-day observation.
