import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from agent.loss_tracker import detect_closed_losses, register_open_trade


class FakeExchange:
    def __init__(self, pnl):
        self.pnl = pnl

    def get_closed_position_pnl(self, symbol, since_ms=None):
        return {"symbol": symbol, "realized_pnl": self.pnl, "close_price": 0.9}


class LossTrackerTest(unittest.TestCase):
    def test_profitable_closed_trade_does_not_trigger_review(self):
        state = {}
        register_open_trade(
            state,
            {"action": "open_long", "symbol": "A/USDT:USDT", "entry_price": 1},
            {"status": "opened", "symbol": "A/USDT:USDT", "order_id": "1", "price": 1},
            [],
        )
        losses = detect_closed_losses(FakeExchange(3.2), [], state)
        self.assertEqual(losses, [])

    def test_loss_closed_trade_triggers_review(self):
        state = {}
        register_open_trade(
            state,
            {"action": "open_long", "symbol": "A/USDT:USDT", "entry_price": 1},
            {"status": "opened", "symbol": "A/USDT:USDT", "order_id": "1", "price": 1},
            [],
        )
        losses = detect_closed_losses(FakeExchange(-2.1), [], state)
        self.assertEqual(len(losses), 1)
        self.assertLess(losses[0]["realized_pnl"], 0)


if __name__ == "__main__":
    unittest.main()
