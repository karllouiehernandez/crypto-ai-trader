# crypto_ai_trader/strategy/ta_features.py
import pandas as pd
import ta

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    out["ma_21"]  = ta.trend.sma_indicator(out.close, window=21)
    out["ma_55"]  = ta.trend.sma_indicator(out.close, window=55)
    macd          = ta.trend.MACD(out.close)
    out["macd"]   = macd.macd()
    out["macd_s"] = macd.macd_signal()
    out["rsi_14"]      = ta.momentum.RSIIndicator(out.close, window=14).rsi()
    bb                 = ta.volatility.BollingerBands(out.close, window=20)
    out["bb_hi"]       = bb.bollinger_hband()
    out["bb_lo"]       = bb.bollinger_lband()
    out["bb_width"]    = bb.bollinger_wband()
    out["ema_200"]     = ta.trend.EMAIndicator(out.close, window=200).ema_indicator()
    out["volume_ma_20"] = ta.trend.sma_indicator(out.volume, window=20)
    adx                = ta.trend.ADXIndicator(out.high, out.low, out.close, window=14)
    out["adx_14"]      = adx.adx()
    return out.dropna()
