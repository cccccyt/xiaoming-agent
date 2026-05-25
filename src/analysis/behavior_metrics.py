from collections import defaultdict
from datetime import date, timedelta

from ..data_ingestion.models import (
    BehaviorMetrics,
    FundFlowRecord,
    PositionRecord,
    TradeRecord,
)


def _match_trades(trades: list[TradeRecord]) -> list[dict]:
    buys: list[TradeRecord] = []
    completed: list[dict] = []

    for t in sorted(trades, key=lambda x: (x.trade_date, x.stock_code)):
        if t.is_buy:
            buys.append(t)
        else:
            remaining_qty = t.quantity
            sell_amount = t.amount
            for buy in buys:
                if buy.stock_code != t.stock_code:
                    continue
                if remaining_qty <= 0:
                    break
                matched_qty = min(buy.quantity, remaining_qty)
                ratio = matched_qty / t.quantity if t.quantity > 0 else 0
                hold_days = (t.trade_date - buy.trade_date).days
                buy_cost = buy.price * matched_qty
                sell_rev = t.price * matched_qty
                pnl = sell_rev - buy_cost - (t.commission + t.stamp_tax) * ratio - (
                    buy.commission
                ) * (matched_qty / buy.quantity if buy.quantity > 0 else 0)

                completed.append(
                    {
                        "stock_code": t.stock_code,
                        "stock_name": t.stock_name,
                        "buy_date": buy.trade_date,
                        "sell_date": t.trade_date,
                        "buy_price": buy.price,
                        "sell_price": t.price,
                        "quantity": matched_qty,
                        "hold_days": hold_days,
                        "pnl": pnl,
                        "pnl_pct": (pnl / buy_cost * 100) if buy_cost > 0 else 0,
                        "is_win": pnl > 0,
                    }
                )
                buy.quantity -= matched_qty
                remaining_qty -= matched_qty
                if buy.quantity <= 0:
                    buys.remove(buy)

    return completed


def compute_behavior_metrics(
    trades: list[TradeRecord],
    fund_flows: list[FundFlowRecord] | None = None,
    positions: list[PositionRecord] | None = None,
    period: str = "",
) -> BehaviorMetrics:
    if not trades:
        return BehaviorMetrics(period=period)

    fund_flows = fund_flows or []
    positions = positions or []

    matched = _match_trades(trades)
    buys = [t for t in trades if t.is_buy]
    sells = [t for t in trades if not t.is_buy]

    trading_dates = sorted(set(t.trade_date for t in trades))
    trading_days = len(trading_dates)

    wins = [m for m in matched if m["is_win"]]
    losses = [m for m in matched if not m["is_win"]]
    win_rate = len(wins) / len(matched) * 100 if matched else 0.0

    total_pnl = sum(m["pnl"] for m in matched)
    total_commission = sum(t.commission + t.stamp_tax + t.other_fees for t in trades)
    largest_win = max((m["pnl"] for m in wins), default=0.0)
    largest_loss = min((m["pnl"] for m in losses), default=0.0)

    hold_days = [m["hold_days"] for m in matched]
    avg_hold = sum(hold_days) / len(hold_days) if hold_days else 0.0
    sorted_hold = sorted(hold_days)
    median_hold = sorted_hold[len(sorted_hold) // 2] if sorted_hold else 0.0

    max_consecutive = 0
    current_streak = 0
    for m in sorted(matched, key=lambda x: x["sell_date"]):
        if not m["is_win"]:
            current_streak += 1
            max_consecutive = max(max_consecutive, current_streak)
        else:
            current_streak = 0

    amounts = [t.amount for t in trades]
    avg_position = sum(amounts) / len(amounts) if amounts else 0.0
    max_position = max(amounts) if amounts else 0.0
    total_capital = max(
        max((f.balance for f in fund_flows), default=sum(amounts) * 2),
        sum(amounts) * 2,
    )
    max_position_ratio = max_position / total_capital if total_capital > 0 else 0.0

    daily_freq = len(trades) / trading_days if trading_days > 0 else 0.0

    morning_count = sum(
        1 for t in trades if t.trade_time and t.trade_time <= "11:30:00"
    )
    afternoon_count = sum(
        1 for t in trades if t.trade_time and t.trade_time >= "13:00:00"
    )
    total_with_time = morning_count + afternoon_count
    morning_ratio = morning_count / total_with_time if total_with_time > 0 else 0.0
    afternoon_ratio = afternoon_count / total_with_time if total_with_time > 0 else 0.0

    panic_sell_count = sum(1 for m in matched if m["hold_days"] <= 3 and not m["is_win"])

    chasing_buy_count = 0

    unique_stocks = len(set(t.stock_code for t in trades))

    re_buy_turnaround: list[int] = []
    sell_dates_by_stock: dict[str, list[date]] = defaultdict(list)
    buy_dates_by_stock: dict[str, list[date]] = defaultdict(list)
    for t in trades:
        if t.is_buy:
            buy_dates_by_stock[t.stock_code].append(t.trade_date)
        else:
            sell_dates_by_stock[t.stock_code].append(t.trade_date)

    for code in set(sell_dates_by_stock) & set(buy_dates_by_stock):
        sells_sorted = sorted(sell_dates_by_stock[code])
        buys_sorted = sorted(buy_dates_by_stock[code])
        for bd in buys_sorted:
            prev_sells = [sd for sd in sells_sorted if sd < bd]
            if prev_sells:
                gap = (bd - max(prev_sells)).days
                if 0 < gap <= 60:
                    re_buy_turnaround.append(gap)

    avg_turnaround = (
        sum(re_buy_turnaround) / len(re_buy_turnaround) if re_buy_turnaround else 0.0
    )

    return BehaviorMetrics(
        period=period,
        total_trades=len(trades),
        total_buys=len(buys),
        total_sells=len(sells),
        unique_stocks=unique_stocks,
        trading_days=trading_days,
        win_rate=round(win_rate, 1),
        total_pnl=round(total_pnl, 2),
        total_commission=round(total_commission, 2),
        avg_hold_days=round(avg_hold, 1),
        median_hold_days=round(median_hold, 1),
        max_hold_days=max(hold_days) if hold_days else 0,
        min_hold_days=min(hold_days) if hold_days else 0,
        max_consecutive_losses=max_consecutive,
        largest_win=round(largest_win, 2),
        largest_loss=round(largest_loss, 2),
        avg_position_size=round(avg_position, 2),
        max_position_size=round(max_position, 2),
        max_position_ratio=round(max_position_ratio, 2),
        daily_trade_frequency=round(daily_freq, 1),
        morning_trade_ratio=round(morning_ratio, 2),
        afternoon_trade_ratio=round(afternoon_ratio, 2),
        panic_sell_count=panic_sell_count,
        chasing_buy_count=chasing_buy_count,
        avg_turnaround_days=round(avg_turnaround, 1),
    )
