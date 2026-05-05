import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from agent.rule_engine import build_rule_trade_card
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

SCREENER = {"min_yaobi_score": 55}


def candidate(score=70, passed=True, stage="逼空启动", atr_pct=2.0):
    return {
        "symbol": "HOME/USDT:USDT",
        "price": 0.01,
        "yaobi_score": score,
        "passed_min_score": passed,
        "stage": stage,
        "atr_pct": atr_pct,
        "avg_funding": -0.003,
        "change_5": 4.2,
        "change_15": 7.8,
        "volume_spike": 5.5,
        "oi_change_pct": 3.2,
    }


class RuleEngineTest(unittest.TestCase):
    def test_low_score_holds(self):
        decision = build_rule_trade_card([candidate(score=40, passed=False)], RISK, SCREENER)
        self.assertEqual(decision["action"], "hold")

    def test_terminal_risk_holds(self):
        decision = build_rule_trade_card([candidate(score=80, passed=True, stage="末端风险")], RISK, SCREENER)
        self.assertEqual(decision["action"], "hold")

    def test_good_candidate_generates_valid_long(self):
        decision = build_rule_trade_card([candidate()], RISK, SCREENER)
        self.assertEqual(decision["action"], "open_long")
        self.assertEqual(decision["decision_source"], "rules")
        ok, reason = validate_decision(decision, 1000, [], RISK, {"day_start_equity": 1000})
        self.assertTrue(ok, reason)


if __name__ == "__main__":
    unittest.main()
