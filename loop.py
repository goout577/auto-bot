import json
import os
import sys
import time
from datetime import datetime, timezone

import yaml
from loguru import logger

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from agent.brain import make_decision, review_failure
from agent.context_builder import build_context, format_trade_card
from agent.executor import execute
from agent.loss_tracker import build_failed_attempt, detect_closed_losses, register_open_trade
from collectors.market import fetch_market_snapshots
from collectors.screener import screen_symbols
from core.env_loader import apply_env_config, load_env_file
from core.exchange import OKXExchange
from core.risk import validate_decision
from core.storage import init_db, record_account_snapshot, record_cycle, record_loss_review

STATE_FILE = "state.json"
CONFIG_FILE = "config/config.yaml"
CONFIG_EXAMPLE_FILE = "config/config.example.yaml"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def load_state() -> dict:
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            state = json.load(f)
    except Exception:
        state = {}
    state.setdefault("last_run_utc", None)
    state.setdefault("cycle_count", 0)
    state.setdefault("last_action", None)
    state.setdefault("cooldowns", {})
    state.setdefault("trade_records", [])
    state.setdefault("open_trades", {})
    state.setdefault("closed_trades", [])
    state.setdefault("reviewed_failures", {})
    state.setdefault("consecutive_losses", 0)
    return state


def save_state(state: dict):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def load_config() -> dict:
    load_env_file(".env")
    config_path = CONFIG_FILE if os.path.exists(CONFIG_FILE) else CONFIG_EXAMPLE_FILE
    if not os.path.exists(config_path):
        raise FileNotFoundError("Missing config/config.example.yaml")
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    return apply_env_config(cfg)


def refresh_daily_state(state: dict, equity: float):
    today = _now().date().isoformat()
    if state.get("day") != today:
        state["day"] = today
        state["day_start_equity"] = equity
        state["day_low_equity"] = equity
        state["consecutive_losses"] = 0
    else:
        state["day_low_equity"] = min(float(state.get("day_low_equity") or equity), equity)


def update_after_result(state: dict, decision: dict, result: dict, equity_before: float, equity_after: float):
    action = decision.get("action")
    if action in ("open_long", "open_short") and decision.get("symbol") and result.get("status") in ("opened", "advice_only"):
        state.setdefault("cooldowns", {})[f"{decision['symbol']}:{action}"] = _now().isoformat()

    record = {
        "time_utc": _now().isoformat(),
        "decision": decision,
        "result": result,
        "equity_before": equity_before,
        "equity_after": equity_after,
    }
    state.setdefault("trade_records", []).append(record)
    state["trade_records"] = state["trade_records"][-500:]


def _candidate_allows_open(decision: dict, candidates: list, min_score: int) -> tuple[bool, str]:
    action = decision.get("action")
    if action not in ("open_long", "open_short"):
        return True, "ok"

    symbol = decision.get("symbol")
    matched = next((c for c in candidates if c.get("symbol") == symbol), None)
    if not matched:
        return False, f"{symbol or '-'} 不在本轮妖币候选榜，禁止开仓"

    score = int(matched.get("yaobi_score") or 0)
    if not matched.get("passed_min_score") or score < min_score:
        return False, f"{symbol} 妖币分 {score} 未达到开仓线 {min_score}，仅记录观察"

    decision["yaobi_score"] = score
    return True, "ok"


def review_failure_once(state: dict, cfg: dict, failure: dict | None):
    if not failure:
        return
    key = str(failure.get("trade_key") or failure.get("symbol") or _now().isoformat())
    reviewed = state.setdefault("reviewed_failures", {})
    if reviewed.get(key):
        return
    logger.info(f"触发 LLM 失败复盘: {failure.get('symbol')} type={failure.get('failure_type')}")
    review = review_failure(failure, cfg["ai"])
    record_loss_review(time_utc=_now().isoformat(), trade=failure, review=review)
    reviewed[key] = _now().isoformat()


def review_closed_losses(exchange: OKXExchange, positions: list[dict], state: dict, cfg: dict):
    for loss_trade in detect_closed_losses(exchange, positions, state):
        loss_trade["failure_type"] = "closed_loss"
        review_failure_once(state, cfg, loss_trade)


def run_once(exchange: OKXExchange, cfg: dict, state: dict):
    cycle_count = state["cycle_count"] + 1
    logger.info(f"=== Cycle {cycle_count}: yaobi short-squeeze scan ===")

    account = exchange.get_usdt_account_snapshot()
    equity = float(account.get("equity") or 0)
    balance = float(account.get("free") or 0)
    positions = exchange.get_usdt_positions()
    refresh_daily_state(state, equity)
    record_account_snapshot(time_utc=_now().isoformat(), account=account, positions=positions)
    review_closed_losses(exchange, positions, state, cfg)

    logger.info(
        f"equity=${equity:.2f} | free=${balance:.2f} | positions={len(positions)}/"
        f"{cfg['risk'].get('max_open_positions', 10)} | day_start=${float(state['day_start_equity']):.2f}"
    )

    candidates = screen_symbols(exchange, cfg["screener"])
    candidates = fetch_market_snapshots(exchange, candidates, cfg["trading"], cfg["screener"])

    context = build_context(equity, balance, positions, candidates, cfg["risk"], state)
    decision = make_decision(context, cfg["ai"], cfg["risk"].get("position_margin_pct", 10))
    logger.info("\n" + format_trade_card(decision))

    min_score = int(cfg.get("screener", {}).get("min_yaobi_score", 55))
    valid, reason = _candidate_allows_open(decision, candidates, min_score)
    if valid:
        valid, reason = validate_decision(decision, equity, positions, cfg["risk"], state)

    if not valid:
        logger.info(f"risk blocked: {reason}")
        result = {"status": "blocked", "reason": reason}
    else:
        execution_mode = cfg["trading"].get("execution_mode", "auto_testnet")
        if execution_mode == "advice_only":
            result = {"status": "advice_only"}
        else:
            try:
                result = execute(decision, exchange, cfg["risk"])
            except Exception as e:
                logger.exception("execution failed")
                result = {"status": "execution_failed", "reason": str(e)}
        logger.info("\n" + format_trade_card(decision, result))
        logger.info(f"execution result: {result}")

    review_failure_once(state, cfg, build_failed_attempt(cycle_count, decision, result, candidates, equity))
    register_open_trade(state, decision, result, candidates)

    record_cycle(
        time_utc=_now().isoformat(),
        cycle_count=cycle_count,
        equity=equity,
        balance=balance,
        positions_count=len(positions),
        state=state,
        candidates=candidates,
        decision=decision,
        result=result,
        account=account,
        positions=positions,
    )

    equity_after = exchange.get_equity()
    refresh_daily_state(state, equity_after)
    update_after_result(state, decision, result, equity, equity_after)

    state["cycle_count"] += 1
    state["last_run_utc"] = _now().isoformat()
    state["last_action"] = decision.get("action")
    save_state(state)
    return result


def wait_for_next_cycle(state: dict, interval_sec: int):
    last_run = state.get("last_run_utc")
    if not last_run:
        return
    try:
        last_dt = datetime.fromisoformat(last_run)
        elapsed = (_now() - last_dt).total_seconds()
        remaining = interval_sec - elapsed
        if remaining > 30:
            logger.info(f"resume wait: last run {int(elapsed // 60)} min ago, wait {int(remaining // 60)} min")
            time.sleep(remaining)
    except Exception:
        pass


def main():
    os.makedirs("logs", exist_ok=True)
    logger.add(
        "logs/agent_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="14 days",
        level="INFO",
        encoding="utf-8",
    )

    cfg = load_config()
    init_db()

    proxy = cfg.get("proxy", {})
    if proxy.get("http"):
        os.environ["HTTP_PROXY"] = proxy["http"]
        os.environ["HTTPS_PROXY"] = proxy.get("https", proxy["http"])
        logger.info(f"proxy: {proxy['http']}")

    testnet = cfg["exchange"].get("testnet", True)
    if not testnet:
        raise RuntimeError("This build is locked to OKX testnet. Do not enable live trading here.")

    state = load_state()
    interval_sec = int(cfg["trading"]["loop_interval_minutes"]) * 60

    logger.info(
        f"agent start | mode=OKX testnet | execution={cfg['trading'].get('execution_mode', 'auto_testnet')} "
        f"| interval={interval_sec // 60} min | llm_role=decision_and_failure_review | llm={cfg['ai'].get('model')}"
    )
    logger.info(f"history cycles: {state['cycle_count']} | last action: {state.get('last_action', 'none')}")

    wait_for_next_cycle(state, interval_sec)
    exchange = OKXExchange(cfg["exchange"], proxy=cfg.get("proxy", {}))

    while True:
        try:
            run_once(exchange, cfg, state)
        except KeyboardInterrupt:
            logger.info("user stopped agent")
            break
        except Exception:
            logger.exception("cycle error")

        logger.info(f"wait {interval_sec // 60} min before next cycle")
        time.sleep(interval_sec)


if __name__ == "__main__":
    main()
