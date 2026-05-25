import re
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from .csv_reader import find_column, read_csv_with_encoding, safe_float, safe_int
from .models import TradeRecord


def parse_date(raw: object) -> date | None:
    if raw is None:
        return None
    s = str(raw).strip()
    formats = ["%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%m/%d/%Y", "%d/%m/%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    try:
        return date.fromisoformat(s)
    except (ValueError, TypeError):
        pass
    return None


def parse_trade_history(filepath: Path) -> list[TradeRecord]:
    df = read_csv_with_encoding(filepath)
    records: list[TradeRecord] = []

    date_col = find_column(df, "成交日期") or find_column(df, "日期", "date")
    time_col = find_column(df, "成交时间")
    code_col = find_column(df, "证券代码") or find_column(df, "代码", "code")
    name_col = find_column(df, "证券名称") or find_column(df, "名称", "name")
    dir_col = (
        find_column(df, "买卖方向")
        or find_column(df, "操作", "方向")
        or find_column(df, "买卖", "类型")
    )
    qty_col = find_column(df, "成交数量") or find_column(df, "数量")
    price_col = find_column(df, "成交均价") or find_column(df, "成交价格") or find_column(df, "均价")
    amount_col = find_column(df, "成交金额") or find_column(df, "发生金额") or find_column(df, "金额")
    comm_col = find_column(df, "手续费") or find_column(df, "佣金")
    tax_col = find_column(df, "印花税")
    other_col = find_column(df, "其他费") or find_column(df, "过户费")
    net_col = find_column(df, "发生金额") or find_column(df, "净额")
    market_col = find_column(df, "交易市场") or find_column(df, "市场")

    if not date_col or not code_col:
        raise ValueError(
            f"无法识别必要列。文件列名: {list(df.columns)}, date_col={date_col}, code_col={code_col}"
        )

    for _, row in df.iterrows():
        d = parse_date(row.get(date_col))
        if d is None:
            continue

        code = str(row.get(code_col, "")).strip().zfill(6)
        if not code.isdigit() or len(code) != 6:
            continue

        raw_dir = str(row.get(dir_col, "")).strip() if dir_col else ""
        if "买" in raw_dir or "buy" in raw_dir.lower():
            direction = "买入"
        elif "卖" in raw_dir or "sell" in raw_dir.lower():
            direction = "卖出"
        else:
            continue

        qty = safe_int(row.get(qty_col, 0) if qty_col else 0)
        if qty <= 0:
            continue

        price = safe_float(row.get(price_col) if price_col else 0)
        amount = safe_float(row.get(amount_col) if amount_col else 0)
        if amount == 0:
            amount = price * qty

        commission = safe_float(row.get(comm_col) if comm_col else 0)
        stamp_tax = safe_float(row.get(tax_col) if tax_col else 0)
        other = safe_float(row.get(other_col) if other_col else 0)
        net = safe_float(row.get(net_col) if net_col else 0)
        if net == 0:
            net = amount - commission - stamp_tax - other if direction == "卖出" else -(amount + commission + stamp_tax + other)

        raw_market = str(row.get(market_col, "")) if market_col else ""
        market = "沪" if "沪" in raw_market or "SH" in raw_market.upper() else "深" if "深" in raw_market or "SZ" in raw_market.upper() else ""

        records.append(
            TradeRecord(
                trade_date=d,
                trade_time=str(row.get(time_col, "")) if time_col else None,
                stock_code=code,
                stock_name=str(row.get(name_col, "")).strip() if name_col else "",
                direction=direction,
                quantity=qty,
                price=price,
                amount=amount,
                commission=commission,
                stamp_tax=stamp_tax,
                other_fees=other,
                net_amount=net,
                trade_market=market,
            )
        )

    return records
