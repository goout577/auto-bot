from datetime import datetime, timezone


def _to_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _cooldown_key(symbol: str, action: str) -> str:
    return f"{symbol}:{action}"


def validate_decision(decision: dict, equity: float, positions: list, risk_cfg: dict, state: dict | None = None) -> tuple[bool, str]:
    state = state or {}
    action = decision.get("action", "hold")

    if action == "hold":
        return True, "hold"

    if action == "close_all":
        if not positions:
            return False, "系统想全平，但当前没有持仓"
        return True, "ok"

    if action not in ("open_long", "open_short"):
        return False, f"未知动作: {action}"

    day_start = _to_float(state.get("day_start_equity"), equity)
    daily_dd = _to_float(risk_cfg.get("daily_max_drawdown_pct", 20), 20)
    if day_start > 0:
        drawdown_pct = (day_start - equity) / day_start * 100
        if drawdown_pct >= daily_dd:
            return False, f"今日回撤 {drawdown_pct:.2f}% 已达到 {daily_dd:.2f}%，停止开新仓"

    confidence = int(decision.get("confidence", 0))
    min_conf = int(risk_cfg.get("min_confidence", 6))
    if confidence < min_conf:
        return False, f"信心 {confidence} < 最低要求 {min_conf}"

    if equity < _to_float(risk_cfg.get("min_balance_usdt", 8.0), 8.0):
        return False, f"权益 ${equity:.2f} 低于最低余额 ${risk_cfg.get('min_balance_usdt', 8.0)}"

    max_pos = int(risk_cfg.get("max_open_positions", 10))
    if len(positions) >= max_pos:
        return False, f"已有 {len(positions)} 个仓位，上限 {max_pos}"

    symbol = decision.get("symbol")
    if not symbol:
        return False, "开仓缺少币种"

    cooldown_minutes = int(risk_cfg.get("same_symbol_cooldown_minutes", 30))
    cooldowns = state.get("cooldowns", {})
    last_time = cooldowns.get(_cooldown_key(symbol, action))
    if last_time:
        try:
            elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(last_time)).total_seconds() / 60
            if elapsed < cooldown_minutes:
                return False, f"{symbol} 同方向冷却中，还需 {cooldown_minutes - elapsed:.1f} 分钟"
        except Exception:
            pass

    leverage = int(decision.get("leverage", 5))
    max_lev = int(risk_cfg.get("max_leverage", 8))
    if leverage > max_lev:
        return False, f"杠杆 {leverage}x 超过上限 {max_lev}x"
    if leverage < 1:
        return False, "杠杆不能小于 1x"

    size_pct = _to_float(decision.get("size_pct", risk_cfg.get("position_margin_pct", 10)), 0)
    max_position_pct = _to_float(risk_cfg.get("position_margin_pct", 10), 10)
    if size_pct <= 0:
        return False, "仓位比例必须大于 0"
    if size_pct > max_position_pct:
        return False, f"仓位比例 {size_pct}% 超过单仓上限 {max_position_pct}%"

    entry = _to_float(decision.get("entry_price"))
    sl = _to_float(decision.get("stop_loss"))
    tp1 = _to_float(decision.get("take_profit_1"))
    if entry <= 0 or sl <= 0 or tp1 <= 0:
        return False, "开仓必须有明确的建议价、止损价、止盈价"

    if action == "open_long":
        if not (sl < entry < tp1):
            return False, "开多价格关系错误，必须是 止损 < 开仓 < 止盈"
        risk_dist = entry - sl
        reward_dist = tp1 - entry
    else:
        if not (tp1 < entry < sl):
            return False, "开空价格关系错误，必须是 止盈 < 开仓 < 止损"
        risk_dist = sl - entry
        reward_dist = entry - tp1

    risk_pct = risk_dist / entry * 100
    reward_r = reward_dist / risk_dist if risk_dist > 0 else 0
    min_sl_pct = _to_float(risk_cfg.get("min_stop_loss_pct", 0.3), 0.3)
    max_sl_pct = _to_float(risk_cfg.get("max_stop_loss_pct", 12), 12)
    min_rr = _to_float(risk_cfg.get("min_reward_r", 1.5), 1.5)
    if risk_pct < min_sl_pct:
        return False, f"止损太近 {risk_pct:.2f}% < {min_sl_pct:.2f}%"
    if risk_pct > max_sl_pct:
        return False, f"止损太远 {risk_pct:.2f}% > {max_sl_pct:.2f}%"
    if reward_r < min_rr:
        return False, f"第一止盈盈亏比 {reward_r:.2f} < {min_rr:.2f}"

    return True, "ok"
