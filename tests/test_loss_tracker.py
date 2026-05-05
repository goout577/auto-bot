import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from agent.loss_tracker import build_failed_attempt, detect_closed_losses, register_open_trade


class FakeExchange:
    def __init__(self, pnl):
        self.pnl = pnl

    def get_closed_position_pnl(self, symbol, since_ms=None):
        return {"symbol": symbol, "realized_pnl": self.pnl, "close_price": 0.9}


class LossTrackerTest(unittest.TestCase):
    def test_hold_decision_does_not_create_failed_attempt(self):
        failure = build_failed_attempt(
            7,
            {"action": "hold", "symbol": "A/USDT:USDT"},
            {"status": "blocked", "reason": "low score"},
            [],
            1000,
        )
        self.assertIsNone(failure)

    def test_open_decision_blocked_creates_sim_failure(self):
        failure = build_failed_attempt(
            8,
            {"action": "open_long", "symbol": "A/USDT:USDT"},
            {"status": "blocked", "reason": "daily drawdown hit"},
            [{"symbol": "A/USDT:USDT", "yaobi_score": 81}],
            1000,
        )
        self.assertIsNotNone(failure)
        self.assertEqual(failure["failure_type"], "sim_testnet_failure")
        self.assertEqual(failure["symbol"], "A/USDT:USDT")
        self.assertEqual(failure["candidate_snapshot"]["yaobi_score"], 81)

    def test_opened_or_advice_only_does_not_create_failed_attempt(self):
        decision = {"action": "open_long", "symbol": "A/USDT:USDT"}
        self.assertIsNone(build_failed_attempt(9, decision, {"status": "opened"}, [], 1000))
        self.assertIsNone(build_failed_attempt(9, decision, {"status": "advice_only"}, [], 1000))

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
