# Extends the official Hummingbot image with the `ta` library
# that crypto_ai_trader_strategy.py depends on.
#
# Build: docker compose build
# Run:   docker compose up -d
FROM hummingbot/hummingbot:latest

# Install ta library into Hummingbot's conda environment
RUN conda run -n hummingbot pip install --no-cache-dir ta==0.11.0
