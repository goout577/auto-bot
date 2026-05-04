import ccxt
import pandas as pd
from loguru import logger


class OKXExchange:
    def __init__(self, cfg: dict, proxy: dict = None):
        params = {
            'apiKey': cfg['api_key'],
            'secret': cfg['secret_key'],
            'password': cfg['passphrase'],
            'options': {'defaultType': 'swap'},
        }
        if proxy and proxy.get('http'):
            params['proxies'] = {'http': proxy['http'], 'https': proxy.get('https', proxy['http'])}
        self.exchange = ccxt.okx(params)
        if cfg.get('testnet', True):
            self.exchange.set_sandbox_mode(True)
        self.exchange.load_markets()
        self._set_oneway_mode()

    def _set_oneway_mode(self):
        try:
            self.exchange.set_position_mode(False)  # False = net/one-way mode
            logger.info("持仓模式: 单向（one-way）")
        except Exception as e:
            logger.debug(f"set_position_mode: {e}")

    def get_equity(self) -> float:
        try:
            bal = self.exchange.fetch_balance({'type': 'swap'})
            data = bal.get('info', {}).get('data', [])
            if data:
                return float(data[0].get('totalEq', 0) or 0)
        except Exception as e:
            logger.warning(f"get_equity fallback: {e}")
        return self.get_free_balance()

    def get_free_balance(self) -> float:
        try:
            bal = self.exchange.fetch_balance()
            return float(bal.get('USDT', {}).get('free', 0) or 0)
        except Exception as e:
            logger.error(f"get_free_balance: {e}")
            return 0.0

    def get_positions(self) -> list:
        try:
            positions = self.exchange.fetch_positions()
            return [p for p in positions if float(p.get('contracts', 0) or 0) != 0]
        except Exception as e:
            logger.error(f"get_positions: {e}")
            return []

    def fetch_ohlcv(self, symbol: str, timeframe: str = '15m', limit: int = 100) -> pd.DataFrame:
        raw = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(raw, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        return df.astype(float)

    def fetch_ticker(self, symbol: str) -> dict:
        return self.exchange.fetch_ticker(symbol)

    def get_all_tickers(self) -> dict:
        return self.exchange.fetch_tickers()

    def get_funding_rate(self, symbol: str) -> float:
        try:
            result = self.exchange.fetch_funding_rate(symbol)
            return float(result.get('fundingRate', 0) or 0)
        except Exception:
            return 0.0

    def get_funding_rate_history(self, symbol: str, limit: int = 3) -> list:
        try:
            history = self.exchange.fetch_funding_rate_history(symbol, limit=limit)
            return [float(r.get('fundingRate', 0) or 0) for r in history]
        except Exception:
            return []

    def get_open_interest(self, symbol: str) -> float:
        """返回 USDT 名义持仓量（openInterestValue 字段，OKX 直接提供）"""
        try:
            result = self.exchange.fetch_open_interest(symbol)
            return float(result.get('openInterestValue', 0) or 0)
        except Exception:
            return 0.0

    def get_long_short_ratio(self, symbol: str) -> float:
        """多空比 > 1 = 多头占优，< 1 = 空头占优"""
        try:
            params = {'instId': symbol.replace('/', '-').replace(':USDT', '-SWAP')}
            result = self.exchange.publicGetRubikStatContractsLongShortAccountRatio(params)
            data = result.get('data', [])
            if data:
                return float(data[0].get('longShortRatio', 1) or 1)
        except Exception:
            pass
        return 1.0

    def get_market(self, symbol: str) -> dict:
        return self.exchange.markets.get(symbol, {})

    def get_contract_size(self, symbol: str) -> float:
        return float(self.exchange.markets.get(symbol, {}).get('contractSize', 1) or 1)

    def get_min_contracts(self, symbol: str) -> float:
        limits = self.exchange.markets.get(symbol, {}).get('limits', {})
        return float(limits.get('amount', {}).get('min', 1) or 1)

    def set_leverage_isolated(self, symbol: str, leverage: int):
        try:
            self.exchange.set_margin_mode('isolated', symbol)
        except Exception as e:
            logger.debug(f"set_margin_mode {symbol}: {e}")
        try:
            self.exchange.set_leverage(leverage, symbol)
        except Exception as e:
            logger.warning(f"set_leverage {symbol}: {e}")

    def place_order_with_sltp(self, symbol: str, side: str, contracts: float,
                               sl_price: float, tp_price: float) -> dict:
        # 不超过交易所单笔市价单最大下单量（OKX 原始字段 maxMktSz）
        market = self.exchange.market(symbol)
        max_mkt = float(market.get('info', {}).get('maxMktSz') or contracts)
        contracts = min(contracts, max_mkt)
        amount = float(self.exchange.amount_to_precision(symbol, contracts))

        # 第一步：入场市价单（单向模式，无需 posSide）
        order = self.exchange.create_market_order(
            symbol, side, amount,
            params={'tdMode': 'isolated'},
        )

        # 第二步：挂止损止盈条件单（best-effort，失败不影响入场）
        close_side = 'sell' if side == 'buy' else 'buy'
        sl_px = self.exchange.price_to_precision(symbol, sl_price)
        tp_px = self.exchange.price_to_precision(symbol, tp_price)
        try:
            self.exchange.create_order(
                symbol, 'conditional', close_side, amount,
                params={
                    'ordType': 'conditional',
                    'tdMode': 'isolated',
                    'posSide': 'net',
                    'reduceOnly': True,
                    'slTriggerPx': sl_px,
                    'slOrdPx': '-1',
                    'slTriggerPxType': 'last',
                    'tpTriggerPx': tp_px,
                    'tpOrdPx': '-1',
                    'tpTriggerPxType': 'last',
                },
            )
            logger.info(f"SL/TP 条件单已挂: SL={sl_price:.4f} TP={tp_price:.4f}")
        except Exception as e:
            logger.warning(f"SL/TP 挂单失败（AI将在下次循环处理）: {e}")

        return order

    def close_all_positions(self):
        for pos in self.get_positions():
            symbol = pos['symbol']
            side = 'sell' if pos.get('side') == 'long' else 'buy'
            contracts = abs(float(pos.get('contracts', 0)))
            try:
                self.exchange.create_market_order(
                    symbol, side, contracts,
                    params={'tdMode': 'isolated', 'reduceOnly': True}
                )
                logger.info(f"Closed {symbol}")
            except Exception as e:
                logger.error(f"Failed to close {symbol}: {e}")
