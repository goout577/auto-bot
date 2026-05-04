def validate_decision(decision: dict, equity: float, positions: list, risk_cfg: dict) -> tuple[bool, str]:
    action = decision.get('action', 'hold')

    if action == 'hold':
        return True, 'hold'

    if action == 'close_all':
        if not positions:
            return False, 'close_all 但当前无持仓'
        return True, 'ok'

    if action in ('open_long', 'open_short'):
        confidence = int(decision.get('confidence', 0))
        min_conf = int(risk_cfg.get('min_confidence', 6))
        if confidence < min_conf:
            return False, f'信心分 {confidence} < 最低要求 {min_conf}'

        if equity < float(risk_cfg.get('min_balance_usdt', 8.0)):
            return False, f'权益 ${equity:.2f} 低于最低余额 ${risk_cfg["min_balance_usdt"]}'

        max_pos = int(risk_cfg.get('max_open_positions', 1))
        if len(positions) >= max_pos:
            return False, f'已有 {len(positions)} 个持仓，上限 {max_pos}'

        leverage = int(decision.get('leverage', 5))
        if leverage > int(risk_cfg.get('max_leverage', 15)):
            return False, f'杠杆 {leverage}x 超过上限 {risk_cfg["max_leverage"]}x'

        size_pct = float(decision.get('size_pct', 0))
        if size_pct > float(risk_cfg.get('max_position_pct', 30)):
            return False, f'仓位比例 {size_pct}% 超过上限 {risk_cfg["max_position_pct"]}%'

        if not decision.get('symbol'):
            return False, '未指定交易标的'

        if not decision.get('sl_pct') or not decision.get('tp_pct'):
            return False, '缺少止损或止盈参数'

        return True, 'ok'

    return False, f'未知指令: {action}'
