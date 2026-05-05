from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_ms(iso_value: str | None) -> int | None:
    if not iso_value:
        return None
    try:
        return int(datetime.fromisoformat(iso_value).timestamp() * 1000)
    except Exception:
        return None


def register_open_trade(state: dict, decision: dict, result: dict, candidates: list[dict]) -> None:
    if result.get("status") != "opened":
        return
    symbol = result.get("symbol") or decision.get("symbol")
    if not symbol:
        return
    candidate = next((c for c in candidates if c.get("symbol") == symbol), {})
    trade_key = str(result.get("order_id") or f"{symbol}:{_now_iso()}")
    state.setdefault("open_trades", {})[trade_key] = {
        "trade_key": trade_key,
        "symbol": symbol,
        "action": decision.get("action"),
        "opened_at": _now_iso(),
        "entry_price": result.get("price") or decision.get("entry_price"),
        "stop_loss": decision.get("stop_loss"),
        "take_profit_1": decision.get("take_profit_1"),
        "take_profit_2": decision.get("take_profit_2"),
        "take_profit_3": decision.get("take_profit_3"),
        "leverage": decision.get("leverage"),
        "size_pct": decision.get("size_pct"),
        "margin_usdt": result.get("margin_usdt"),
        "contracts": result.get("contracts"),
        "yaobi_score": decision.get("yaobi_score"),
        "candidate_snapshot": candidate,
        "decision": decision,
        "result": result,
        "reviewed": False,
    }


def detect_closed_losses(exchange, positions: list[dict], state: dict) -> list[dict]:
    open_trades = state.setdefault("open_trades", {})
    active_symbols = {p.get("symbol") for p in positions}
    losses = []

    for trade_key, trade in list(open_trades.items()):
        symbol = trade.get("symbol")
        if not symbol or symbol in active_symbols:
            continue

        closed = exchange.get_closed_position_pnl(symbol, _to_ms(trade.get("opened_at")))
        if not closed:
            continue

        realized_pnl = float(closed.get("realized_pnl") or 0)
        finished = {
            **trade,
            **closed,
            "trade_key": trade_key,
            "closed_at": _now_iso(),
        }
        state.setdefault("closed_trades", []).append(finished)
        state["closed_trades"] = state["closed_trades"][-500:]
        del open_trades[trade_key]

        if realized_pnl < 0 and not trade.get("reviewed"):
            losses.append(finished)

    return losses
