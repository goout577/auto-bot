import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

from core.env_loader import load_env_file
from core.storage import DB_PATH, connect, init_db

try:
    import docker
except Exception:
    docker = None

ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "state.json"
CONFIG_PATH = ROOT / "config" / "config.yaml"
CONFIG_EXAMPLE_PATH = ROOT / "config" / "config.example.yaml"
LOG_DIR = ROOT / "logs"
BOT_CONTAINER_NAME = os.environ.get("BOT_CONTAINER_NAME", "yaobi-bot")

st.set_page_config(page_title="妖币逼空机器人", layout="wide", initial_sidebar_state="expanded")


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_config() -> dict:
    path = CONFIG_PATH if CONFIG_PATH.exists() else CONFIG_EXAMPLE_PATH
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def read_table(sql: str, params: tuple = ()) -> pd.DataFrame:
    if not DB_PATH.exists():
        init_db()
    with connect() as conn:
        return pd.read_sql_query(sql, conn, params=params)


def latest_log_text(max_chars: int = 9000) -> str:
    if not LOG_DIR.exists():
        return "还没有日志。"
    files = sorted(LOG_DIR.glob("agent_*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return "还没有日志。"
    return files[0].read_text(encoding="utf-8", errors="replace")[-max_chars:]


def env_status() -> pd.DataFrame:
    load_env_file(str(ROOT / ".env"))
    keys = [
        ("OKX_API_KEY", "OKX API Key"),
        ("OKX_SECRET_KEY", "OKX Secret"),
        ("OKX_PASSPHRASE", "OKX Passphrase"),
        ("LLM_BASE_URL", "LLM 复盘地址"),
        ("LLM_API_KEY", "LLM 复盘 Key"),
        ("LLM_MODEL", "LLM 复盘模型"),
        ("CRYPTOPANIC_TOKEN", "CryptoPanic"),
        ("COINGECKO_DEMO_KEY", "CoinGecko"),
    ]
    rows = []
    for key, label in keys:
        value = os.environ.get(key, "").strip()
        ok = bool(value and not value.startswith("YOUR_"))
        rows.append({"项目": label, "状态": "已配置" if ok else "未配置", "环境变量": key})
    return pd.DataFrame(rows)


def docker_client():
    if docker is None:
        return None, "容器里没有安装 docker Python 包。"
    try:
        return docker.from_env(), ""
    except Exception as e:
        return None, f"连接 Docker 失败：{e}"


def bot_status() -> dict:
    client, err = docker_client()
    if client is None:
        return {"exists": False, "status": "unknown", "error": err}
    try:
        container = client.containers.get(BOT_CONTAINER_NAME)
        container.reload()
        return {"exists": True, "status": container.status, "id": container.short_id, "error": ""}
    except Exception as e:
        return {"exists": False, "status": "not_created", "error": str(e)}


def control_bot(action: str) -> tuple[bool, str]:
    client, err = docker_client()
    if client is None:
        return False, err
    try:
        container = client.containers.get(BOT_CONTAINER_NAME)
        if action == "start":
            container.start()
            return True, "机器人已启动。"
        if action == "stop":
            container.stop(timeout=20)
            return True, "机器人已停止。"
        if action == "restart":
            container.restart(timeout=20)
            return True, "机器人已重启。"
        return False, f"未知动作：{action}"
    except Exception as e:
        return False, f"操作失败：{e}"


def render_bot_controls():
    status = bot_status()
    st.sidebar.header("机器人控制")
    st.sidebar.metric("容器", BOT_CONTAINER_NAME)
    st.sidebar.metric("状态", status.get("status", "unknown"))
    if status.get("error"):
        st.sidebar.caption(status["error"])

    cols = st.sidebar.columns(3)
    if cols[0].button("启动", use_container_width=True, disabled=status.get("status") == "running"):
        ok, msg = control_bot("start")
        st.toast(msg)
        st.rerun() if ok else st.sidebar.error(msg)
    if cols[1].button("停止", use_container_width=True, disabled=status.get("status") != "running"):
        ok, msg = control_bot("stop")
        st.toast(msg)
        st.rerun() if ok else st.sidebar.error(msg)
    if cols[2].button("重启", use_container_width=True, disabled=not status.get("exists")):
        ok, msg = control_bot("restart")
        st.toast(msg)
        st.rerun() if ok else st.sidebar.error(msg)


def latest_account() -> dict:
    df = read_table("select * from account_snapshots order by id desc limit 1")
    return df.iloc[0].to_dict() if not df.empty else {}


def latest_positions() -> pd.DataFrame:
    latest = read_table("select max(cycle_id) as cycle_id from position_snapshots")
    if latest.empty or pd.isna(latest.iloc[0]["cycle_id"]):
        return pd.DataFrame()
    return read_table(
        """
        select symbol, side, contracts, entry_price, mark_price, notional, margin,
               unrealized_pnl, percentage, liquidation_price, leverage, margin_mode
        from position_snapshots
        where cycle_id = ?
        order by abs(unrealized_pnl) desc
        """,
        (int(latest.iloc[0]["cycle_id"]),),
    )


def render_top_metrics(state: dict, cfg: dict, account: dict):
    risk = cfg.get("risk", {})
    day_start = float(state.get("day_start_equity") or account.get("equity") or 0)
    day_low = float(state.get("day_low_equity") or account.get("equity") or 0)
    drawdown = ((day_start - day_low) / day_start * 100) if day_start > 0 else 0

    cols = st.columns(6)
    cols[0].metric("总权益 USDT", f"{float(account.get('equity') or 0):,.2f}")
    cols[1].metric("可用保证金 USDT", f"{float(account.get('free_usdt') or 0):,.2f}")
    cols[2].metric("已用保证金 USDT", f"{float(account.get('used_usdt') or 0):,.2f}")
    cols[3].metric("浮动盈亏 USDT", f"{float(account.get('unrealized_pnl') or 0):,.2f}")
    cols[4].metric("今日最大回撤", f"{drawdown:.2f}%")
    cols[5].metric("仓位上限", risk.get("max_open_positions", 10))


def render_trade_card(trade: dict):
    if not trade:
        st.info("还没有规则交易卡。机器人跑完第一轮后这里会出现记录。")
        return
    source = "LLM" if (trade.get("raw_json") or "").find("llm") >= 0 else "系统"
    st.subheader(f"{trade.get('symbol') or '-'} | {trade.get('action') or '-'} | {trade.get('status') or '-'}")
    st.caption(f"决策来源：{source}。模拟盘失败和真实亏损都会进入复盘建议池。")
    cols = st.columns(4)
    cols[0].metric("阶段", trade.get("stage") or "-")
    cols[1].metric("信心", f"{trade.get('confidence') or '-'} / 10")
    cols[2].metric("杠杆", f"{trade.get('leverage') or '-'}x")
    cols[3].metric("仓位", f"{trade.get('size_pct') or '-'}%")
    cols = st.columns(5)
    cols[0].metric("建议价", trade.get("suggested_entry") or "-")
    cols[1].metric("实际价", trade.get("actual_entry") or "-")
    cols[2].metric("止损", trade.get("stop_loss") or "-")
    cols[3].metric("止盈1", trade.get("take_profit_1") or "-")
    cols[4].metric("止盈2/3", f"{trade.get('take_profit_2') or '-'} / {trade.get('take_profit_3') or '-'}")
    st.caption(trade.get("reasoning") or trade.get("reason") or "无理由记录")


def main():
    render_bot_controls()
    st.title("OKX 测试盘妖币逼空机器人")
    st.caption("只看 U 本位：LLM 交易卡、可用保证金、实时仓位、权益曲线和失败复盘。")

    state = load_state()
    cfg = load_config()
    init_db()
    account = latest_account()
    render_top_metrics(state, cfg, account)

    tab_account, tab_positions, tab_candidates, tab_trades, tab_reviews, tab_logs, tab_settings = st.tabs(
        ["账户曲线", "实时仓位", "妖币榜", "LLM交易卡", "复盘建议池", "日志", "配置"]
    )

    with tab_account:
        st.markdown("### U 本位余额曲线")
        snapshots = read_table(
            """
            select time_utc, equity, free_usdt, used_usdt, unrealized_pnl, positions_count
            from account_snapshots
            order by id asc
            limit 500
            """
        )
        if snapshots.empty:
            st.info("还没有账户快照。机器人完成第一轮后会出现曲线。")
        else:
            chart = snapshots.set_index("time_utc")[["equity", "free_usdt", "used_usdt", "unrealized_pnl"]]
            st.line_chart(chart)
            st.dataframe(snapshots.sort_values("time_utc", ascending=False), use_container_width=True, hide_index=True)

    with tab_positions:
        st.markdown("### 当前 U 本位仓位")
        positions = latest_positions()
        if positions.empty:
            st.info("当前没有 U 本位持仓，或机器人还没有写入仓位快照。")
        else:
            st.dataframe(positions, use_container_width=True, hide_index=True)
            pnl = float(positions["unrealized_pnl"].sum())
            notional = float(positions["notional"].sum())
            margin = float(positions["margin"].sum())
            cols = st.columns(3)
            cols[0].metric("仓位名义价值", f"{notional:,.2f} USDT")
            cols[1].metric("仓位保证金", f"{margin:,.2f} USDT")
            cols[2].metric("仓位浮盈亏", f"{pnl:,.2f} USDT")

    with tab_candidates:
        st.markdown("### 最新妖币候选")
        latest_cycles = read_table("select id from cycles order by id desc limit 1")
        latest_id = int(latest_cycles.iloc[0]["id"]) if not latest_cycles.empty else 0
        candidates = read_table(
            """
            select rank, symbol, yaobi_score, passed_min_score, stage, price, change_24h, change_5, change_15,
                   volume_24h, volume_spike, funding_rate, avg_funding, funding_neg_streak,
                   oi_usdt, oi_change_pct, ls_ratio, atr_pct
            from candidates
            where cycle_id = ?
            order by rank
            """,
            (latest_id,),
        )
        st.dataframe(candidates, use_container_width=True, hide_index=True)

    with tab_trades:
        st.markdown("### 最新 LLM 交易卡")
        latest_trades = read_table("select * from trades order by id desc limit 1")
        render_trade_card(latest_trades.iloc[0].to_dict() if not latest_trades.empty else {})
        st.markdown("### 历史交易卡")
        trades = read_table(
            """
            select time_utc, action, symbol, stage, confidence, suggested_entry, actual_entry,
                   stop_loss, take_profit_1, leverage, size_pct, status, reason, reasoning
            from trades
            order by id desc
            limit 100
            """
        )
        st.dataframe(trades, use_container_width=True, hide_index=True)

    with tab_reviews:
        st.markdown("### 失败复盘建议池")
        reviews = read_table(
            """
            select time_utc, symbol, realized_pnl, summary, likely_causes,
                   logic_issues, suggested_adjustments, risk_notes, adopted
            from loss_reviews
            order by id desc
            limit 100
            """
        )
        if reviews.empty:
            st.info("还没有失败复盘。模拟盘失败或真实亏损平仓后，LLM 会在这里写建议。")
        else:
            st.dataframe(reviews, use_container_width=True, hide_index=True)

    with tab_logs:
        st.markdown("### 最近日志")
        st.code(latest_log_text(), language="text")

    with tab_settings:
        st.markdown("### 密钥配置状态")
        st.dataframe(env_status(), use_container_width=True, hide_index=True)
        st.markdown("### 策略配置")
        st.json({
            "trading": cfg.get("trading", {}),
            "risk": cfg.get("risk", {}),
            "screener": cfg.get("screener", {}),
            "llm_role": "开仓决策 + 失败复盘",
            "llm_model": os.environ.get("LLM_MODEL", cfg.get("ai", {}).get("model", "")),
            "llm_base_url": os.environ.get("LLM_BASE_URL", ""),
            "bot_container": BOT_CONTAINER_NAME,
        })


if __name__ == "__main__":
    main()
