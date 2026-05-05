from loguru import logger

from core.exchange import OKXExchange


def execute(decision: dict, exchange: OKXExchange, risk_cfg: dict) -> dict:
    action = decision.get("action")

    if action == "hold":
        return {"status": "hold"}

    if action == "close_all":
        exchange.close_all_positions()
        return {"status": "closed_all"}

    if action in ("open_long", "open_short"):
        symbol = decision["symbol"]
        leverage = int(decision.get("leverage", risk_cfg.get("max_leverage", 5)))
        size_pct = float(decision.get("size_pct", risk_cfg.get("position_margin_pct", 10)))
        sl_price = float(decision["stop_loss"])
        tp_price = float(decision["take_profit_1"])

        balance = exchange.get_free_balance()
        margin_usdt = balance * size_pct / 100
        notional = margin_usdt * leverage

        ticker = exchange.fetch_ticker(symbol)
        actual_price = float(ticker["last"])
        side = "buy" if action == "open_long" else "sell"

        ct_val = exchange.get_contract_size(symbol)
        min_qty = exchange.get_min_contracts(symbol)
        contracts = max(notional / (ct_val * actual_price), min_qty)

        exchange.set_leverage_isolated(symbol, leverage)

        logger.info(
            f"市价开仓 {action} {symbol}: 建议价={float(decision['entry_price']):.8f} "
            f"实际价={actual_price:.8f} 保证金=${margin_usdt:.2f} 名义=${notional:.2f} "
            f"SL={sl_price:.8f} TP1={tp_price:.8f} 杠杆={leverage}x"
        )

        order_bundle = exchange.place_order_with_sltp(symbol, side, contracts, sl_price, tp_price)
        entry_order = order_bundle["entry_order"]
        return {
            "status": "opened",
            "action": action,
            "symbol": symbol,
            "contracts": order_bundle["contracts"],
            "suggested_entry": float(decision["entry_price"]),
            "price": actual_price,
            "sl": sl_price,
            "tp1": tp_price,
            "tp2": decision.get("take_profit_2"),
            "tp3": decision.get("take_profit_3"),
            "leverage": leverage,
            "size_pct": size_pct,
            "margin_usdt": margin_usdt,
            "order_id": entry_order.get("id"),
            "protection_order_id": order_bundle["protection_order"].get("id"),
        }

    return {"status": "unknown", "action": action}
