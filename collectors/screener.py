from loguru import logger
from core.exchange import OKXExchange


def screen_symbols(exchange: OKXExchange, cfg: dict) -> list:
    min_volume = float(cfg.get('min_volume_24h_usdt', 30_000_000))
    max_notional = float(cfg.get('max_contract_notional_usdt', 12.0))
    top_n = int(cfg.get('top_n', 10))
    excluded = set(cfg.get('excluded_bases', ['BTC', 'ETH', 'USDC', 'USDT']))

    try:
        tickers = exchange.get_all_tickers()
    except Exception as e:
        logger.error(f"fetch_tickers 失败: {e}")
        return []

    markets = exchange.exchange.markets
    candidates = []

    for symbol, ticker in tickers.items():
        if not symbol.endswith(':USDT'):
            continue
        base = symbol.split('/')[0]
        if base in excluded:
            continue

        market = markets.get(symbol)
        if not market or not market.get('active'):
            continue

        try:
            price = float(ticker.get('last', 0) or 0)
            if price <= 0:
                continue

            # OKX demo 下 quoteVolume 为 None，使用 info['volCcy24h']（USDT 计价成交量）
            info = ticker.get('info', {})
            quote_vol = float(info.get('volCcy24h', 0) or 0)
            if quote_vol < min_volume:
                continue

            ct_val = float(market.get('contractSize', 1) or 1)
            min_qty = float((market.get('limits') or {}).get('amount', {}).get('min', 1) or 1)
            if min_qty * ct_val * price > max_notional:
                continue

            # OKX percentage 为小数形式（0.0596 = 5.96%），统一转换为百分比
            raw_pct = float(ticker.get('percentage', 0) or 0)
            change_24h = raw_pct * 100 if abs(raw_pct) < 1 else raw_pct
            score = abs(change_24h)

            candidates.append({
                'symbol': symbol,
                'price': price,
                'change_24h': change_24h,
                'volume_24h': quote_vol,
                'ct_val': ct_val,
                'min_contracts': min_qty,
                'score': score,
            })
        except Exception as e:
            logger.debug(f"跳过 {symbol}: {e}")

    candidates.sort(key=lambda x: x['score'], reverse=True)
    logger.info(f"筛选到 {len(candidates)} 个候选，取前 {top_n}")
    return candidates[:top_n]
