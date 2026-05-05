import ccxt
import pandas as pd
from loguru import logger


class OKXExchange:
    def __init__(self, cfg: dict, proxy: dict = None):
        params = {
            "apiKey": cfg["api_key"],
            "secret": cfg["secret_key"],
            "password": cfg["passphrase"],
            "options": {"defaultType": "swap"},
        }
        if proxy and proxy.get("http"):
            params["proxies"] = {"http": proxy["http"], "https": proxy.get("https", proxy["http"])}
        self.exchange = ccxt.okx(params)
        if cfg.get("testnet", True):
            self.exchange.set_sandbox_mode(True)
        self.exchange.load_markets()
        self._set_oneway_mode()

    def _set_oneway_mode(self):
        try:
            self.exchange.set_position_mode(False)
            logger.info("持仓模式: 单向 one-way")
        except Exception as e:
            logger.debug(f"set_position_mode: {e}")

    def get_equity(self) -> float:
        try:
            bal = self.exchange.fetch_balance({"type": "swap"})
            data = bal.get("info", {}).get("data", [])
            if data:
                return float(data[0].get("totalEq", 0) or 0)
        except Exception as e:
            logger.warning(f"get_equity fallback: {e}")
        return self.get_free_balance()

    def get_free_balance(self) -> float:
        try:
            bal = self.exchange.fetch_balance()
            return float(bal.get("USDT", {}).get("free", 0) or 0)
        except Exception as e:
            logger.error(f"get_free_balance: {e}")
            return 0.0

    def get_usdt_account_snapshot(self) -> dict:
        try:
            bal = self.exchange.fetch_balance({"type": "swap"})
            usdt = bal.get("USDT", {}) or {}
            info_data = bal.get("info", {}).get("data", [])
            info = info_data[0] if info_data else {}
            details = info.get("details", []) or []
            usdt_detail = next((d for d in details if d.get("ccy") == "USDT"), {})
            equity = float(info.get("totalEq", 0) or usdt.get("total", 0) or 0)
            free = float(usdt.get("free", 0) or usdt_detail.get("availBal", 0) or info.get("availEq", 0) or 0)
            used = float(usdt.get("used", 0) or usdt_detail.get("imr", 0) or 0)
            total = float(usdt.get("total", 0) or usdt_detail.get("cashBal", 0) or equity)
            unrealized_pnl = float(usdt_detail.get("upl", 0) or 0)
            margin_ratio = float(info.get("mgnRatio", 0) or 0)
            return {
                "equity": equity,
                "free": free,
                "used": used,
                "total": total,
                "unrealized_pnl": unrealized_pnl,
                "margin_ratio": margin_ratio,
            }
        except Exception as e:
            logger.warning(f"get_usdt_account_snapshot fallback: {e}")
            return {
                "equity": self.get_equity(),
                "free": self.get_free_balance(),
                "used": 0.0,
                "total": 0.0,
                "unrealized_pnl": 0.0,
                "margin_ratio": 0.0,
            }

    def get_positions(self) -> list:
        try:
            positions = self.exchange.fetch_positions()
            return [p for p in positions if abs(float(p.get("contracts", 0) or 0)) > 0]
        except Exception as e:
            logger.error(f"get_positions: {e}")
            return []

    def get_usdt_positions(self) -> list:
        positions = []
        for p in self.get_positions():
            symbol = p.get("symbol", "")
            if not symbol.endswith(":USDT"):
                continue
            contracts = abs(float(p.get("contracts", 0) or 0))
            entry = float(p.get("entryPrice", 0) or 0)
            mark = float(p.get("markPrice", 0) or p.get("lastPrice", 0) or 0)
            notional = abs(float(p.get("notional", 0) or 0))
            margin = float(p.get("initialMargin", 0) or p.get("collateral", 0) or 0)
            pnl = float(p.get("unrealizedPnl", 0) or 0)
            percentage = float(p.get("percentage", 0) or 0)
            liquidation = float(p.get("liquidationPrice", 0) or 0)
            positions.append({
                "symbol": symbol,
                "side": p.get("side", ""),
                "contracts": contracts,
                "entry_price": entry,
                "mark_price": mark,
                "notional": notional,
                "margin": margin,
                "unrealized_pnl": pnl,
                "percentage": percentage,
                "liquidation_price": liquidation,
                "leverage": p.get("leverage"),
                "margin_mode": p.get("marginMode"),
                "raw": p,
            })
        return positions

    def fetch_ohlcv(self, symbol: str, timeframe: str = "15m", limit: int = 100) -> pd.DataFrame:
        raw = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)
        return df.astype(float)

    def fetch_ticker(self, symbol: str) -> dict:
        return self.exchange.fetch_ticker(symbol)

    def get_all_tickers(self) -> dict:
        return self.exchange.fetch_tickers()

    def get_funding_rate(self, symbol: str) -> float:
        try:
            result = self.exchange.fetch_funding_rate(symbol)
            return float(result.get("fundingRate", 0) or 0)
        except Exception:
            return 0.0

    def get_funding_rate_history(self, symbol: str, limit: int = 5) -> list:
        try:
            history = self.exchange.fetch_funding_rate_history(symbol, limit=limit)
            return [float(r.get("fundingRate", 0) or 0) for r in history]
        except Exception:
            return []

    def get_open_interest(self, symbol: str) -> float:
        try:
            result = self.exchange.fetch_open_interest(symbol)
            return float(result.get("openInterestValue", 0) or 0)
        except Exception:
            return 0.0

    def get_open_interest_history(self, symbol: str, timeframe: str = "5m", limit: int = 6) -> list:
        try:
            if not self.exchange.has.get("fetchOpenInterestHistory"):
                return []
            history = self.exchange.fetch_open_interest_history(symbol, timeframe=timeframe, limit=limit)
            values = []
            for item in history:
                value = item.get("openInterestValue") or item.get("openInterestAmount") or item.get("openInterest")
                values.append(float(value or 0))
            return values
        except Exception as e:
            logger.debug(f"open interest history {symbol}: {e}")
            return []

    def get_long_short_ratio(self, symbol: str) -> float:
        try:
            params = {"instId": symbol.replace("/", "-").replace(":USDT", "-SWAP")}
            result = self.exchange.publicGetRubikStatContractsLongShortAccountRatio(params)
            data = result.get("data", [])
            if data:
                return float(data[0].get("longShortRatio", 1) or 1)
        except Exception:
            pass
        return 1.0

    def get_closed_position_pnl(self, symbol: str, since_ms: int | None = None) -> dict | None:
        try:
            market = self.exchange.market(symbol)
            params = {"instId": market.get("id")}
            if since_ms:
                params["after"] = str(since_ms)
            result = self.exchange.privateGetAccountPositionsHistory(params)
            rows = result.get("data", []) if isinstance(result, dict) else []
            if not rows:
                return None
            row = rows[0]
            pnl = float(row.get("realizedPnl", row.get("pnl", 0)) or 0)
            close_price = float(row.get("closeAvgPx", row.get("avgPx", 0)) or 0)
            return {
                "symbol": symbol,
                "realized_pnl": pnl,
                "close_price": close_price,
                "raw": row,
            }
        except Exception as e:
            logger.debug(f"closed position pnl {symbol}: {e}")
            return None

    def get_contract_size(self, symbol: str) -> float:
        return float(self.exchange.markets.get(symbol, {}).get("contractSize", 1) or 1)

    def get_min_contracts(self, symbol: str) -> float:
        limits = self.exchange.markets.get(symbol, {}).get("limits", {})
        return float(limits.get("amount", {}).get("min", 1) or 1)

    def set_leverage_isolated(self, symbol: str, leverage: int):
        try:
            self.exchange.set_margin_mode("isolated", symbol)
        except Exception as e:
            logger.debug(f"set_margin_mode {symbol}: {e}")
        try:
            self.exchange.set_leverage(leverage, symbol)
        except Exception as e:
            logger.warning(f"set_leverage {symbol}: {e}")

    def _close_side(self, entry_side: str) -> str:
        return "sell" if entry_side == "buy" else "buy"

    def close_position_market(self, symbol: str, side: str, contracts: float) -> dict:
        amount = float(self.exchange.amount_to_precision(symbol, contracts))
        return self.exchange.create_market_order(
            symbol,
            self._close_side(side),
            amount,
            params={"tdMode": "isolated", "reduceOnly": True},
        )

    def place_sltp_order(self, symbol: str, side: str, amount: float, sl_price: float, tp_price: float) -> dict:
        close_side = self._close_side(side)
        sl_px = self.exchange.price_to_precision(symbol, sl_price)
        tp_px = self.exchange.price_to_precision(symbol, tp_price)
        return self.exchange.create_order(
            symbol,
            "conditional",
            close_side,
            amount,
            params={
                "ordType": "conditional",
                "tdMode": "isolated",
                "posSide": "net",
                "reduceOnly": True,
                "slTriggerPx": sl_px,
                "slOrdPx": "-1",
                "slTriggerPxType": "last",
                "tpTriggerPx": tp_px,
                "tpOrdPx": "-1",
                "tpTriggerPxType": "last",
            },
        )

    def place_order_with_sltp(self, symbol: str, side: str, contracts: float, sl_price: float, tp_price: float) -> dict:
        market = self.exchange.market(symbol)
        max_mkt = float(market.get("info", {}).get("maxMktSz") or contracts)
        contracts = min(contracts, max_mkt)
        amount = float(self.exchange.amount_to_precision(symbol, contracts))

        order = self.exchange.create_market_order(symbol, side, amount, params={"tdMode": "isolated"})
        sltp_order = None
        protection_error = None

        for attempt in range(1, 3):
            try:
                sltp_order = self.place_sltp_order(symbol, side, amount, sl_price, tp_price)
                logger.info(f"保护单已挂好: {symbol} SL={sl_price:.8f} TP={tp_price:.8f}")
                break
            except Exception as e:
                protection_error = e
                logger.warning(f"保护单第 {attempt} 次失败: {symbol} {e}")

        if sltp_order is None:
            logger.error(f"{symbol} 入场后保护单失败，立即市价退出，避免裸仓")
            try:
                self.close_position_market(symbol, side, amount)
            except Exception as e:
                logger.error(f"{symbol} 保护失败后的退出也失败，请手动检查测试盘: {e}")
            raise RuntimeError(f"保护单失败，已尝试退出: {protection_error}")

        return {
            "entry_order": order,
            "protection_order": sltp_order,
            "contracts": amount,
        }

    def close_all_positions(self):
        for pos in self.get_positions():
            symbol = pos["symbol"]
            side = "sell" if pos.get("side") == "long" else "buy"
            contracts = abs(float(pos.get("contracts", 0)))
            try:
                self.exchange.create_market_order(symbol, side, contracts, params={"tdMode": "isolated", "reduceOnly": True})
                logger.info(f"已平仓 {symbol}")
            except Exception as e:
                logger.error(f"平仓失败 {symbol}: {e}")
