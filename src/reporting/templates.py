def monthly_report_template(
    year_month: str,
    overview_section: str,
    behavior_section: str,
    psychology_section: str,
    market_section: str,
    ai_section: str,
    score_section: str,
    plan_section: str,
    generated_at: str = "",
) -> str:
    return f"""# 小明交易心理月报 - {year_month}
{f"生成时间: {generated_at}" if generated_at else ""}

---

## 1. 本月概览

{overview_section}

---

## 2. 交易行为分析

{behavior_section}

---

## 3. 心理偏差检测

{psychology_section}

---

## 4. 市场环境对照

{market_section}

---

## 5. AI 深度分析

{ai_section}

---

## 6. 综合评分

{score_section}

---

## 7. 下月关注点

{plan_section}
"""


def progress_report_template(
    overall: str,
    score_table: str,
    trend_analysis: str,
    persistent_issues: str,
    improved: str,
    next_phase: str,
    generated_at: str = "",
) -> str:
    return f"""# 交易心理进步报告
{f"生成时间: {generated_at}" if generated_at else ""}

---

## 总体评估

{overall}

---

## 月度评分趋势

{score_table}

---

## 趋势分析

{trend_analysis}

---

## 持续问题

{persistent_issues}

---

## 已改善问题

{improved}

---

## 下阶段重点

{next_phase}
"""
