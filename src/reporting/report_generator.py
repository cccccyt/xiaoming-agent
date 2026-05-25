import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ..data_ingestion.models import (
    BehaviorMetrics,
    LLMAnalysisResult,
    MarketContext,
    MonthlyAnalysis,
    PsychologyPattern,
)
from .templates import monthly_report_template, progress_report_template


class ReportGenerator:
    def __init__(self, reports_dir: Path):
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def generate_monthly_report(self, analysis: MonthlyAnalysis) -> str:
        overview = self._render_overview(analysis)
        behavior = self._render_behavior(analysis)
        psychology = self._render_psychology(analysis.psychology_patterns)
        market = self._render_market(analysis.market_context)
        ai_section = self._render_llm(analysis.llm_result)
        score = self._render_score(analysis)
        plan = self._render_plan(analysis.llm_result)

        content = monthly_report_template(
            year_month=analysis.year_month,
            overview_section=overview,
            behavior_section=behavior,
            psychology_section=psychology,
            market_section=market,
            ai_section=ai_section,
            score_section=score,
            plan_section=plan,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        filename = self.reports_dir / f"{analysis.year_month}.md"
        filename.write_text(content)
        return str(filename)

    def generate_progress_report(
        self, monthly_analyses: list[MonthlyAnalysis], llm_progress: dict | None = None
    ) -> str:
        score_rows: list[str] = []
        score_rows.append(
            "| 月份 | 综合评分 | 胜率 | 持仓天数 | 恐慌卖出 | 追涨买入 |"
        )
        score_rows.append(
            "|------|---------|------|---------|---------|---------|"
        )
        for a in sorted(monthly_analyses, key=lambda x: x.year_month):
            m = a.behavior_metrics
            score = a.llm_result.overall_score if a.llm_result else 0
            score_rows.append(
                f"| {a.year_month} | {score} | "
                f"{m.win_rate if m else 0}% | "
                f"{m.avg_hold_days if m else 0}天 | "
                f"{m.panic_sell_count if m else 0} | "
                f"{m.chasing_buy_count if m else 0} |"
            )

        if llm_progress:
            overall = llm_progress.get("overall_assessment", "")
            trend = llm_progress.get("trend_analysis", "")
            persistent = "\n".join(
                f"- {x}" for x in llm_progress.get("persistent_issues", [])
            )
            improved = "\n".join(
                f"- {x}" for x in llm_progress.get("improved_areas", [])
            )
            next_phase = "\n".join(
                f"- {x}" for x in llm_progress.get("next_phase_recommendations", [])
            )
        else:
            overall = "进度报告生成中..."
            trend = ""
            persistent = ""
            improved = ""
            next_phase = ""

        content = progress_report_template(
            overall=overall,
            score_table="\n".join(score_rows),
            trend_analysis=trend,
            persistent_issues=persistent or "无数据",
            improved=improved or "无数据",
            next_phase=next_phase or "无数据",
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        filename = self.reports_dir / "进步报告.md"
        filename.write_text(content)
        return str(filename)

    def _render_overview(self, analysis: MonthlyAnalysis) -> str:
        m = analysis.behavior_metrics
        if not m:
            return "本月无交易记录"

        rows = [
            "| 指标 | 数值 |",
            "|------|------|",
            f"| 交易天数 | {m.trading_days} |",
            f"| 总交易次数 | {m.total_trades} |",
            f"| 买入次数 | {m.total_buys} |",
            f"| 卖出次数 | {m.total_sells} |",
            f"| 涉及股票数 | {m.unique_stocks} |",
            f"| 胜率 | {m.win_rate}% |",
            f"| 总盈亏 | {m.total_pnl:+,.2f} |",
            f"| 总手续费 | {m.total_commission:,.2f} |",
            f"| 最大单笔盈利 | {m.largest_win:+,.2f} |",
            f"| 最大单笔亏损 | {m.largest_loss:+,.2f} |",
            f"| 平均持仓 | {m.avg_hold_days} 天 |",
            f"| 日均交易频率 | {m.daily_trade_frequency} 次/天 |",
        ]
        return "\n".join(rows)

    def _render_behavior(self, analysis: MonthlyAnalysis) -> str:
        m = analysis.behavior_metrics
        if not m:
            return "无数据"

        cats = {"日内 (≤1天)": 0, "短线 (2-3天)": 0, "中线 (4-7天)": 0, "长线 (8-14天)": 0, "超长线 (>14天)": 0}
        trades = analysis.trades
        buys_by_code: dict[str, list] = {}
        for t in trades:
            if t.is_buy:
                buys_by_code.setdefault(t.stock_code, []).append(t)
        for t in trades:
            if t.is_buy:
                continue
            for buy in buys_by_code.get(t.stock_code, []):
                days = (t.trade_date - buy.trade_date).days
                if days <= 1:
                    cats["日内 (≤1天)"] += 1
                elif days <= 3:
                    cats["短线 (2-3天)"] += 1
                elif days <= 7:
                    cats["中线 (4-7天)"] += 1
                elif days <= 14:
                    cats["长线 (8-14天)"] += 1
                else:
                    cats["超长线 (>14天)"] += 1
                break

        total = sum(cats.values()) or 1
        lines = ["### 持仓时间分布", "", "| 类型 | 笔数 | 占比 |", "|------|------|------|"]
        for label, count in cats.items():
            lines.append(f"| {label} | {count} | {count / total * 100:.1f}% |")

        if m.avg_hold_days <= 5:
            lines.append(
                f"\n**分析**: 超过60%的持仓在3天以内，显示显著的短线交易倾向。"
            )

        lines.append(f"\n### 交易频率")
        lines.append(f"- 平均每日交易 {m.daily_trade_frequency} 次")
        lines.append(f"- 最大连亏次数: {m.max_consecutive_losses}")
        lines.append(f"- 最大单笔仓位占比: {m.max_position_ratio * 100:.0f}%")

        return "\n".join(lines)

    def _render_psychology(self, patterns: list[PsychologyPattern]) -> str:
        if not patterns:
            return "未检测到明显的心理偏差模式"

        severity_map = {0.7: "🔴", 0.4: "🟡", 0.0: "🟢"}
        lines: list[str] = []
        for p in sorted(patterns, key=lambda x: x.severity, reverse=True):
            icon = "🔴" if p.severity >= 0.7 else "🟡" if p.severity >= 0.4 else "🟢"
            lines.append(f"\n### {icon} {p.pattern_type} (严重度: {p.severity:.2f})")
            lines.append(f"\n出现 {p.frequency} 次\n")
            lines.append("**证据**:")
            for e in p.evidence[:5]:
                lines.append(f"1. {e}")
            lines.append("\n**改进建议**:")
            for r in p.recommendations:
                lines.append(f"- {r}")

        return "\n".join(lines)

    def _render_market(self, ctx: MarketContext | None) -> str:
        if not ctx:
            return "市场数据不可用"

        lines = [
            "### 上证指数走势",
            f"- 同期趋势: {ctx.index_trend}",
            f"- 指数涨跌: {ctx.index_return:+.1f}%",
            f"- 波动率: {ctx.volatility_regime}",
            f"- 市场情绪: {ctx.market_sentiment_label}",
        ]

        if ctx.sector_performance:
            lines.append("\n### 板块表现")
            lines.append("| 板块 | 同期涨跌 |")
            lines.append("|------|---------|")
            for board, perf in list(ctx.sector_performance.items())[:10]:
                lines.append(f"| {board} | {perf:+.1f}% |")

        return "\n".join(lines)

    def _render_llm(self, result: LLMAnalysisResult | None) -> str:
        if not result:
            return "AI 分析不可用（请配置 LLM API Key）"

        lines = [
            f"**综合评分: {result.overall_score}/100**",
            "",
            f"### 总结",
            result.summary,
            "",
            f"### 市场匹配度分析",
            result.market_alignment,
            "",
            "### 核心问题",
        ]
        for issue in result.key_issues:
            lines.append(f"- {issue}")
        lines.append("")
        lines.append("### 优势")
        for s in result.strengths:
            lines.append(f"- {s}")
        lines.append("")
        lines.append("### 改进建议")
        for s in result.improvement_suggestions:
            lines.append(f"- {s}")

        return "\n".join(lines)

    def _render_score(self, analysis: MonthlyAnalysis) -> str:
        result = analysis.llm_result
        score = result.overall_score if result else 0
        label = (
            "需要重点关注"
            if score < 60
            else "有待改进"
            if score < 80
            else "良好"
        )

        return (
            f"| 综合评分 | 评级 |\n"
            f"|---------|------|\n"
            f"| **{score}/100** | {label} |"
        )

    def _render_plan(self, result: LLMAnalysisResult | None) -> str:
        if not result or not result.next_month_focus:
            return "请运行分析获取关注点"

        lines = []
        for i, focus in enumerate(result.next_month_focus, 1):
            lines.append(f"- [ ] {focus}")
        return "\n".join(lines)
