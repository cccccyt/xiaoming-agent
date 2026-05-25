from datetime import date

from ..data_ingestion.models import (
    BehaviorMetrics,
    PsychologyPattern,
    TradeRecord,
)
from ..market_data.stock_fetcher import StockFetcher


class PsychologyDetector:
    def __init__(self, thresholds: dict, stock_fetcher: StockFetcher | None = None):
        self.thresholds = thresholds
        self.stock_fetcher = stock_fetcher

    def detect_patterns(
        self, trades: list[TradeRecord], metrics: BehaviorMetrics
    ) -> list[PsychologyPattern]:
        if not trades:
            return []

        patterns: list[PsychologyPattern | None] = [
            self._detect_chasing_highs(trades),
            self._detect_panic_selling(trades),
            self._detect_hesitation_miss(trades),
            self._detect_gambling(trades, metrics),
            self._detect_over_trading(trades, metrics),
            self._detect_anchoring(trades),
        ]
        return [p for p in patterns if p is not None]

    def _detect_chasing_highs(
        self, trades: list[TradeRecord]
    ) -> PsychologyPattern | None:
        cfg = self.thresholds.get("chasing_highs", {})
        threshold_pct = cfg.get("price_increase_pct", 5.0)
        lookback = cfg.get("lookback_days", 5)

        evidence: list[str] = []
        chasing_count = 0

        buys = [t for t in trades if t.is_buy]
        for t in buys:
            if self.stock_fetcher:
                try:
                    change = self.stock_fetcher.get_price_change(
                        t.stock_code, t.trade_date, lookback
                    )
                    if change > threshold_pct:
                        chasing_count += 1
                        evidence.append(
                            f"{t.trade_date} 买入 {t.stock_name}({t.stock_code}) "
                            f"价格 {t.price}，此前{lookback}日已上涨 {change}%"
                        )
                except Exception:
                    pass
            else:
                break

        if chasing_count == 0:
            return None

        severity = min(chasing_count / max(len(buys), 1) * 2, 1.0)
        return PsychologyPattern(
            pattern_type="追涨杀跌",
            severity=round(severity, 2),
            evidence=evidence[:10],
            frequency=chasing_count,
            recommendations=[
                "买入前检查：确认不是因为看到上涨才追入",
                "设置买入参考线：只在回调到均线附近时买入",
                f"如果一只股票过去{lookback}天已涨超{threshold_pct}%，等回调再入场",
            ],
        )

    def _detect_panic_selling(
        self, trades: list[TradeRecord]
    ) -> PsychologyPattern | None:
        cfg = self.thresholds.get("panic_selling", {})
        max_hold = cfg.get("max_hold_days", 3)

        evidence: list[str] = []
        panic_count = 0

        buys_by_code: dict[str, list[TradeRecord]] = {}
        for t in trades:
            if t.is_buy:
                buys_by_code.setdefault(t.stock_code, []).append(t)

        for t in trades:
            if t.is_buy:
                continue
            code_buys = buys_by_code.get(t.stock_code, [])
            for buy in code_buys:
                hold_days = (t.trade_date - buy.trade_date).days
                if 0 <= hold_days <= max_hold:
                    pnl_pct = (t.price - buy.price) / buy.price * 100
                    if pnl_pct < 0:
                        panic_count += 1
                        evidence.append(
                            f"{buy.trade_date} 买入 {t.stock_name}({t.stock_code}) "
                            f"价格 {buy.price} → {t.trade_date} 卖出 价格 {t.price}，"
                            f"仅持有 {hold_days} 天，亏损 {abs(pnl_pct):.1f}%"
                        )
                        break

        if panic_count == 0:
            return None

        severity = min(panic_count / max(len([t for t in trades if not t.is_buy]), 1) * 2, 1.0)
        return PsychologyPattern(
            pattern_type="恐慌割肉",
            severity=round(severity, 2),
            evidence=evidence[:10],
            frequency=panic_count,
            recommendations=[
                "每次买入前就设定止损位，不要在盘中因恐慌临时决定卖出",
                f"如果持仓少于{max_hold}天即亏损卖出，大概率是情绪驱动",
                "考虑给每笔交易至少5个交易日的观察期（除触及预设止损外）",
            ],
        )

    def _detect_hesitation_miss(
        self, trades: list[TradeRecord]
    ) -> PsychologyPattern | None:
        evidence: list[str] = []
        miss_count = 0

        sell_dates: dict[str, list[tuple[date, float]]] = {}
        for t in trades:
            if not t.is_buy:
                sell_dates.setdefault(t.stock_code, []).append((t.trade_date, t.price))

        for t in trades:
            if t.is_buy:
                prev_sells = sell_dates.get(t.stock_code, [])
                for sd, sp in prev_sells:
                    if sd < t.trade_date and t.price > sp:
                        increase = (t.price - sp) / sp * 100
                        if increase > 5:
                            miss_count += 1
                            evidence.append(
                                f"{sd} 卖出 {t.stock_name}({t.stock_code}) 价格 {sp} → "
                                f"{t.trade_date} 重新买入 价格 {t.price}，高出 {increase:.1f}%"
                            )
                            break

        if miss_count == 0:
            return None

        return PsychologyPattern(
            pattern_type="犹豫踏空",
            severity=min(miss_count * 0.25, 1.0),
            evidence=evidence[:10],
            frequency=miss_count,
            recommendations=[
                "卖出时要明确原因（止损/止盈/基本面变化），记录在交易日志中",
                "如果频繁出现卖出后追高买回，说明卖出决策不够审慎",
                "对熟悉的标的，可以分批卖出而非一次性清仓",
            ],
        )

    def _detect_gambling(
        self, trades: list[TradeRecord], metrics: BehaviorMetrics
    ) -> PsychologyPattern | None:
        cfg = self.thresholds.get("gambling", {})
        max_ratio = cfg.get("max_position_ratio", 0.3)
        max_concentration = cfg.get("max_concentration", 0.5)

        issues: list[str] = []

        if metrics.max_position_ratio > max_ratio:
            issues.append(
                f"最大单笔仓位占比 {metrics.max_position_ratio * 100:.0f}%，超过 {max_ratio * 100:.0f}% 警戒线"
            )

        stock_amounts: dict[str, float] = {}
        for t in trades:
            stock_amounts[t.stock_code] = stock_amounts.get(t.stock_code, 0) + t.amount
        total = sum(stock_amounts.values())
        top3 = sum(sorted(stock_amounts.values(), reverse=True)[:3])
        concentration = top3 / total if total > 0 else 0
        if concentration > max_concentration:
            issues.append(
                f"前3大持仓集中度 {concentration * 100:.0f}%，超过 {max_concentration * 100:.0f}% 警戒线"
            )

        if not issues:
            return None

        return PsychologyPattern(
            pattern_type="重仓赌性",
            severity=min(len(issues) * 0.5, 1.0),
            evidence=issues,
            frequency=len(issues),
            recommendations=[
                "单只股票仓位不超过总资金30%",
                "至少分散到3-5只不同行业的股票",
                "仓位越重，止损线应该越严格",
            ],
        )

    def _detect_over_trading(
        self, trades: list[TradeRecord], metrics: BehaviorMetrics
    ) -> PsychologyPattern | None:
        cfg = self.thresholds.get("over_trading", {})
        max_daily = cfg.get("max_daily_trades", 4)

        daily_counts: dict[date, int] = {}
        for t in trades:
            daily_counts[t.trade_date] = daily_counts.get(t.trade_date, 0) + 1

        over_trade_days = [
            (d, c) for d, c in daily_counts.items() if c > max_daily
        ]

        if not over_trade_days or metrics.daily_trade_frequency <= 2:
            return None

        evidence = [
            f"{d}: 单日交易 {c} 次，超过 {max_daily} 次警戒线"
            for d, c in sorted(over_trade_days)[:5]
        ]

        return PsychologyPattern(
            pattern_type="过度交易",
            severity=min(metrics.daily_trade_frequency / 8, 1.0),
            evidence=evidence,
            frequency=len(over_trade_days),
            recommendations=[
                f"限制单日交易次数不超过 {max_daily} 次",
                "每笔交易之间至少间隔30分钟冷静期",
                "高频交易通常来自焦虑——问问自己频繁操作的原因",
            ],
        )

    def _detect_anchoring(
        self, trades: list[TradeRecord]
    ) -> PsychologyPattern | None:
        evidence: list[str] = []

        buys_by_code: dict[str, list[TradeRecord]] = {}
        sells_by_code: dict[str, list[TradeRecord]] = {}
        for t in trades:
            if t.is_buy:
                buys_by_code.setdefault(t.stock_code, []).append(t)
            else:
                sells_by_code.setdefault(t.stock_code, []).append(t)

        for code in set(sells_by_code):
            code_sells = sorted(sells_by_code[code], key=lambda x: x.trade_date)
            code_buys = sorted(buys_by_code.get(code, []), key=lambda x: x.trade_date)
            if not code_buys:
                continue

            for t in code_sells:
                related_buys = [b for b in code_buys if b.trade_date < t.trade_date]
                if not related_buys:
                    continue
                buy_avg = sum(b.price for b in related_buys) / len(related_buys)
                if buy_avg > 0 and abs(t.price - buy_avg) / buy_avg < 0.02:
                    evidence.append(
                        f"{t.trade_date} 卖出 {t.stock_name}({code}) 价格 {t.price}，"
                        f"接近成本价 {buy_avg:.2f}（偏差仅 {abs(t.price - buy_avg) / buy_avg * 100:.1f}%）"
                    )

        if len(evidence) < 2:
            return None

        return PsychologyPattern(
            pattern_type="锚定效应",
            severity=min(len(evidence) * 0.2, 1.0),
            evidence=evidence[:10],
            frequency=len(evidence),
            recommendations=[
                "成本价只是心理锚点，不影响股票未来走势",
                "卖出决策应基于当前估值和预期，而非与成本价比较",
                "尝试在交易软件中隐藏成本价，减少锚定影响",
            ],
        )
