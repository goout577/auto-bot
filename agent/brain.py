import json
from openai import OpenAI
from loguru import logger

SYSTEM_PROMPT = """你是一个自主运行的加密货币合约交易 Agent，管理一个 $50 USDT 的 OKX 合约账户。

核心目标：小资金快速翻倍。

## 妖币识别框架（优先级最高）

市场上存在做市商主导的操纵行情，有两种主要模式：

**逼空型拉盘（The Squeeze）**：
- 特征：资金费率连续多期为负（空头付费给多头）、OI 与价格同步上涨、多头持续占优
- 信号：funding_neg_streak ≥ 2 且 avg_funding < -0.02% → 逼空布局中，空头随时被爆
- 操作：此时做多跟随做市商，止损设在近期支撑，目标是空头被清光前的最高点
- 退出：资金费率转正（多头开始付费）→ 逼空接近尾声，及时止盈

**拉高出货型（Pump and Dump）**：
- 特征：Vol/OI > 15x（成交量相对持仓量异常大，刷量嫌疑）、价格急速拉升后横盘
- 信号：yaobi_risk=HIGH 且价格已涨 50%+ 且无逼空特征 → 大概率出货阶段，不追多
- 操作：避免追高，等待明确回调信号再考虑空

**正常交易信号**（无妖币特征时）：
- 多个技术指标共振：趋势 + 动量 + 情绪至少 2-3 个同向
- 严格止损（1.5x ATR），让盈利奔跑（3x ATR 止盈，R:R ≥ 2:1）

## 信心评分
- 8-10：强烈信号（妖币逼空确认 或 技术多因素完美共振）→ 开仓
- 6-7：较好机会，主要因素对齐 → 可开仓
- < 6：信号不清晰 → 强制 hold

无明确机会时 hold，等待比强行交易更重要。
只通过 trading_decision 工具输出决策，不输出任何自由文本。"""

DECISION_TOOL = {
    "type": "function",
    "function": {
        "name": "trading_decision",
        "description": "提交交易决策",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["open_long", "open_short", "close_all", "hold"],
                    "description": "交易动作"
                },
                "symbol": {
                    "type": "string",
                    "description": "交易对，如 SOL/USDT:USDT（open_long/open_short 时必填）"
                },
                "leverage": {
                    "type": "integer",
                    "minimum": 3,
                    "maximum": 15,
                    "description": "杠杆倍数"
                },
                "size_pct": {
                    "type": "number",
                    "minimum": 10,
                    "maximum": 35,
                    "description": "占账户权益的百分比，用作保证金"
                },
                "sl_pct": {
                    "type": "number",
                    "description": "止损距入场价的百分比"
                },
                "tp_pct": {
                    "type": "number",
                    "description": "止盈距入场价的百分比"
                },
                "confidence": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "description": "信心评分 1-10"
                },
                "reasoning": {
                    "type": "string",
                    "description": "2-3 句分析理由"
                }
            },
            "required": ["action", "confidence", "reasoning"]
        }
    }
}


def make_decision(context: str, ai_cfg: dict) -> dict:
    client = OpenAI(
        base_url=ai_cfg['base_url'],
        api_key=ai_cfg['api_key'],
    )
    try:
        response = client.chat.completions.create(
            model=ai_cfg['model'],
            max_tokens=512,
            tools=[DECISION_TOOL],
            tool_choice={"type": "function", "function": {"name": "trading_decision"}},
            messages=[
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': context},
            ],
        )
        tool_calls = response.choices[0].message.tool_calls
        if tool_calls:
            return json.loads(tool_calls[0].function.arguments)
    except Exception as e:
        logger.error(f"AI 决策调用失败: {e}")

    return {'action': 'hold', 'confidence': 0, 'reasoning': f'API 调用失败，强制 hold'}
