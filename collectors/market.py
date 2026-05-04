from loguru import logger
from core.exchange import OKXExchange
from collectors.indicators import compute_indicators


def fetch_market_snapshots(exchange: OKXExchange, candidates: list, trading_cfg: dict) -> list:
    timeframe = trading_cfg.get('timeframe', '15m')
    limit = int(trading_cfg.get('ohlcv_limit', 100))

    enriched = []
    for c in candidates:
        symbol = c['symbol']
        try:
            df = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            if len(df) < 55:
                logger.debug(f"{symbol} K线数据不足，跳过")
                continue
            indicators = compute_indicators(df)
            funding = exchange.get_funding_rate(symbol)

            # 妖币检测信号（oi 单位：USDT 名义价值）
            price = c.get('price', 1)
            oi = exchange.get_open_interest(symbol)
            funding_history = exchange.get_funding_rate_history(symbol, limit=3)
            vol_24h = c.get('volume_24h', 0)  # volCcy24h: USDT 计价
            vol_oi_ratio = round(vol_24h / oi, 1) if oi > 0 else 0
            # 超过500x基本是单位不匹配（如PEPE的volCcy24h为代币数量），标记为无效
            if vol_oi_ratio > 500:
                logger.debug(f"{symbol} Vol/OI={vol_oi_ratio}x 超出合理范围，疑似单位异常，置零")
                vol_oi_ratio = 0
            # 连续资金费率为负的周期数（逼空布局信号）
            neg_streak = sum(1 for r in funding_history if r < -0.0001)
            # 资金费率均值
            avg_funding = sum(funding_history) / len(funding_history) if funding_history else funding
            # 多空比
            ls_ratio = exchange.get_long_short_ratio(symbol)

            yaobi = {
                'oi_usdt': oi,
                'vol_oi_ratio': vol_oi_ratio,
                'funding_neg_streak': neg_streak,   # 连续负资金费率期数（0-3）
                'avg_funding': avg_funding,
                'ls_ratio': ls_ratio,
                # 综合妖币风险：Vol/OI>15 或连续3期负资金费率
                'yaobi_risk': 'HIGH' if vol_oi_ratio > 20 else ('MED' if (vol_oi_ratio > 12 or neg_streak >= 2) else 'LOW'),
            }
            enriched.append({**c, **indicators, 'funding_rate': funding, **yaobi})
        except Exception as e:
            logger.warning(f"{symbol} 数据获取失败: {e}")

    logger.info(f"成功获取 {len(enriched)} 个标的的市场快照")
    return enriched
