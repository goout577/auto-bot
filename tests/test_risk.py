import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from core.risk import validate_decision


RISK = {
    "position_margin_pct": 10,
    "max_open_positions": 10,
    "daily_max_drawdown_pct": 20,
    "same_symbol_cooldown_minutes": 30,
    "max_leverage": 8,
    "min_confidence": 6,
    "min_balance_usdt": 8,
    "min_stop_loss_pct": 0.3,
    "max_stop_loss_pct": 12,
    "min_reward_r": 1.5,
}


def good_long():
    return {
        "action": "open_long",
        "symbol": "DOGE/USDT:USDT",
        "entry_price": 1.0,
        "stop_loss": 0.97,
        "take_profit_1": 1.06,
        "leverage": 5,
        "size_pct": 10,
        "confidence": 7,
        "reasoning": "测试",
    }


class RiskTest(unittest.TestCase):
    def test_good_long_passes(self):
        ok, reason = validate_decision(good_long(), 100, [], RISK, {"day_start_equity": 100})
        self.assertTrue(ok, reason)

    def test_missing_prices_blocked(self):
        decision = good_long()
        decision.pop("stop_loss")
        ok, reason = validate_decision(decision, 100, [], RISK, {"day_start_equity": 100})
        self.assertFalse(ok)
        self.assertIn("止损", reason)

    def test_daily_drawdown_blocks(self):
        ok, reason = validate_decision(good_long(), 79, [], RISK, {"day_start_equity": 100})
        self.assertFalse(ok)
        self.assertIn("今日回撤", reason)

    def test_max_positions_blocks(self):
        positions = [{"symbol": f"X{i}/USDT:USDT", "contracts": 1} for i in range(10)]
        ok, reason = validate_decision(good_long(), 100, positions, RISK, {"day_start_equity": 100})
        self.assertFalse(ok)
        self.assertIn("上限", reason)

    def test_bad_price_order_blocks(self):
        decision = good_long()
        decision["stop_loss"] = 1.01
        ok, reason = validate_decision(decision, 100, [], RISK, {"day_start_equity": 100})
        self.assertFalse(ok)
        self.assertIn("价格关系", reason)


if __name__ == "__main__":
    unittest.main()
