# OKX 测试盘妖币逼空机器人

这是一个用于 OKX 测试盘的 USDT 合约机器人。它会扫描山寨合约里可能出现的“逼空妖币”，用固定规则生成交易卡，通过风控后自动在测试盘下单。

当前版本的 LLM 只做一件事：**真实亏损后的复盘分析**。它不参与实时开仓，不决定买哪个币，也不能自动改参数。

## 它会做什么

1. 扫描 OKX USDT 本位合约市场。
2. 排除 BTC、ETH、稳定币和不适合小资金的合约。
3. 按资金费率、成交量、持仓量、短线涨幅、多空比例、波动率计算妖币分。
4. 固定规则生成交易卡：动作、币种、开仓价、止损、止盈、杠杆、仓位和理由。
5. 通过风控后，在 OKX 测试盘市价开仓，并立即挂止损止盈。
6. 如果真实亏损平仓，才调用 LLM 生成复盘建议，写入前端“复盘建议池”。
7. 每轮数据写入 SQLite，前端面板可以查看。

## 配置 `.env`

复制 `.env.example` 为 `.env`，然后填入真实密钥。

```env
OKX_API_KEY=你的OKX测试盘API_KEY
OKX_SECRET_KEY=你的OKX测试盘SECRET_KEY
OKX_PASSPHRASE=你的OKX测试盘PASSPHRASE
OKX_TESTNET=true

LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=你的LLM_KEY
LLM_MODEL=gpt-4.1-mini

HTTP_PROXY_URL=
HTTPS_PROXY_URL=

CRYPTOPANIC_TOKEN=
COINGECKO_DEMO_KEY=
```

第三方 LLM 只要兼容 OpenAI 格式即可。LLM 只用于亏损复盘，不参与实时开仓。

## Docker 运行

确保 `.env` 和 `state.json` 存在。如果没有 `state.json`：

```powershell
copy state.example.json state.json
```

构建并启动：

```bash
docker compose build
docker compose up -d
```

查看状态：

```bash
docker compose ps
docker compose logs -f bot
```

前端默认端口：

```text
http://127.0.0.1:18601
```

如果 Windows 访问 WSL Docker 端口不稳定，可以使用项目里的转发脚本把前端转到 `18602`。

## 前端面板

前端包含：

- 账户曲线：U 本位权益、可用保证金、已用保证金、浮动盈亏。
- 实时仓位：只看 USDT 本位仓位。
- 妖币榜：候选币评分、阶段、资金费率、放量、持仓量变化。
- 交易卡：规则生成的开仓计划、风控结果和执行结果。
- 复盘建议池：真实亏损后由 LLM 给出的策略调整建议。
- 日志和配置：查看运行状态和密钥配置情况。

## 当前默认风控

- 只跑 OKX 测试盘。
- 每仓 10% 保证金。
- 最多 10 仓。
- 最高 8 倍杠杆。
- 每日最大回撤 20% 后停止开新仓。
- 同币同方向冷却 30 分钟。
- 开仓必须有止损和止盈。
- 第一止盈必须满足最低盈亏比。
- 止损止盈挂不上会补挂；补挂失败会尝试立刻退出。

## GitHub 发布规则

每次大更新完成后：

1. 运行语法检查和测试。
2. Docker 构建并启动验证。
3. 提交到 GitHub。
4. 打版本标签，例如 `v0.3.0`。

## 风险说明

这是测试盘机器人，不保证收益。它的主要价值是积累数据、验证筛选逻辑、复盘亏损原因，并逐步改进规则。

不要把 `.env` 发给别人，也不要上传到 GitHub。
