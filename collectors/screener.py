from loguru import logger

from core.exchange import OKXExchange


def _ticker_change_pct(ticker: dict) -> float:
    raw_pct = float(ticker.get("percentage", 0) or 0)
    return raw_pct * 100 if abs(raw_pct) < 1 else raw_pct


def screen_symbols(exchange: OKXExchange, cfg: dict) -> list:
    min_volume = float(cfg.get("min_volume_24h_usdt", 1_000_000))
    max_notional = float(cfg.get("max_contract_notional_usdt", 200.0))
    scan_top_n = int(cfg.get("scan_top_n", cfg.get("top_n", 40)))
    excluded = set(cfg.get("excluded_bases", ["BTC", "ETH", "USDC", "USDT"]))

    try:
        tickers = exchange.get_all_tickers()
    except Exception as e:
        logger.error(f"获取全市场行情失败: {e}")
        return []

    markets = exchange.exchange.markets
    candidates = []

    for symbol, ticker in tickers.items():
        if not symbol.endswith(":USDT"):
            continue

        base = symbol.split("/")[0]
        if base in excluded:
            continue

        market = markets.get(symbol)
        if not market or not market.get("active"):
            continue

        try:
            price = float(ticker.get("last", 0) or 0)
            if price <= 0:
                continue

            info = ticker.get("info", {})
            quote_vol = float(info.get("volCcy24h", 0) or ticker.get("quoteVolume", 0) or 0)
            if quote_vol < min_volume:
                continue

            ct_val = float(market.get("contractSize", 1) or 1)
            min_qty = float((market.get("limits") or {}).get("amount", {}).get("min", 1) or 1)
            min_notional = min_qty * ct_val * price
            if min_notional > max_notional:
                continue

            change_24h = _ticker_change_pct(ticker)
            pre_score = abs(change_24h) + min(quote_vol / 1_000_000, 30)

            candidates.append({
                "symbol": symbol,
                "base": base,
                "price": price,
                "change_24h": round(change_24h, 3),
                "volume_24h": quote_vol,
                "ct_val": ct_val,
                "min_contracts": min_qty,
                "min_notional": min_notional,
                "pre_score": round(pre_score, 3),
            })
        except Exception as e:
            logger.debug(f"跳过 {symbol}: {e}")

    candidates.sort(key=lambda x: x["pre_score"], reverse=True)
    logger.info(f"基础筛选得到 {len(candidates)} 个山寨合约，进入深度扫描 {scan_top_n} 个")
    return candidates[:scan_top_n]
