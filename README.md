# 小明交易心理分析 Agent

基于东方财富 CSV 交易记录的交易心理复盘工具。读取交易数据 → 拉取市场新闻 → 双维度分析（个人心态 + 市场情绪）→ 生成月度复盘报告。

## 快速开始

```bash
# 1. 安装依赖
cd xiaoming-agent
pip install -e .

# 2. 把东方财富导出的 CSV 放入 data/input/
#    - 历史成交记录 (文件名含"成交"或"trade")
#    - 资金流水 (文件名含"资金"或"流水")
#    - 持仓记录 (文件名含"持仓"或"position")

# 3. 检查 CSV 格式
python -m src.main --inspect

# 4. 配置 LLM API Key（可选，不配也能用规则引擎）
export ANTHROPIC_API_KEY=sk-ant-xxx   # Claude
export DEEPSEEK_API_KEY=sk-xxx        # DeepSeek

# 5. 生成月度报告
python -m src.main --month 2024-01

# 6. 生成全部月份报告
python -m src.main --all

# 7. 生成跨月进步报告
python -m src.main --progress
```

## 数据格式要求

### 历史成交 CSV

东方财富 App/PC 端导出的标准格式，典型列名：

| 列名 | 说明 |
|------|------|
| 成交日期 | 交易日期 |
| 成交时间 | 可选 |
| 证券代码 | 6 位数字代码 |
| 证券名称 | 股票名称 |
| 买卖方向 | 买入/卖出 |
| 成交数量 | 股数 |
| 成交均价 | 成交价格 |
| 成交金额 | 成交数量 × 均价 |
| 手续费 | 佣金 |
| 印花税 | 卖出收取 |
| 发生金额 | 净额（正=卖出收入，负=买入支出） |

列名使用模糊匹配，不要求完全一致。支持 GBK/UTF-8 编码自动检测。

## 心理偏差检测

规则引擎自动识别六种交易心理问题：

| 偏差类型 | 检测规则 |
|---------|---------|
| **追涨杀跌** | 买入前 N 日已涨超阈值（默认 5%）；买入后短期亏损即卖 |
| **恐慌割肉** | 买入后 3 日内亏损卖出 |
| **犹豫踏空** | 卖出后又在更高价格买回同一标的 |
| **重仓赌性** | 单笔仓位 >30% 或前 3 大持仓集中度 >50% |
| **过度交易** | 单日交易 >4 次，高频操作 |
| **锚定效应** | 卖出价格接近成本价（偏差 <2%），被成本价锚定 |

阈值在 `config/config.yaml` 中可调。

## 报告内容

每份月度报告包含 7 个部分：

1. **本月概览** — 交易天数、胜率、盈亏、手续费等关键指标
2. **交易行为分析** — 持仓时间分布、交易频率、仓位分析
3. **心理偏差检测** — 规则引擎发现的偏差模式 + 具体证据 + 改进建议
4. **市场环境对照** — 同期大盘走势、行业板块表现、市场情绪
5. **AI 深度分析** — LLM 综合评分、核心问题、优势、改进建议（需 API Key）
6. **综合评分** — 0-100 分，60 以下需重点关注
7. **下月关注点** — 可操作的改进清单

进步报告汇总多月数据，追踪评分趋势，识别持续问题和已改善问题。

## CLI 参数

```
xiaoming-agent --month 2024-01     # 分析指定月份
xiaoming-agent --all               # 分析所有月份
xiaoming-agent --progress          # 生成跨月进步报告
xiaoming-agent --no-llm            # 不用 LLM，仅规则引擎分析
xiaoming-agent --inspect           # 检查 CSV 列名和格式
xiaoming-agent --config path.yaml  # 指定配置文件
```

## 配置

`config/config.yaml`：

```yaml
llm:
  provider: claude          # claude | deepseek
  model: claude-sonnet-4-20250514
  temperature: 0.2

psychology_thresholds:      # 心理检测阈值
  chasing_highs:
    price_increase_pct: 5.0
    lookback_days: 5
  panic_selling:
    max_hold_days: 3
  gambling:
    max_position_ratio: 0.3
    max_concentration: 0.5

market:
  cache_ttl_hours: 24       # akshare 缓存时间
  rate_limit_seconds: 0.5   # API 调用间隔
```

## 架构

```
[东方财富 CSV]          [akshare API]
      |                      |
      v                      v
  DataIngestion          MarketData
  (解析交易记录)          (新闻/指数/板块)
      |                      |
      +----------+-----------+
                 v
          Analysis Engine
          (行为指标 + 规则检测)
                 |
                 v
          LLM Integration
          (Claude/DeepSeek)
                 |
                 v
          Report Generator
          → data/reports/*.md
```

## 隐私说明

- 交易数据完全在本地处理，不上传
- 仅在启用 LLM 分析时向 API 发送脱敏后的交易摘要（不含账户信息）
- akshare 新闻拉取仅查询公开市场数据
