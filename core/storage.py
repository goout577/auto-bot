import json
import sqlite3
from pathlib import Path
from typing import Iterable

DB_PATH = Path("data/bot.db")


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path = DB_PATH):
    with connect(db_path) as conn:
        conn.executescript(
            """
            create table if not exists cycles (
                id integer primary key autoincrement,
                time_utc text not null,
                cycle_count integer not null,
                equity real,
                balance real,
                positions_count integer,
                day_start_equity real,
                day_low_equity real,
                candidates_count integer,
                decision_action text,
                decision_symbol text,
                result_status text,
                result_reason text,
                raw_json text not null
            );

            create table if not exists candidates (
                id integer primary key autoincrement,
                cycle_id integer not null,
                rank integer not null,
                symbol text not null,
                yaobi_score real,
                stage text,
                price real,
                change_24h real,
                change_5 real,
                change_15 real,
                volume_24h real,
                volume_spike real,
                funding_rate real,
                avg_funding real,
                funding_neg_streak integer,
                oi_usdt real,
                oi_change_pct real,
                ls_ratio real,
                atr_pct real,
                passed_min_score integer,
                raw_json text not null,
                foreign key(cycle_id) references cycles(id)
            );

            create table if not exists trades (
                id integer primary key autoincrement,
                time_utc text not null,
                cycle_id integer,
                action text,
                symbol text,
                stage text,
                confidence integer,
                suggested_entry real,
                actual_entry real,
                stop_loss real,
                take_profit_1 real,
                take_profit_2 real,
                take_profit_3 real,
                leverage integer,
                size_pct real,
                status text,
                reason text,
                reasoning text,
                raw_json text not null,
                foreign key(cycle_id) references cycles(id)
            );

            create table if not exists loss_reviews (
                id integer primary key autoincrement,
                time_utc text not null,
                trade_key text not null unique,
                symbol text,
                realized_pnl real,
                summary text,
                likely_causes text,
                logic_issues text,
                suggested_adjustments text,
                risk_notes text,
                adopted integer default 0,
                raw_json text not null
            );

            create table if not exists account_snapshots (
                id integer primary key autoincrement,
                cycle_id integer,
                time_utc text not null,
                equity real,
                free_usdt real,
                used_usdt real,
                total_usdt real,
                unrealized_pnl real,
                margin_ratio real,
                positions_count integer,
                raw_json text not null,
                foreign key(cycle_id) references cycles(id)
            );

            create table if not exists position_snapshots (
                id integer primary key autoincrement,
                cycle_id integer,
                time_utc text not null,
                symbol text not null,
                side text,
                contracts real,
                entry_price real,
                mark_price real,
                notional real,
                margin real,
                unrealized_pnl real,
                percentage real,
                liquidation_price real,
                leverage text,
                margin_mode text,
                raw_json text not null,
                foreign key(cycle_id) references cycles(id)
            );
            """
        )
        existing = {row["name"] for row in conn.execute("pragma table_info(candidates)").fetchall()}
        if "passed_min_score" not in existing:
            conn.execute("alter table candidates add column passed_min_score integer")


def _dump(data) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


def _insert_account_snapshot(
    conn: sqlite3.Connection,
    *,
    time_utc: str,
    account: dict,
    positions: list[dict],
    cycle_id: int | None,
) -> None:
    conn.execute(
        """
        insert into account_snapshots (
            cycle_id, time_utc, equity, free_usdt, used_usdt, total_usdt,
            unrealized_pnl, margin_ratio, positions_count, raw_json
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            cycle_id,
            time_utc,
            account.get("equity"),
            account.get("free"),
            account.get("used"),
            account.get("total"),
            account.get("unrealized_pnl"),
            account.get("margin_ratio"),
            len(positions),
            _dump(account),
        ),
    )

    for item in positions:
        conn.execute(
            """
            insert into position_snapshots (
                cycle_id, time_utc, symbol, side, contracts, entry_price, mark_price,
                notional, margin, unrealized_pnl, percentage, liquidation_price,
                leverage, margin_mode, raw_json
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cycle_id,
                time_utc,
                item.get("symbol"),
                item.get("side"),
                item.get("contracts"),
                item.get("entry_price"),
                item.get("mark_price"),
                item.get("notional"),
                item.get("margin"),
                item.get("unrealized_pnl"),
                item.get("percentage"),
                item.get("liquidation_price"),
                str(item.get("leverage") or ""),
                item.get("margin_mode"),
                _dump(item),
            ),
        )


def record_account_snapshot(
    *,
    time_utc: str,
    account: dict | None = None,
    positions: Iterable[dict] | None = None,
    cycle_id: int | None = None,
) -> None:
    init_db()
    account = account or {}
    positions = list(positions or [])
    with connect() as conn:
        _insert_account_snapshot(conn, time_utc=time_utc, account=account, positions=positions, cycle_id=cycle_id)


def record_cycle(
    *,
    time_utc: str,
    cycle_count: int,
    equity: float,
    balance: float,
    positions_count: int,
    state: dict,
    candidates: Iterable[dict],
    decision: dict,
    result: dict,
    account: dict | None = None,
    positions: Iterable[dict] | None = None,
) -> int:
    init_db()
    candidates = list(candidates)
    positions = list(positions or [])
    account = account or {}
    payload = {
        "state": state,
        "candidates": candidates,
        "decision": decision,
        "result": result,
        "account": account,
        "positions": positions,
    }
    with connect() as conn:
        cur = conn.execute(
            """
            insert into cycles (
                time_utc, cycle_count, equity, balance, positions_count,
                day_start_equity, day_low_equity, candidates_count,
                decision_action, decision_symbol, result_status, result_reason, raw_json
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                time_utc,
                cycle_count,
                equity,
                balance,
                positions_count,
                float(state.get("day_start_equity") or 0),
                float(state.get("day_low_equity") or 0),
                len(candidates),
                decision.get("action"),
                decision.get("symbol"),
                result.get("status"),
                result.get("reason"),
                _dump(payload),
            ),
        )
        cycle_id = int(cur.lastrowid)

        for rank, item in enumerate(candidates, 1):
            conn.execute(
                """
                insert into candidates (
                    cycle_id, rank, symbol, yaobi_score, stage, price, change_24h, change_5, change_15,
                    volume_24h, volume_spike, funding_rate, avg_funding, funding_neg_streak,
                    oi_usdt, oi_change_pct, ls_ratio, atr_pct, passed_min_score, raw_json
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cycle_id,
                    rank,
                    item.get("symbol"),
                    item.get("yaobi_score"),
                    item.get("stage"),
                    item.get("price"),
                    item.get("change_24h"),
                    item.get("change_5"),
                    item.get("change_15"),
                    item.get("volume_24h"),
                    item.get("volume_spike"),
                    item.get("funding_rate"),
                    item.get("avg_funding"),
                    item.get("funding_neg_streak"),
                    item.get("oi_usdt"),
                    item.get("oi_change_pct"),
                    item.get("ls_ratio"),
                    item.get("atr_pct"),
                    1 if item.get("passed_min_score") else 0,
                    _dump(item),
                ),
            )

        conn.execute(
            """
            insert into trades (
                time_utc, cycle_id, action, symbol, stage, confidence, suggested_entry, actual_entry,
                stop_loss, take_profit_1, take_profit_2, take_profit_3, leverage, size_pct,
                status, reason, reasoning, raw_json
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                time_utc,
                cycle_id,
                decision.get("action"),
                decision.get("symbol"),
                decision.get("stage"),
                decision.get("confidence"),
                decision.get("entry_price"),
                result.get("price"),
                decision.get("stop_loss"),
                decision.get("take_profit_1"),
                decision.get("take_profit_2"),
                decision.get("take_profit_3"),
                decision.get("leverage"),
                decision.get("size_pct"),
                result.get("status"),
                result.get("reason"),
                decision.get("reasoning"),
                _dump({"decision": decision, "result": result}),
            ),
        )

        _insert_account_snapshot(
            conn,
            time_utc=time_utc,
            account=account,
            positions=positions,
            cycle_id=cycle_id,
        )
        return cycle_id


def record_loss_review(*, time_utc: str, trade: dict, review: dict) -> None:
    init_db()
    trade_key = str(trade.get("trade_key") or trade.get("order_id") or trade.get("symbol") or time_utc)
    with connect() as conn:
        conn.execute(
            """
            insert or ignore into loss_reviews (
                time_utc, trade_key, symbol, realized_pnl, summary, likely_causes,
                logic_issues, suggested_adjustments, risk_notes, raw_json
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                time_utc,
                trade_key,
                trade.get("symbol"),
                trade.get("realized_pnl"),
                review.get("summary"),
                _dump(review.get("likely_causes", [])),
                _dump(review.get("logic_issues", [])),
                _dump(review.get("suggested_adjustments", [])),
                _dump(review.get("risk_notes", [])),
                _dump({"trade": trade, "review": review}),
            ),
        )
