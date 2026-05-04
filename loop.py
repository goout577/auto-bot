import os
import sys
import json
import time
import yaml
from datetime import datetime, timezone
from loguru import logger

# Windows 控制台 UTF-8 输出
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from core.exchange import OKXExchange
from collectors.screener import screen_symbols
from collectors.market import fetch_market_snapshots
from collectors.sentiment import get_fear_greed, get_crypto_news
from collectors.onchain import get_defi_tvl, get_market_overview
from agent.context_builder import build_context
from agent.brain import make_decision
from agent.executor import execute
from core.risk import validate_decision

STATE_FILE = 'state.json'


def load_state() -> dict:
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {'last_run_utc': None, 'cycle_count': 0, 'last_action': None}


def save_state(state: dict):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def run_once(exchange: OKXExchange, cfg: dict, state: dict):
    logger.info(f"=== 第 {state['cycle_count'] + 1} 轮决策循环开始 ===")

    equity = exchange.get_equity()
    balance = exchange.get_free_balance()
    positions = exchange.get_positions()
    logger.info(f"权益: ${equity:.2f} | 可用: ${balance:.2f} | 持仓: {len(positions)} 个")

    candidates = screen_symbols(exchange, cfg['screener'])
    candidates = fetch_market_snapshots(exchange, candidates, cfg['trading'])

    sentiment = get_fear_greed()
    news = get_crypto_news(cfg['external_apis'].get('cryptopanic_token', ''))
    defi = get_defi_tvl()
    market_overview = get_market_overview(cfg['external_apis'].get('coingecko_demo_key', ''))

    context = build_context(
        equity, balance, positions,
        candidates, sentiment, news, defi, market_overview,
        cfg['risk']
    )

    decision = make_decision(context, cfg['ai'])
    logger.info(
        f"决策: {decision.get('action')} | "
        f"信心: {decision.get('confidence')} | "
        f"理由: {decision.get('reasoning', '')}"
    )

    valid, reason = validate_decision(decision, equity, positions, cfg['risk'])
    if not valid:
        logger.info(f"风控拦截: {reason}")
        result = {'status': 'blocked', 'reason': reason}
    else:
        result = execute(decision, exchange)
        logger.info(f"执行结果: {result}")

    state['cycle_count'] += 1
    state['last_run_utc'] = datetime.now(timezone.utc).isoformat()
    state['last_action'] = decision.get('action')
    save_state(state)
    return result


def wait_for_next_cycle(state: dict, interval_sec: int):
    last_run = state.get('last_run_utc')
    if not last_run:
        return
    try:
        last_dt = datetime.fromisoformat(last_run)
        elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds()
        remaining = interval_sec - elapsed
        if remaining > 30:
            logger.info(f"重启恢复：距上次运行 {int(elapsed//60)}分钟，等待 {int(remaining//60)}分{int(remaining%60)}秒后继续")
            time.sleep(remaining)
    except Exception:
        pass


def main():
    os.makedirs('logs', exist_ok=True)
    logger.add(
        'logs/agent_{time:YYYY-MM-DD}.log',
        rotation='00:00',
        retention='7 days',
        level='INFO',
        encoding='utf-8',
    )

    with open('config/config.yaml', encoding='utf-8') as f:
        cfg = yaml.safe_load(f)

    # 代理设置（让 requests 库的所有 HTTP 请求都走代理）
    proxy = cfg.get('proxy', {})
    if proxy.get('http'):
        os.environ['HTTP_PROXY'] = proxy['http']
        os.environ['HTTPS_PROXY'] = proxy.get('https', proxy['http'])
        logger.info(f"代理: {proxy['http']}")

    state = load_state()
    interval_sec = int(cfg['trading']['loop_interval_minutes']) * 60
    testnet = cfg['exchange'].get('testnet', True)

    logger.info(f"Agent 启动 | 模式: {'模拟盘' if testnet else '实盘'} | 间隔: {interval_sec//60}分钟")
    logger.info(f"历史轮次: {state['cycle_count']} | 上次操作: {state.get('last_action', '无')}")

    # 重启后，如果距上次运行不足一个间隔，等待补齐
    wait_for_next_cycle(state, interval_sec)

    exchange = OKXExchange(cfg['exchange'], proxy=cfg.get('proxy', {}))

    while True:
        try:
            run_once(exchange, cfg, state)
        except KeyboardInterrupt:
            logger.info("用户手动停止 Agent。")
            break
        except Exception:
            logger.exception("循环异常")

        logger.info(f"等待 {interval_sec//60} 分钟后进入下一轮...")
        time.sleep(interval_sec)


if __name__ == '__main__':
    main()
