def _to_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _hold(reason: str, confidence: int = 0) -> dict:
    return {
        "action": "hold",
        "symbol": "",
        "stage": "观察",
        "entry_price": None,
        "stop_loss": None,
        "take_profit_1": None,
        "take_profit_2": None,
        "take_profit_3": None,
        "leverage": 5,
        "size_pct": 10,
        "confidence": confidence,
        "reasoning": reason,
        "decision_source": "rules",
    }


def _confidence(score: float) -> int:
    if score >= 85:
        return 9
    if score >= 75:
        return 8
    if score >= 65:
        return 7
    if score >= 55:
        return 6
    return 4


def _leverage(score: float, max_leverage: int) -> int:
    if score >= 80:
        return min(max_leverage, 8)
    if score >= 70:
        return min(max_leverage, 6)
    return min(max_leverage, 5)


def build_rule_trade_card(candidates: list[dict], risk_cfg: dict, screener_cfg: dict) -> dict:
    min_score = int(screener_cfg.get("min_yaobi_score", 55))
    min_rr = _to_float(risk_cfg.get("min_reward_r", 1.5), 1.5)
    min_sl_pct = _to_float(risk_cfg.get("min_stop_loss_pct", 0.3), 0.3)
    max_sl_pct = _to_float(risk_cfg.get("max_stop_loss_pct", 12.0), 12.0)
    max_leverage = int(risk_cfg.get("max_leverage", 8))
    size_pct = _to_float(risk_cfg.get("position_margin_pct", 10.0), 10.0)

    tradable = [
        c for c in candidates
        if c.get("passed_min_score")
        and _to_float(c.get("yaobi_score")) >= min_score
        and c.get("stage") not in {"末端风险", "假突破"}
    ]
    if not tradable:
        return _hold(f"没有候选币达到开仓线 {min_score}，本轮只记录观察。")

    candidate = max(tradable, key=lambda c: _to_float(c.get("yaobi_score")))
    price = _to_float(candidate.get("price"))
    score = _to_float(candidate.get("yaobi_score"))
    atr_pct = _to_float(candidate.get("atr_pct"), 1.0)
    if price <= 0:
        return _hold(f"{candidate.get('symbol', '-')} 没有有效价格，放弃开仓。")

    risk_pct = max(min_sl_pct, min(max_sl_pct, max(atr_pct * 1.4, 1.0)))
    entry = price
    stop_loss = entry * (1 - risk_pct / 100)
    take_profit_1 = entry + (entry - stop_loss) * (min_rr + 0.25)
    take_profit_2 = entry + (entry - stop_loss) * (min_rr + 1.0)
    take_profit_3 = entry + (entry - stop_loss) * (min_rr + 2.0)

    rr = (take_profit_1 - entry) / (entry - stop_loss) if entry > stop_loss else 0
    if rr < min_rr:
        return _hold(
            f"{candidate['symbol']} 达到开仓线，但按当前波动计算第一止盈盈亏比 {rr:.2f} < {min_rr:.2f}，等待。"
        )

    return {
        "action": "open_long",
        "symbol": candidate["symbol"],
        "stage": candidate.get("stage", "逼空启动"),
        "entry_price": round(entry, 10),
        "stop_loss": round(stop_loss, 10),
        "take_profit_1": round(take_profit_1, 10),
        "take_profit_2": round(take_profit_2, 10),
        "take_profit_3": round(take_profit_3, 10),
        "leverage": _leverage(score, max_leverage),
        "size_pct": size_pct,
        "confidence": _confidence(score),
        "reasoning": (
            f"规则选择 {candidate['symbol']}：妖币分 {score:.0f} 达到开仓线，阶段 {candidate.get('stage', '观察')}，"
            f"资金费率 {candidate.get('avg_funding', 0) * 100:+.4f}%，"
            f"5m/15m 涨幅 {candidate.get('change_5', 0):+.2f}%/{candidate.get('change_15', 0):+.2f}%，"
            f"放量 {candidate.get('volume_spike', 0)}x，OI 变化 {candidate.get('oi_change_pct', 0):+.2f}%。"
        ),
        "decision_source": "rules",
        "yaobi_score": score,
    }
