from datetime import date, datetime
from pathlib import Path

from .csv_reader import find_column, read_csv_with_encoding, safe_float
from .models import FundFlowRecord


def parse_fund_flow(filepath: Path) -> list[FundFlowRecord]:
    df = read_csv_with_encoding(filepath)
    records: list[FundFlowRecord] = []

    date_col = find_column(df, "日期") or find_column(df, "业务日期") or find_column(df, "date")
    type_col = find_column(df, "业务名称") or find_column(df, "类型") or find_column(df, "摘要")
    amount_col = find_column(df, "发生金额") or find_column(df, "变动金额") or find_column(df, "金额")
    balance_col = find_column(df, "余额") or find_column(df, "资金余额") or find_column(df, "账户余额")

    if not date_col or not amount_col:
        return records

    for _, row in df.iterrows():
        raw_date = row.get(date_col)
        if raw_date is None:
            continue
        try:
            d = datetime.strptime(str(raw_date).strip(), "%Y-%m-%d").date()
        except ValueError:
            try:
                d = datetime.strptime(str(raw_date).strip(), "%Y/%m/%d").date()
            except ValueError:
                continue

        amount = safe_float(row.get(amount_col))
        balance = safe_float(row.get(balance_col) if balance_col else 0)
        btype = str(row.get(type_col, "")).strip() if type_col else ""

        records.append(
            FundFlowRecord(
                business_date=d,
                business_type=btype,
                amount=amount,
                balance=balance,
            )
        )

    return records
