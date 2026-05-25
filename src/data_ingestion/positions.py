from datetime import date, datetime
from pathlib import Path

from .csv_reader import find_column, read_csv_with_encoding, safe_float, safe_int
from .models import PositionRecord


def parse_positions(filepath: Path) -> list[PositionRecord]:
    df = read_csv_with_encoding(filepath)
    records: list[PositionRecord] = []

    code_col = find_column(df, "证券代码") or find_column(df, "代码")
    name_col = find_column(df, "证券名称") or find_column(df, "名称")
    total_col = find_column(df, "持仓数量") or find_column(df, "证券数量") or find_column(df, "当前拥股")
    avail_col = find_column(df, "可用数量") or find_column(df, "可卖数量")
    cost_col = find_column(df, "成本价") or find_column(df, "买入均价") or find_column(df, "参考成本价")
    price_col = find_column(df, "最新价") or find_column(df, "当前价") or find_column(df, "市价")
    mv_col = find_column(df, "市值") or find_column(df, "持仓市值") or find_column(df, "参考市值")
    pnl_col = find_column(df, "浮动盈亏") or find_column(df, "盈亏") or find_column(df, "持仓盈亏")
    pnl_pct_col = find_column(df, "盈亏比例") or find_column(df, "收益率")
    snap_col = find_column(df, "日期") or find_column(df, "查询日期")

    if not code_col:
        return records

    for _, row in df.iterrows():
        code = str(row.get(code_col, "")).strip().zfill(6)
        if not code.isdigit() or len(code) != 6:
            continue

        snapshot_date = None
        if snap_col:
            raw = str(row.get(snap_col, "")).strip()
            try:
                snapshot_date = datetime.strptime(raw, "%Y-%m-%d").date()
            except ValueError:
                pass

        records.append(
            PositionRecord(
                stock_code=code,
                stock_name=str(row.get(name_col, "")).strip() if name_col else "",
                total_shares=safe_int(row.get(total_col) if total_col else 0),
                available_shares=safe_int(row.get(avail_col) if avail_col else 0),
                cost_price=safe_float(row.get(cost_col) if cost_col else 0),
                current_price=safe_float(row.get(price_col) if price_col else 0),
                market_value=safe_float(row.get(mv_col) if mv_col else 0),
                floating_pnl=safe_float(row.get(pnl_col) if pnl_col else 0),
                pnl_pct=safe_float(row.get(pnl_pct_col) if pnl_pct_col else 0),
                snapshot_date=snapshot_date,
            )
        )

    return records
