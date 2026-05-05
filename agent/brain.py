import json

from loguru import logger
from openai import OpenAI


REVIEW_PROMPT = """你是 OKX 测试盘妖币逼空机器人的亏损复盘教练。
你不能给实时开仓建议，不能要求马上加仓或放宽风控。
你的任务是：根据一笔真实亏损交易，指出这次亏损可能暴露了哪些筛选、入场、止损、止盈或风控问题，并给出下一版策略可以考虑的规则调整建议。
建议必须面向“整个机器人逻辑”，不要只解释单笔交易。
"""


REVIEW_TOOL = {
    "type": "function",
    "function": {
        "name": "loss_review",
        "description": "提交亏损复盘建议",
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


def review_loss_trade(trade: dict, ai_cfg: dict) -> dict:
    client = OpenAI(base_url=ai_cfg["base_url"], api_key=ai_cfg["api_key"])
    context = json.dumps(trade, ensure_ascii=False, default=str)
    try:
        response = client.chat.completions.create(
            model=ai_cfg["model"],
            max_tokens=1000,
            tools=[REVIEW_TOOL],
            tool_choice={"type": "function", "function": {"name": "loss_review"}},
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
        logger.error(f"LLM 亏损复盘失败: {e}")

    return {
        "summary": "LLM 复盘失败，保留亏损记录等待人工查看。",
        "likely_causes": [],
        "logic_issues": [],
        "suggested_adjustments": [],
        "risk_notes": ["复盘调用失败，不自动调整任何规则。"],
        "review_source": "fallback",
    }
