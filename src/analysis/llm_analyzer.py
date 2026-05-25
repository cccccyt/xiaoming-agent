from ..data_ingestion.models import (
    BehaviorMetrics,
    LLMAnalysisResult,
    MarketContext,
    MonthlyAnalysis,
    PsychologyPattern,
    TradeRecord,
)
from ..llm.client import LLMClient
from ..llm.prompts import (
    MONTHLY_ANALYSIS_PROMPT,
    PROGRESS_PROMPT,
    SYSTEM_PROMPT,
    TRADE_SUMMARY_TEMPLATE,
)
from ..llm.schemas import LLMConfig


class LLMAnalyzer:
    def __init__(self, client: LLMClient):
        self.client = client

    def analyze_month(
        self,
        trades: list[TradeRecord],
        metrics: BehaviorMetrics,
        market_context: MarketContext,
        rule_patterns: list[PsychologyPattern],
        year_month: str,
    ) -> LLMAnalysisResult:
        trade_details_lines: list[str] = []
        for t in sorted(trades, key=lambda x: x.trade_date)[:50]:
            emoji = "🟢" if t.is_buy else "🔴"
            trade_details_lines.append(
                f"{emoji} {t.trade_date} {t.direction} {t.stock_name}({t.stock_code}) "
                f"{t.quantity}股 × {t.price} = {t.amount:,.0f}"
            )

        total_amount = sum(abs(t.net_amount) for t in trades)
        total_pnl = metrics.total_pnl
        win_rate = metrics.win_rate
        avg_hold = metrics.avg_hold_days
        buys = [t for t in trades if t.is_buy]
        sells = [t for t in trades if not t.is_buy]

        trade_summary = TRADE_SUMMARY_TEMPLATE.format(
            count=len(trades),
            buy_count=len(buys),
            sell_count=len(sells),
            stock_count=metrics.unique_stocks,
            total_amount=total_amount,
            total_pnl=total_pnl,
            win_rate=win_rate,
            avg_hold=avg_hold,
            trade_details="\n".join(trade_details_lines[:40]),
        )

        behavior_lines = [
            f"- 交易总数: {metrics.total_trades}",
            f"- 胜率: {metrics.win_rate}%",
            f"- 总盈亏: {metrics.total_pnl:+,.2f}",
            f"- 总手续费: {metrics.total_commission:,.2f}",
            f"- 平均持仓: {metrics.avg_hold_days} 天 / 中位数: {metrics.median_hold_days} 天",
            f"- 最长持仓: {metrics.max_hold_days} 天 / 最短: {metrics.min_hold_days} 天",
            f"- 最大连亏次数: {metrics.max_consecutive_losses}",
            f"- 最大单笔盈利: {metrics.largest_win:+,.2f}",
            f"- 最大单笔亏损: {metrics.largest_loss:+,.2f}",
            f"- 日均交易频率: {metrics.daily_trade_frequency} 次",
            f"- 最大单笔仓位占比: {metrics.max_position_ratio * 100:.0f}%",
            f"- 恐慌卖出次数: {metrics.panic_sell_count}",
            f"- 追涨买入次数: {metrics.chasing_buy_count}",
        ]

        rule_lines: list[str] = []
        for p in rule_patterns:
            rule_lines.append(f"\n### {p.pattern_type} (严重度: {p.severity})")
            rule_lines.append(f"出现次数: {p.frequency}")
            rule_lines.append("证据:")
            for e in p.evidence[:5]:
                rule_lines.append(f"  - {e}")

        market_lines = [
            f"- 大盘趋势: {market_context.index_trend}",
            f"- 大盘涨跌: {market_context.index_return:+.1f}%",
            f"- 波动率环境: {market_context.volatility_regime}",
            f"- 市场情绪: {market_context.market_sentiment_label}",
        ]
        if market_context.sector_performance:
            market_lines.append("- 行业板块表现:")
            for board, perf in list(market_context.sector_performance.items())[:5]:
                market_lines.append(f"  - {board}: {perf:+.1f}%")

        user_prompt = MONTHLY_ANALYSIS_PROMPT.format(
            year_month=year_month,
            trade_summary=trade_summary,
            behavior_metrics="\n".join(behavior_lines),
            market_context="\n".join(market_lines),
            rule_findings="\n".join(rule_lines) if rule_lines else "无",
        )

        return self.client.analyze(SYSTEM_PROMPT, user_prompt, LLMAnalysisResult)

    def analyze_progress(
        self, monthly_results: list[dict]
    ) -> dict:
        historical = []
        for m in monthly_results:
            historical.append(
                f"- {m['year_month']}: 综合评分 {m.get('score', 'N/A')}"
            )

        user_prompt = PROGRESS_PROMPT.format(
            historical_scores="\n".join(historical),
        )

        result = self.client.chat(SYSTEM_PROMPT, user_prompt)
        import json

        return json.loads(result)
