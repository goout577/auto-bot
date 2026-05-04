import pandas as pd
import ta


def compute_indicators(df: pd.DataFrame) -> dict:
    close = df['close']
    high = df['high']
    low = df['low']
    price = float(close.iloc[-1])

    try:
        rsi = round(float(ta.momentum.RSIIndicator(close, window=14).rsi().iloc[-1]), 1)
    except Exception:
        rsi = 50.0

    try:
        ema20 = round(float(ta.trend.EMAIndicator(close, window=20).ema_indicator().iloc[-1]), 6)
        ema50 = round(float(ta.trend.EMAIndicator(close, window=50).ema_indicator().iloc[-1]), 6)
    except Exception:
        ema20 = ema50 = round(price, 6)

    try:
        macd_hist = round(float(ta.trend.MACD(close).macd_diff().iloc[-1]), 6)
    except Exception:
        macd_hist = 0.0

    try:
        atr = float(ta.volatility.AverageTrueRange(high, low, close, window=14).average_true_range().iloc[-1])
        atr_pct = round(atr / price * 100, 3)
        atr = round(atr, 6)
    except Exception:
        atr = round(price * 0.01, 6)
        atr_pct = 1.0

    try:
        bb = ta.volatility.BollingerBands(close, window=20)
        bb_width = round(
            (float(bb.bollinger_hband().iloc[-1]) - float(bb.bollinger_lband().iloc[-1])) / price * 100, 2
        )
    except Exception:
        bb_width = 2.0

    if price > ema20 > ema50:
        trend = 'BULLISH'
    elif price < ema20 < ema50:
        trend = 'BEARISH'
    else:
        trend = 'NEUTRAL'

    return {
        'rsi': rsi,
        'ema20': ema20,
        'ema50': ema50,
        'macd_hist': macd_hist,
        'atr': atr,
        'atr_pct': atr_pct,
        'bb_width_pct': bb_width,
        'trend': trend,
    }
