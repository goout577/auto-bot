def format_trade_card(decision: dict, result: dict | None = None) -> str:
    result = result or {}
    lines = [
        "【OKX测试盘规则交易卡】",
        f"来源: {decision.get('decision_source', 'rules')}",
        f"动作: {decision.get('action', 'hold')}",
        f"币种: {decision.get('symbol', '-') or '-'}",
        f"阶段: {decision.get('stage', '观察')}",
        f"建议开仓价: {decision.get('entry_price', '-')}",
        f"实际开仓价: {result.get('price', '-')}",
        f"止损: {decision.get('stop_loss', '-')}",
        f"止盈1: {decision.get('take_profit_1', '-')}",
        f"止盈2: {decision.get('take_profit_2', '-')}",
        f"止盈3: {decision.get('take_profit_3', '-')}",
        f"杠杆: {decision.get('leverage', '-')}x",
        f"仓位: {decision.get('size_pct', '-')}%",
        f"信心: {decision.get('confidence', '-')}/10",
        f"理由: {decision.get('reasoning', '')}",
    ]
    return "\n".join(lines)
