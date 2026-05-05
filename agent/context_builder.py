from datetime import datetime, timezone


def build_context(
    equity: float,
    balance: float,
    positions: list,
    candidates: list,
    risk_cfg: dict,
    state: dict | None = None,
) -> str:
    state = state or {}
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    size_pct = float(risk_cfg.get("position_margin_pct", 10))
    max_pos = int(risk_cfg.get("max_open_positions", 10))
    max_lev = int(risk_cfg.get("max_leverage", 8))
    daily_dd = float(risk_cfg.get("daily_max_drawdown_pct", 20))

    lines = [
        f"=== OKX 测试盘妖币逼空机器人 | {ts} ===",
        "",
        "## 账户状态",
        f"- 总权益: ${equity:.2f} USDT",
        f"- 可用保证金: ${balance:.2f} USDT",
        f"- 当前仓位: {len(positions)} / {max_pos}",
        f"- 单仓保证金: {size_pct:.1f}%",
        f"- 最高杠杆: {max_lev}x",
        f"- 每日最大回撤刹车: {daily_dd:.1f}%",
        f"- 今日起始权益: ${float(state.get('day_start_equity') or equity):.2f}",
        f"- 今日最低权益: ${float(state.get('day_low_equity') or equity):.2f}",
        "",
        "## 当前持仓",
    ]

    if not positions:
        lines.append("- 无")
    else:
        for p in positions:
            lines.append(
                f"- {p.get('symbol')} {p.get('side')} 开仓 {p.get('entry_price')} "
                f"标记 {p.get('mark_price')} 浮盈亏 {p.get('unrealized_pnl')}"
            )

    lines += ["", "## 妖币候选榜"]
    if not candidates:
        lines.append("- 本轮没有候选币完成深度扫描。")
    else:
        for i, c in enumerate(candidates, 1):
            passed = "达到开仓线" if c.get("passed_min_score") else "未达开仓线，仅观察"
            lines += [
                "",
                f"### {i}. {c['symbol']} | 妖币分 {c.get('yaobi_score', 0)} | {passed} | 阶段 {c.get('stage', '观察')}",
                f"- 价格: {c.get('price')} | 24h: {c.get('change_24h', 0):+.2f}% | 5m: {c.get('change_5', 0):+.2f}% | 15m: {c.get('change_15', 0):+.2f}%",
                f"- 成交额: ${c.get('volume_24h', 0)/1e6:.1f}M | 放量: {c.get('volume_spike', 0)}x | ATR: {c.get('atr_pct', 0)}%",
                f"- 资金费率: {c.get('funding_rate', 0)*100:+.4f}% | 平均费率: {c.get('avg_funding', 0)*100:+.4f}% | 连续负费率: {c.get('funding_neg_streak', 0)}",
                f"- OI: ${c.get('oi_usdt', 0)/1e6:.1f}M | OI变化: {c.get('oi_change_pct', 0):+.2f}% | 多空比: {c.get('ls_ratio', 1):.2f}",
                f"- 趋势: {c.get('trend', '-')} | 确认周期趋势: {c.get('confirm_trend', '-')}",
            ]

    lines += [
        "",
        "## 决策硬规则",
        "- 只有候选币标注“达到开仓线”时，才允许 open_long/open_short。",
        "- 未达开仓线只能 hold。",
        "- 主做逼空追多，不要轻易开空。",
        "- 末端风险、假突破、止损止盈不合理时必须 hold。",
        "- 开仓必须给明确 entry_price、stop_loss、take_profit_1。",
        "- 第一止盈必须满足风控里的最低盈亏比。",
        "- 用中文给出简短理由。",
    ]
    return "\n".join(lines)


def format_trade_card(decision: dict, result: dict | None = None) -> str:
    result = result or {}
    lines = [
        "【OKX测试盘LLM交易卡】",
        f"来源: {decision.get('decision_source', 'llm')}",
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
