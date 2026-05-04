from datetime import datetime, timezone


def build_context(equity: float, balance: float, positions: list,
                  candidates: list, sentiment: dict, news: list,
                  defi: dict, market: dict, risk_cfg: dict) -> str:
    ts = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    max_margin = equity * float(risk_cfg.get('max_position_pct', 30)) / 100
    max_lev = int(risk_cfg.get('max_leverage', 15))

    lines = [
        f"=== CRYPTO FUTURES AGENT — {ts} ===",
        "",
        "## 账户状态",
        f"- 总权益: ${equity:.2f} USDT",
        f"- 可用余额: ${balance:.2f} USDT",
        f"- 单笔最大保证金: ${max_margin:.2f} (最高 {max_lev}x 杠杆)",
        f"- 目标: 小资金快速翻倍，高风险偏好",
    ]

    if positions:
        lines.append(f"- 当前持仓: {len(positions)} 个")
        for p in positions:
            sym = p.get('symbol', '?')
            side = p.get('side', '?').upper()
            entry = float(p.get('entryPrice', 0) or 0)
            pnl = float(p.get('unrealizedPnl', 0) or 0)
            liq = float(p.get('liquidationPrice', 0) or 0)
            lines.append(f"  * {sym} {side} 开仓价=${entry:.4f} 浮盈=${pnl:+.2f} 强平价=${liq:.4f}")
    else:
        lines.append("- 当前持仓: 无")

    fg_val = sentiment.get('value', 50)
    fg_label = sentiment.get('label', 'Neutral')
    lines += ["", "## 市场情绪"]
    lines.append(f"- 恐贪指数: {fg_val}/100 ({fg_label})")

    tvl = defi.get('tvl_usd', 0)
    if tvl > 0:
        lines.append(f"- DeFi TVL: ${tvl/1e9:.1f}B ({defi.get('tvl_change_24h', 0):+.1f}% 24h)")

    mcap = market.get('total_mcap_usd', 0)
    if mcap > 0:
        lines.append(f"- 加密总市值: ${mcap/1e9:.0f}B ({market.get('mcap_change_24h', 0):+.1f}% 24h)")
        lines.append(f"- BTC 占比: {market.get('btc_dominance', 0):.1f}%")

    if news:
        lines += ["", "## 近期热点新闻"]
        for n in news[:5]:
            coins = ', '.join(n['coins']) if n['coins'] else '市场'
            lines.append(f"  [{n['sentiment'].upper()}] {n['title']} ({coins})")

    lines += ["", "## 动量候选标的（已过滤流动性和合约尺寸）"]

    if not candidates:
        lines.append("无候选标的通过筛选。")
    else:
        for i, c in enumerate(candidates, 1):
            sym = c['symbol']
            price = c.get('price', 0)
            chg = c.get('change_24h', 0)
            vol = c.get('volume_24h', 0)
            funding = c.get('funding_rate', 0)
            rsi = c.get('rsi', '-')
            atr_pct = c.get('atr_pct', '-')
            trend = c.get('trend', '-')
            ema20 = c.get('ema20', '-')
            ema50 = c.get('ema50', '-')
            macd = c.get('macd_hist', '-')
            bb = c.get('bb_width_pct', '-')
            atr = c.get('atr', '-')
            # 妖币信号
            oi = c.get('oi_usdt', 0)
            vol_oi = c.get('vol_oi_ratio', 0)
            neg_streak = c.get('funding_neg_streak', 0)
            avg_fund = c.get('avg_funding', funding)
            ls = c.get('ls_ratio', 1.0)
            risk = c.get('yaobi_risk', 'LOW')
            risk_tag = f"⚠️妖币风险:{risk}" if risk != 'LOW' else f"妖币风险:{risk}"
            squeeze_hint = ""
            if neg_streak >= 2 and avg_fund < -0.0002:
                squeeze_hint = " ← 逼空布局中(连续负费率，空头或将被爆仓)"
            elif avg_fund > 0.0005:
                squeeze_hint = " ← 费率转正，逼空可能接近尾声"
            lines += [
                f"",
                f"### {i}. {sym}  [{risk_tag}]",
                f"  价格: ${price:.4f} | 24h涨跌: {chg:+.2f}% | 成交量: ${vol/1e6:.0f}M | 资金费率: {funding*100:+.4f}%{squeeze_hint}",
                f"  OI: ${oi/1e6:.1f}M | Vol/OI: {vol_oi}x {'⚠️刷量嫌疑' if vol_oi > 15 else ''} | 多空比: {ls:.2f} {'(多头占优)' if ls > 1.2 else '(空头占优)' if ls < 0.8 else '(均衡)'}",
                f"  RSI: {rsi} | ATR: {atr_pct}% | 趋势: {trend}",
                f"  EMA20: {ema20} | EMA50: {ema50} | MACD柱: {macd}",
                f"  布林带宽: {bb}% | ATR绝对值: {atr}",
            ]

    lines += [
        "",
        "## 决策要求",
        "分析以上全部数据，做出一个最优决策：",
        "- open_long / open_short: 多个因素共振时果断开仓",
        "- close_all: 持仓出现明确反转信号时止损离场",
        "- hold: 无高确信机会时等待（默认）",
        "",
        "止损建议: 1.5x ATR（用 atr_pct 换算 sl_pct）",
        "止盈建议: 3x ATR（R:R ≥ 2:1）",
        "信心分 ≥ 7 才开仓，低于 6 强制 hold。",
        "目标是翻倍，不要过于保守，但要严格止损。",
    ]

    return '\n'.join(lines)
