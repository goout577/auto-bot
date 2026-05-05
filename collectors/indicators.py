import pandas as pd
import ta


def _safe_last(series, default: float = 0.0) -> float:
    try:
        value = float(series.dropna().iloc[-1])
        return value
    except Exception:
        return default


def compute_indicators(df: pd.DataFrame) -> dict:
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]
    price = float(close.iloc[-1])

    try:
        rsi = round(_safe_last(ta.momentum.RSIIndicator(close, window=14).rsi(), 50.0), 1)
    except Exception:
        rsi = 50.0

    try:
        ema20 = round(_safe_last(ta.trend.EMAIndicator(close, window=20).ema_indicator(), price), 8)
        ema50 = round(_safe_last(ta.trend.EMAIndicator(close, window=50).ema_indicator(), price), 8)
    except Exception:
        ema20 = ema50 = round(price, 8)

    try:
        macd_hist = round(_safe_last(ta.trend.MACD(close).macd_diff(), 0.0), 8)
    except Exception:
        macd_hist = 0.0

    try:
        atr = _safe_last(ta.volatility.AverageTrueRange(high, low, close, window=14).average_true_range(), price * 0.01)
        atr_pct = round(atr / price * 100, 3) if price > 0 else 1.0
        atr = round(atr, 8)
    except Exception:
        atr = round(price * 0.01, 8)
        atr_pct = 1.0

    try:
        bb = ta.volatility.BollingerBands(close, window=20)
        upper = _safe_last(bb.bollinger_hband(), price)
        lower = _safe_last(bb.bollinger_lband(), price)
        bb_width = round((upper - lower) / price * 100, 2) if price > 0 else 2.0
    except Exception:
        bb_width = 2.0

    volume_now = float(volume.iloc[-1])
    volume_avg_20 = float(volume.tail(21).head(20).mean() or 0)
    volume_spike = round(volume_now / volume_avg_20, 2) if volume_avg_20 > 0 else 0.0

    lookback_5 = min(5, len(close) - 1)
    lookback_15 = min(15, len(close) - 1)
    change_5 = round((price / float(close.iloc[-lookback_5 - 1]) - 1) * 100, 3) if lookback_5 > 0 else 0.0
    change_15 = round((price / float(close.iloc[-lookback_15 - 1]) - 1) * 100, 3) if lookback_15 > 0 else 0.0

    high_20_prev = float(high.iloc[-21:-1].max()) if len(high) >= 21 else float(high.max())
    breakout_pct = round((price / high_20_prev - 1) * 100, 3) if high_20_prev > 0 else 0.0

    if price > ema20 > ema50:
        trend = "BULLISH"
    elif price < ema20 < ema50:
        trend = "BEARISH"
    else:
        trend = "NEUTRAL"

    return {
        "rsi": rsi,
        "ema20": ema20,
        "ema50": ema50,
        "macd_hist": macd_hist,
        "atr": atr,
        "atr_pct": atr_pct,
        "bb_width_pct": bb_width,
        "trend": trend,
        "volume_spike": volume_spike,
        "change_5": change_5,
        "change_15": change_15,
        "breakout_pct": breakout_pct,
    }
