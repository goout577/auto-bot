from loguru import logger

from collectors.indicators import compute_indicators
from core.exchange import OKXExchange


def _score_range(value: float, low: float, high: float, points: int) -> int:
    if value <= low:
        return 0
    if value >= high:
        return points
    return int((value - low) / (high - low) * points)


def _classify_stage(row: dict) -> str:
    if row["avg_funding"] > 0.0005 and row["change_24h"] > 25:
        return "末端风险"
    if row["change_15"] > 3.0 and row["volume_spike"] >= 2.5:
        return "逼空加速"
    if row["change_5"] > 1.0 and row["volume_spike"] >= 2.0 and row["oi_change_pct"] > 0:
        return "逼空启动"
    if row["breakout_pct"] > 0 and row["volume_spike"] < 1.2:
        return "假突破"
    return "观察"


def _yaobi_score(row: dict) -> int:
    score = 0

    avg_funding = row["avg_funding"]
    if avg_funding < -0.0003:
        score += 25
    elif avg_funding < -0.0001:
        score += 18
    elif avg_funding < 0:
        score += 10

    score += _score_range(row["volume_spike"], 1.2, 3.0, 20)
    score += _score_range(row["oi_change_pct"], 0.5, 8.0, 20)

    if row["change_5"] > 0 and row["change_15"] > 0:
        score += _score_range(row["change_15"], 0.5, 5.0, 15)

    score += _score_range(row["atr_pct"], 1.0, 6.0, 10)

    ls_ratio = row["ls_ratio"]
    if ls_ratio < 0.65:
        score += 10
    elif ls_ratio < 0.85:
        score += 7
    elif ls_ratio < 1.0:
        score += 4

    if row["stage"] == "末端风险":
        score -= 20
    if row["stage"] == "假突破":
        score -= 10

    return max(0, min(100, score))


def fetch_market_snapshots(
    exchange: OKXExchange,
    candidates: list,
    trading_cfg: dict,
    screener_cfg: dict | None = None,
) -> list:
    screener_cfg = screener_cfg or {}
    timeframe = trading_cfg.get("timeframe", "5m")
    confirm_timeframe = trading_cfg.get("confirm_timeframe", "15m")
    limit = int(trading_cfg.get("ohlcv_limit", 120))
    min_score = int(screener_cfg.get("min_yaobi_score", 55))
    ai_top_n = int(screener_cfg.get("ai_top_n", 20))

    enriched = []
    for c in candidates:
        symbol = c["symbol"]
        try:
            df = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            if len(df) < 55:
                logger.debug(f"{symbol} K线不足，跳过")
                continue

            indicators = compute_indicators(df)

            try:
                confirm_df = exchange.fetch_ohlcv(symbol, timeframe=confirm_timeframe, limit=80)
                confirm_indicators = compute_indicators(confirm_df)
            except Exception:
                confirm_indicators = {}

            funding = exchange.get_funding_rate(symbol)
            funding_history = exchange.get_funding_rate_history(symbol, limit=5)
            avg_funding = sum(funding_history) / len(funding_history) if funding_history else funding
            neg_streak = sum(1 for r in funding_history if r < -0.0001)

            oi = exchange.get_open_interest(symbol)
            oi_history = exchange.get_open_interest_history(symbol, timeframe=timeframe, limit=6)
            oi_change_pct = 0.0
            if len(oi_history) >= 2 and oi_history[0] > 0:
                oi_change_pct = round((oi_history[-1] / oi_history[0] - 1) * 100, 3)

            vol_24h = c.get("volume_24h", 0)
            vol_oi_ratio = round(vol_24h / oi, 1) if oi > 0 else 0
            if vol_oi_ratio > 500:
                vol_oi_ratio = 0

            row = {
                **c,
                **indicators,
                "confirm_trend": confirm_indicators.get("trend", "UNKNOWN"),
                "confirm_change_15": confirm_indicators.get("change_15", 0),
                "funding_rate": funding,
                "funding_neg_streak": neg_streak,
                "avg_funding": avg_funding,
                "oi_usdt": oi,
                "oi_change_pct": oi_change_pct,
                "vol_oi_ratio": vol_oi_ratio,
                "ls_ratio": exchange.get_long_short_ratio(symbol),
            }
            row["stage"] = _classify_stage(row)
            row["yaobi_score"] = _yaobi_score(row)
            row["passed_min_score"] = row["yaobi_score"] >= min_score
            row["yaobi_risk"] = "HIGH" if row["yaobi_score"] >= 75 else ("MED" if row["yaobi_score"] >= 55 else "LOW")
            enriched.append(row)
        except Exception as e:
            logger.warning(f"{symbol} 深度数据获取失败: {e}")

    enriched.sort(key=lambda x: x["yaobi_score"], reverse=True)
    passed = [c for c in enriched if c["passed_min_score"]]
    shown = enriched[:ai_top_n]
    logger.info(f"妖币深度扫描完成：展示 {len(shown)} 个，达到开仓线 {len(passed)} 个，交给规则引擎前 {ai_top_n} 个")
    for c in shown:
        flag = "可开仓观察" if c["passed_min_score"] else "仅记录观察"
        logger.info(
            f"候选 {c['symbol']} 分={c['yaobi_score']} {flag} 阶段={c['stage']} "
            f"5m={c['change_5']:+.2f}% 15m={c['change_15']:+.2f}% "
            f"量={c['volume_spike']}x OI={c['oi_change_pct']:+.2f}% 费率={c['avg_funding']*100:+.4f}%"
        )
    return shown
