# 小明交易心理分析 Agent

基于东方财富交易记录的交易心理复盘工具。自动解析交易数据，拉取市场新闻，通过规则引擎 + LLM 双维度分析个人交易心态与市场情绪，按月生成结构化复盘报告。

---

## 目录

- [快速开始](#快速开始)
- [Step 1: 环境安装](#step-1-环境安装)
- [Step 2: 获取交易数据](#step-2-获取交易数据)
- [Step 3: CSV 格式检查](#step-3-csv-格式检查)
- [Step 4: 配置 LLM API](#step-4-配置-llm-api)
- [Step 5: 生成月度报告](#step-5-生成月度报告)
- [Step 6: 生成进步报告](#step-6-生成进步报告)
- [完整 CLI 参考](#完整-cli-参考)
- [配置文件详解](#配置文件详解)
- [心理偏差检测规则](#心理偏差检测规则)
- [报告结构说明](#报告结构说明)
- [OCR 图片提取（无 CSV 时使用）](#ocr-图片提取无-csv-时使用)
- [项目架构](#项目架构)
- [目录结构](#目录结构)
- [隐私说明](#隐私说明)

---

## 快速开始

```bash
# 1. 安装
cd xiaoming-agent
pip install -e .

# 2. 配置 API（使用 DeepSeek Anthropic 兼容接口）
export ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
export ANTHROPIC_AUTH_TOKEN=sk-xxxxxxxx
export ANTHROPIC_MODEL=deepseek-v4-pro[1m]

# 3. 放入东方财富 CSV 到 data/input/，然后分析
python -m src.main --all
```

---

## Step 1: 环境安装

### 依赖

- Python >= 3.11
- 操作系统: macOS / Linux / Windows

### 安装步骤

```bash
cd xiaoming-agent

# 创建虚拟环境（推荐）
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows

# 安装项目和依赖
pip install -e .
```

这会自动安装所有依赖：
- `pandas` — 数据处理
- `pydantic` — 数据模型校验
- `akshare` — 金融市场数据
- `anthropic` — LLM API 客户端
- `pyyaml` — 配置文件解析
- `python-dotenv` — 环境变量加载

### 验证安装

```bash
python -m src.main --help
```

---

## Step 2: 获取交易数据

### 方式 A: 东方财富直接导出 CSV（推荐）

从东方财富 App 或 PC 端导出交易记录：

1. 打开东方财富 → 交易 → 历史成交
2. 选择日期范围 → 导出 → 保存为 CSV 文件
3. 将 CSV 文件放入 `data/input/` 目录

**文件命名规则**（自动识别，模糊匹配）：

| 关键词 | 对应类型 | 示例文件名 |
|--------|---------|-----------|
| `成交` / `trade` | 历史成交记录 | `历史成交_2026.csv` |
| `资金` / `流水` / `fund` | 资金流水 | `资金流水_2026.csv` |
| `持仓` / `position` | 持仓记录 | `持仓_2026.csv` |

**历史成交 CSV 列名要求**（模糊匹配，不要求完全一致）：

| 列名关键词 | 说明 | 必需 |
|-----------|------|------|
| 成交日期 / 发生日期 | 交易日期，格式 `YYYY-MM-DD` | 是 |
| 成交时间 | 交易时间，格式 `HH:MM:SS` | 否 |
| 证券代码 | 6 位数字 | 是 |
| 证券名称 | 股票名称 | 否 |
| 买卖方向 / 买卖类别 | 买入/卖出 | 是 |
| 成交数量 | 股数 | 是 |
| 成交均价 / 成交价格 | 成交单价 | 是 |
| 成交金额 | 数量 × 价格 | 否 |
| 手续费 | 佣金 | 否 |
| 印花税 | 卖出收取 0.1% | 否 |
| 发生金额 | 净额（正=卖出收入，负=买入支出） | 否 |

支持 GBK / GB2312 / GB18030 / UTF-8 编码自动检测。

### 方式 B: 从截图提取 CSV（无 CSV 导出时）

如果你的交割单只有截图（PNG 格式），可以用 OCR 脚本提取：

```bash
# 1. 安装 OCR 依赖
pip install easyocr

# 2. 将截图放入 pic/ 目录
#    pic/trading_data_1.png
#    pic/trading_data_2.png

# 3. 运行 OCR 提取
python scripts/ocr_to_csv.py

# 4. 检查结果
python -m src.main --inspect
```

OCR 使用 EasyOCR（支持中英文），自动识别表格结构并转换为标准 CSV。注意：
- 截图需要清晰，分辨率建议 1500px 以上
- 部分手写体或模糊文字可能识别不准，建议人工核对
- 生成的文件保存在 `data/input/历史成交_2026.csv`

---

## Step 3: CSV 格式检查

在正式分析前，先检查 CSV 是否被正确解析：

```bash
python -m src.main --inspect
```

输出示例：
```
## trade_history (1 个文件)
  - 历史成交_2026.csv

### trade_history 列名示例
  列名: ['成交日期', '成交时间', '证券代码', '证券名称', '买卖方向', ...]
  行数: 20
```

如果列名和行数正确，说明解析正常。如有问题，常见解决方案：
- 检查 CSV 编码是否为 GBK/UTF-8（脚本自动检测）
- 确认列名包含关键词（如"成交日期"、"证券代码"）
- 用 Excel 打开确认数据完整

---

## Step 4: 配置 LLM API

系统通过 Anthropic SDK 调用 LLM，当前使用 DeepSeek 的 Anthropic 兼容接口。

### 设置环境变量

```bash
# DeepSeek Anthropic-compatible API
export ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
export ANTHROPIC_AUTH_TOKEN=xxx
export ANTHROPIC_MODEL=deepseek-v4-pro[1m]

# 可选：子任务模型
export ANTHROPIC_DEFAULT_HAIKU_MODEL=deepseek-v4-flash
```

环境变量说明：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `ANTHROPIC_BASE_URL` | API 端点地址 | 需设置 |
| `ANTHROPIC_AUTH_TOKEN` | API 认证 Token | 需设置 |
| `ANTHROPIC_MODEL` | 主分析模型 | `deepseek-v4-pro[1m]` |

也可将这些写入 `.env` 文件（项目根目录），启动时自动加载。

### 不使用 LLM

即使不配置 API Key，系统也能用规则引擎完成分析：

```bash
# 跳过 LLM，仅用规则引擎
python -m src.main --month 2026-05 --no-llm
```

规则引擎会识别 6 种心理偏差并给出现象描述，只是没有 AI 叙事的深度分析、综合评分和改进建议。

---

## Step 5: 生成月度报告

### 分析最近一个月

```bash
python -m src.main
```

### 分析指定月份

```bash
python -m src.main --month 2026-04
```

### 分析全部月份

```bash
python -m src.main --all
```

### 运行流程

每次分析按 4 步执行：

```
[1/4] 计算行为指标...
      胜率 40.0%, 总盈亏 -1,614.50, 平均持仓 4.5天

[2/4] 检测心理偏差: 2 个模式
      重仓赌性 (严重度: 0.50)
      过度交易 (严重度: 0.38)

[3/4] 市场环境: 震荡, 指数 +1.2%

[4/4] LLM 深度分析中...
      综合评分: 40/100

报告已生成: data/reports/2026-05.md
```

### 输出

报告保存在 `data/reports/` 目录：
- `data/reports/2026-04.md`
- `data/reports/2026-05.md`

---

## Step 6: 生成进步报告

当有 2 个月以上的月度报告后，生成跨月对比：

```bash
python -m src.main --progress
```

进步报告包含：
- **月度评分趋势表** — 各月评分、胜率、持仓天数、恐慌卖出次数对比
- **核心问题追踪** — 哪些问题持续存在
- **已改善问题** — 改善点确认
- **趋势分析** — LLM 评估改进速度
- **下阶段建议** — 下一步的具体行动

---

## 完整 CLI 参考

```
xiaoming-agent [选项]

数据输入:
  --month YYYY-MM     指定分析月份（如 2026-05）
  --all               分析 CSV 中所有可用月份
  --inspect           仅检查 CSV 列名和行数，不做分析

分析:
  --no-llm            不使用 LLM，仅规则引擎分析
  --progress          生成跨月进步报告（需 >=2 个月份的历史报告）

配置:
  --config path.yaml  指定配置文件路径（默认 config/config.yaml）
```

### 常见用法组合

```bash
# 首次使用：检查数据
python -m src.main --inspect

# 无 LLM 快速分析
python -m src.main --month 2026-05 --no-llm

# 完整分析全部月份
python -m src.main --all

# 月底复盘：生成进步报告
python -m src.main --progress
```

---

## 配置文件详解

`config/config.yaml`：

```yaml
# LLM 配置
llm:
  provider: claude                    # 固定使用 claude（Anthropic 协议）
  model: deepseek-v4-pro[1m]         # 模型名称
  temperature: 0.2                    # 输出随机性（0=确定，1=自由）
  max_tokens: 4096                    # 最大输出 token

# Claude/Anthropic 连接
claude:
  api_key_env: ANTHROPIC_AUTH_TOKEN   # 认证 Token 的环境变量名
  base_url_env: ANTHROPIC_BASE_URL    # API 端点的环境变量名

# 数据路径（相对于项目根目录）
data:
  input_dir: data/input               # CSV 文件位置
  cache_dir: data/cache               # akshare API 缓存
  reports_dir: data/reports           # 报告输出位置

# 心理偏差检测阈值
psychology_thresholds:
  chasing_highs:
    price_increase_pct: 5.0           # 追涨：买入前 N 日涨幅超此值触发
    lookback_days: 5                  # 追涨：回看天数
  panic_selling:
    max_hold_days: 3                  # 恐慌割肉：买入后 N 日内亏损卖出
  gambling:
    max_position_ratio: 0.3           # 重仓：单票仓位超 30% 触发
    max_concentration: 0.5            # 重仓：前 3 大持仓超 50% 触发
  over_trading:
    max_daily_trades: 4               # 过度交易：单日超 4 笔触发
  anchoring:
    lookback_window: 20               # 锚定效应：回看天数

# 市场数据
market:
  index_codes:
    shanghai: sh000001                # 上证指数
    shenzhen: sz399001                # 深证成指
    chi_next: sz399006                # 创业板指
  rate_limit_seconds: 0.5             # akshare API 调用间隔
  cache_ttl_hours: 24                 # 缓存有效期
```

### 调整阈值示例

如果你交易较稳健，可以收紧阈值：

```yaml
psychology_thresholds:
  panic_selling:
    max_hold_days: 1       # 缩短至 1 天（更严格定义恐慌）
  gambling:
    max_position_ratio: 0.2  # 单票超 20% 即报警
```

---

## 心理偏差检测规则

规则引擎（不依赖 LLM）自动检测 6 种交易心理问题。每种偏差包含严重度（0-1）、具体交易证据和改进建议。

### 1. 追涨杀跌

**数据来源**：akshare 个股历史行情

**检测逻辑**：
1. 对每笔买入，查询买入前 N 日（默认 5 日）股价涨幅
2. 涨幅超过阈值（默认 5%）= 追涨
3. 统计追涨次数 / 总买入次数 → 严重度

**改进建议**：
- 买入前确认不是因为看到上涨才追入
- 设定参考价格线（如均线），只在回调到线附近买入

### 2. 恐慌割肉

**数据来源**：交易记录

**检测逻辑**：
1. 对每笔卖出，找到对应的同股票买入
2. 持有天数 ≤ 3 天 且 亏损 = 恐慌卖出
3. 统计恐慌次数 / 总卖出次数 → 严重度

**改进建议**：
- 买入前预设定止损位，盘中有明确信号才卖出
- 给每笔交易至少 5 个交易日观察期（除非触及预设止损）

### 3. 犹豫踏空

**数据来源**：交易记录

**检测逻辑**：
1. 找到「卖出后又在更高价买回」的模式
2. 重新买入价高于之前卖出价 5% 以上 = 踏空追回
3. 统计次数 → 严重度

**改进建议**：
- 卖出时记录明确原因，事后复盘
- 对熟悉标的采用分批卖出而非一次性清仓

### 4. 重仓赌性

**数据来源**：交易记录

**检测逻辑**：
1. 单笔买入金额 / 总资金 > 30% = 单票重仓
2. 前 3 大持仓金额合计 / 总资金 > 50% = 集中度过高
3. 命中任一条件 → 严重度 0.5，全中 → 1.0

**改进建议**：
- 单票不超过总资金 30%
- 至少分散到 3-5 只不同行业股票

### 5. 过度交易

**数据来源**：交易记录

**检测逻辑**：
1. 按交易日统计交易笔数
2. 单日 > 4 笔 = 过度交易
3. 日均交易频率 > 2 次 = 整体偏高频

**改进建议**：
- 限制单日不超过 4 笔
- 每笔交易间隔至少 30 分钟冷静期

### 6. 锚定效应

**数据来源**：交易记录

**检测逻辑**：
1. 找到卖出价接近买入成本价（偏差 < 2%）的交易
2. 说明交易者被成本价锚定，而非基于市场判断
3. 出现 ≥ 2 次 = 检出

**改进建议**：
- 成本价只是心理锚点，不影响未来走势
- 尝试在交易软件中隐藏成本价显示

---

## 报告结构说明

### 月度报告（7 个部分）

#### 1. 本月概览
关键量化指标一览表：交易天数、总交易次数、买卖次数、涉及股票数、胜率、总盈亏、总手续费、最大单笔盈亏、平均持仓、日均交易频率。

#### 2. 交易行为分析
- **持仓时间分布**：日内/短线/中线/长线/超长线各占比
- **交易频率**：日均交易次数、最大连亏次数、最大仓位占比
- 自动产出简要分析（如"超过 60% 持仓在 3 天以内，显著短线倾向"）

#### 3. 心理偏差检测
规则引擎输出，按严重度排序：
- 🔴 严重 ≥ 0.7 | 🟡 中等 0.4-0.7 | 🟢 轻微 < 0.4
- 每项含：出现次数、具体交易证据（日期+股票+价格）、改进建议

#### 4. 市场环境对照
- 上证指数同期趋势（上涨/震荡/下跌）、涨跌幅、波动率状态
- 相关行业板块同期涨跌
- 市场情绪标签（乐观/中性/悲观）
- 相关个股新闻摘要

#### 5. AI 深度分析
LLM 生成，包含：
- **综合评分**（0-100）
- **总结**：2-3 句话概述本月特征
- **市场匹配度**：个人操作与大盘走势的对应关系分析
- **核心问题**：最严重 3 个问题
- **优势**：做得好的方面
- **改进建议**：3-5 条具体可操作建议

#### 6. 综合评分
评分卡：

| 分数 | 评级 |
|------|------|
| 80-100 | 良好 |
| 60-79 | 有待改进 |
| <60 | 需要重点关注 |

#### 7. 下月关注点
可勾选的 checklist，如：
- [ ] 将单日交易次数控制在 2 次以内
- [ ] 降低前三大持仓集中度至 40% 以下

### 进步报告

跨月对比报告，包含：
1. **总体评估** — LLM 对整体进步情况的判断
2. **月度评分趋势表** — 各指标按月对比
3. **趋势分析** — 改进速度和持久性评估
4. **持续问题** — 未解决的核心问题
5. **已改善问题** — 进步的方面
6. **下阶段重点** — 建议行动

---

## OCR 图片提取（无 CSV 时使用）

### 安装

```bash
pip install easyocr
```

### 使用方法

```bash
# 1. 把交割单截图放 pic/ 目录
ls pic/
# trading_data_1.png
# trading_data_2.png

# 2. 运行 OCR
python scripts/ocr_to_csv.py
```

### 输出示例

```
正在加载 OCR 模型...
正在识别图片文字...
识别到 21 行文本
  2026-05-20 买入 三环集团(300408) 200股 × 94.970
  2026-05-20 卖出 特变电工(600089) 700股 × 26.880
  ...
✅ 已生成: data/input/历史成交_2026.csv
共 20 条交易记录

--- 验证 ---
xiaoming-agent 解析通过: 20 条记录
  2026-04: 8 笔
  2026-05: 12 笔
```

### OCR 注意事项

- 截图分辨率建议 ≥ 1500px 宽
- 支持中英文混合识别
- 自动修正常见误识别（如"特娈电工"→"特变电工"）
- 数值字段通过乘积约束（数量×价格≈金额）反向纠正 OCR 错误
- 图片按列 x 坐标自动对齐表格结构
- **建议人工核对生成结果**，特别是不常见的股票名称

### OCR 工作原理

```
PNG 图片 → EasyOCR 文字识别+坐标 → 按 y 聚行 → 行内模式匹配
→ 正则分字段（日期/时间/代码/名称/方向/数值）
→ 乘积约束反推 数量×价格≈金额 → 生成标准 CSV
```

---

## 项目架构

```
                          ┌──────────────────────┐
                          │   东方财富 CSV 文件     │
                          │   data/input/*.csv    │
                          └──────────┬───────────┘
                                     │
                                     ▼
                          ┌──────────────────────┐
                          │    DataIngestion      │
                          │    csv_reader.py      │
                          │    ┌────────────────┐ │
                          │    │ 编码检测 GBK/   │ │
                          │    │ UTF-8 自动切换  │ │
                          │    │ 列名模糊匹配    │ │
                          │    │ 类型转换+清洗   │ │
                          │    └───────┬────────┘ │
                          │            │          │
                          │    ┌───────▼────────┐ │
                          │    │ trade_history  │ │
                          │    │ fund_flow      │ │
                          │    │ positions      │ │
                          │    └───────┬────────┘ │
                          └──────────────┬───────┘
                                         │
                    ┌────────────────────┼────────────────────┐
                    │                    │                    │
                    ▼                    ▼                    ▼
          ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
          │  akshare API    │  │  BehaviorMetrics │  │  Psychology     │
          │  ┌────────────┐ │  │  ┌────────────┐  │  │  Detector       │
          │  │ NewsFetcher│ │  │  │ 胜率/持仓  │  │  │  ┌────────────┐ │
          │  │ stock_news │ │  │  │ 天数/频率  │  │  │  │ 追涨杀跌   │ │
          │  │ _em()      │ │  │  │ 仓位/回撤  │  │  │  │ 恐慌割肉   │ │
          │  ├────────────┤ │  │  │ FIFO 匹配  │  │  │  │ 犹豫踏空   │ │
          │  │IndexFetcher│ │  │  └────────────┘  │  │  │ 重仓赌性   │ │
          │  │ 上证/深证  │ │  │                  │  │  │ 过度交易   │ │
          │  ├────────────┤ │  │                  │  │  │ 锚定效应   │ │
          │  │BoardFetcher│ │  │                  │  │  └────────────┘ │
          │  │ 行业板块   │ │  │                  │  │                  │
          │  ├────────────┤ │  │                  │  │                  │
          │  │StockFetcher│ │  │                  │  │                  │
          │  │ 个股行情   │ │  │                  │  │                  │
          │  └────────────┘ │  │                  │  │                  │
          │  24h 缓存       │  │                  │  │                  │
          └────────┬────────┘  └────────┬─────────┘  └────────┬─────────┘
                   │                    │                      │
                   ▼                    ▼                      ▼
          ┌─────────────────────────────────────────────────────────┐
          │                    MarketSentiment                       │
          │  大盘趋势 + 板块表现 + 市场情绪 + 相关新闻               │
          └────────────────────────┬────────────────────────────────┘
                                   │
                                   ▼
          ┌─────────────────────────────────────────────────────────┐
          │                      LLM Analyzer                        │
          │  组装 prompt(交易摘要+指标+偏差+市场) → LLM → 结构化 JSON │
          └────────────────────────┬────────────────────────────────┘
                                   │
                                   ▼
          ┌─────────────────────────────────────────────────────────┐
          │                    Report Generator                       │
          │  月度报告 (7 章节) / 进步报告 (6 章节) → Markdown 文件    │
          └─────────────────────────────────────────────────────────┘
```

### 数据流说明

1. **DataIngestion**：纯本地处理，不联网。读取 CSV → 编码检测 → 列名模糊匹配 → Pydantic 数据校验 → `TradeRecord` 列表
2. **MarketData**：联网拉取市场数据，24 小时文件缓存。akshare API 调用的响应缓存为 JSON 文件，避免重复请求
3. **BehaviorMetrics**：纯计算层。FIFO 匹配买卖对 → 计算胜率/持仓天数/连亏/仓位等
4. **PsychologyDetector**：规则引擎。读取量化指标 + 个股行情（可选）→ 六种偏差检测
5. **MarketSentiment**：组装市场上下文（大盘趋势 + 行业表现 + 情绪标签 + 新闻列表）
6. **LLM Analyzer**：将前三层输出格式化为 prompt → 调用 LLM → 解析结构化 JSON → Pydantic 校验
7. **Report Generator**：合并所有分析结果 → 渲染 Markdown 模板 → 写入文件

---

## 目录结构

```
xiaoming-agent/
├── README.md                        # 本文档
├── pyproject.toml                    # 项目配置和依赖
├── .env.example                      # 环境变量模板
│
├── config/
│   └── config.yaml                   # 运行时配置（阈值、路径、LLM）
│
├── data/
│   ├── input/                        # ← CSV 文件放这里
│   │   └── 历史成交_2026.csv        #    东方财富导出的交易明细
│   ├── cache/                        # akshare API 缓存（自动生成）
│   └── reports/                      # 生成的 Markdown 报告
│       ├── 2026-04.md
│       ├── 2026-05.md
│       └── 进步报告.md
│
├── pic/                              # ← 交割单截图放这里（无 CSV 时）
│   ├── trading_data_1.png
│   └── trading_data_2.png
│
├── scripts/
│   └── ocr_to_csv.py                 # PNG → CSV OCR 提取脚本
│
├── src/
│   ├── __init__.py
│   ├── main.py                       # CLI 入口
│   ├── config.py                     # 配置加载
│   │
│   ├── data_ingestion/               # 数据摄入层
│   │   ├── models.py                 #   Pydantic 数据模型
│   │   ├── csv_reader.py             #   CSV 读取 + 编码检测
│   │   ├── trade_history.py          #   历史成交解析
│   │   ├── fund_flow.py              #   资金流水解析
│   │   └── positions.py              #   持仓解析
│   │
│   ├── market_data/                  # 市场数据层
│   │   ├── cache.py                  #   文件缓存（24h TTL）
│   │   ├── news_fetcher.py           #   个股新闻 (akshare)
│   │   ├── index_fetcher.py          #   大盘指数
│   │   ├── board_fetcher.py          #   行业板块
│   │   └── stock_fetcher.py          #   个股行情
│   │
│   ├── analysis/                     # 分析引擎层
│   │   ├── behavior_metrics.py       #   量化行为指标
│   │   ├── psychology_detector.py    #   规则引擎心理检测
│   │   ├── market_sentiment.py       #   市场环境分析
│   │   └── llm_analyzer.py           #   LLM 分析编排
│   │
│   ├── llm/                          # LLM 集成层
│   │   ├── client.py                 #   Anthropic SDK 客户端
│   │   ├── prompts.py                #   中文提示词模板
│   │   └── schemas.py                #   LLMConfig 模型
│   │
│   └── reporting/                    # 报告生成层
│       ├── templates.py              #   Markdown 模板
│       └── report_generator.py       #   报告组装逻辑
│
└── tests/                            # 测试
    └── __init__.py
```

---

## 隐私说明

- **交易数据完全本地处理**：CSV 解析、指标计算、规则检测均在本地完成
- **LLM 分析仅发送摘要**：发送给 LLM 的是脱敏后的交易摘要（日期、股票代码、数量、价格），不含账户号、姓名、资金余额等个人信息
- **akshare 仅查询公开数据**：新闻、指数、行情等均为公开金融市场数据
- **不上传任何文件**：CSV 文件和截图不会上传到任何服务器
- **API 缓存本地**：akshare 缓存在 `data/cache/`，不含交易数据
