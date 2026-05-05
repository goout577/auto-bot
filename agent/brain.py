import json

from loguru import logger
from openai import OpenAI


DECISION_PROMPT = """你是运行在 OKX 测试盘的妖币逼空交易助手。
你的任务是根据候选榜做开仓建议，输出完整交易卡。

核心目标：
- 只做 OKX 测试盘。
- 主方向是山寨妖币逼空追多。
- 只有候选币达到开仓线，才允许建议开仓。
- 如果没有清晰机会，必须 hold。

重点看：
1. 妖币分是否达到开仓线。
2. 资金费率是否偏负，空头是否拥挤。
3. 5m/15m 是否同步上涨。
4. 成交量是否突然放大。
5. 持仓量是否跟随增加。
6. 是否有末端风险或假突破。

开仓要求：
- open_long/open_short 必须给 symbol、entry_price、stop_loss、take_profit_1。
- 尽量给 take_profit_2 和 take_profit_3。
- 第一止盈必须比止损距离更远。
- 仓位默认 10%，杠杆建议 3-8。
- 不要为了交易而交易，错过比乱做更好。
"""


DECISION_TOOL = {
    "type": "function",
    "function": {
        "name": "trading_decision",
        "description": "提交 OKX 测试盘交易卡",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["open_long", "open_short", "close_all", "hold"]},
                "symbol": {"type": "string"},
                "stage": {"type": "string", "enum": ["逼空启动", "逼空加速", "末端风险", "假突破", "观察"]},
                "entry_price": {"type": "number"},
                "stop_loss": {"type": "number"},
                "take_profit_1": {"type": "number"},
                "take_profit_2": {"type": "number"},
                "take_profit_3": {"type": "number"},
                "leverage": {"type": "integer", "minimum": 1, "maximum": 10},
                "size_pct": {"type": "number", "minimum": 1, "maximum": 20},
                "confidence": {"type": "integer", "minimum": 1, "maximum": 10},
                "reasoning": {"type": "string"},
            },
            "required": ["action", "confidence", "reasoning"],
        },
    },
}


REVIEW_PROMPT = """你是 OKX 测试盘妖币逼空机器人的失败复盘教练。
你要复盘两类失败：
1. 测试盘真实亏损平仓。
2. 模拟盘/测试盘中，LLM 给出开仓建议但被风控拦截、下单失败、保护单失败或执行失败。

你的目标不是继续喊单，而是帮助我们调整整个机器人逻辑，避免同类失败重复出现。
你不能直接修改参数，不能要求马上加仓，不能要求放宽风控。
你只能给“建议池”内容，供人工或下一版策略审核。
"""


REVIEW_TOOL = {
    "type": "function",
    "function": {
        "name": "failure_review",
        "description": "提交失败复盘建议",
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "likely_causes": {"type": "array", "items": {"type": "string"}},
                "logic_issues": {"type": "array", "items": {"type": "string"}},
                "suggested_adjustments": {"type": "array", "items": {"type": "string"}},
                "risk_notes": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["summary", "likely_causes", "logic_issues", "suggested_adjustments", "risk_notes"],
        },
    },
}


def normalize_decision(decision: dict, default_size_pct: float = 10.0) -> dict:
    decision = dict(decision or {})
    decision.setdefault("action", "hold")
    decision.setdefault("stage", "观察")
    decision.setdefault("size_pct", default_size_pct)
    decision.setdefault("leverage", 5)
    decision.setdefault("confidence", 0)
    decision.setdefault("reasoning", "LLM 未给出明确理由")
    decision["decision_source"] = "llm"
    return decision


def make_decision(context: str, ai_cfg: dict, default_size_pct: float = 10.0) -> dict:
    client = OpenAI(base_url=ai_cfg["base_url"], api_key=ai_cfg["api_key"])
    try:
        response = client.chat.completions.create(
            model=ai_cfg["model"],
            max_tokens=1000,
            tools=[DECISION_TOOL],
            tool_choice={"type": "function", "function": {"name": "trading_decision"}},
            messages=[
                {"role": "system", "content": DECISION_PROMPT},
                {"role": "user", "content": context},
            ],
        )
        tool_calls = response.choices[0].message.tool_calls
        if tool_calls:
            return normalize_decision(json.loads(tool_calls[0].function.arguments), default_size_pct)
    except Exception as e:
        logger.error(f"LLM 决策调用失败: {e}")

    return normalize_decision({"action": "hold", "confidence": 0, "reasoning": "LLM 决策调用失败，强制等待"}, default_size_pct)


def review_failure(trade: dict, ai_cfg: dict) -> dict:
    client = OpenAI(base_url=ai_cfg["base_url"], api_key=ai_cfg["api_key"])
    context = json.dumps(trade, ensure_ascii=False, default=str)
    try:
        response = client.chat.completions.create(
            model=ai_cfg["model"],
            max_tokens=1000,
            tools=[REVIEW_TOOL],
            tool_choice={"type": "function", "function": {"name": "failure_review"}},
            messages=[
                {"role": "system", "content": REVIEW_PROMPT},
                {"role": "user", "content": context},
            ],
        )
        tool_calls = response.choices[0].message.tool_calls
        if tool_calls:
            review = json.loads(tool_calls[0].function.arguments)
            review["review_source"] = "llm"
            return review
    except Exception as e:
        logger.error(f"LLM 失败复盘调用失败: {e}")

    return {
        "summary": "LLM 复盘失败，保留失败记录等待人工查看。",
        "likely_causes": [],
        "logic_issues": [],
        "suggested_adjustments": [],
        "risk_notes": ["复盘调用失败，不自动调整任何规则。"],
        "review_source": "fallback",
    }


def review_loss_trade(trade: dict, ai_cfg: dict) -> dict:
    return review_failure(trade, ai_cfg)
