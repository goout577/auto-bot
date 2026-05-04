from loguru import logger
from core.exchange import OKXExchange


def execute(decision: dict, exchange: OKXExchange) -> dict:
    action = decision.get('action')

    if action == 'hold':
        return {'status': 'hold'}

    if action == 'close_all':
        exchange.close_all_positions()
        return {'status': 'closed_all'}

    if action in ('open_long', 'open_short'):
        symbol = decision['symbol']
        leverage = int(decision.get('leverage', 5))
        size_pct = float(decision.get('size_pct', 20))
        sl_pct = float(decision['sl_pct'])
        tp_pct = float(decision['tp_pct'])

        balance = exchange.get_free_balance()
        margin_usdt = balance * size_pct / 100
        notional = margin_usdt * leverage

        ticker = exchange.fetch_ticker(symbol)
        price = float(ticker['last'])

        if action == 'open_long':
            side = 'buy'
            sl_price = price * (1 - sl_pct / 100)
            tp_price = price * (1 + tp_pct / 100)
        else:
            side = 'sell'
            sl_price = price * (1 + sl_pct / 100)
            tp_price = price * (1 - tp_pct / 100)

        ct_val = exchange.get_contract_size(symbol)
        min_qty = exchange.get_min_contracts(symbol)
        contracts = max(notional / (ct_val * price), min_qty)

        exchange.set_leverage_isolated(symbol, leverage)

        logger.info(
            f"下单 {action} {symbol}: {contracts:.4f} 张 @ ${price:.4f} "
            f"SL=${sl_price:.4f} TP=${tp_price:.4f} 杠杆={leverage}x 可用余额=${balance:.2f}"
        )

        order = exchange.place_order_with_sltp(symbol, side, contracts, sl_price, tp_price)
        return {
            'status': 'opened',
            'action': action,
            'symbol': symbol,
            'contracts': contracts,
            'price': price,
            'sl': sl_price,
            'tp': tp_price,
            'leverage': leverage,
            'order_id': order.get('id'),
        }

    return {'status': 'unknown', 'action': action}
