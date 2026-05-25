import re
from pathlib import Path

import pandas as pd


def read_csv_with_encoding(filepath: Path) -> pd.DataFrame:
    encodings = ["gbk", "gb2312", "gb18030", "utf-8", "utf-8-sig"]
    for enc in encodings:
        try:
            df = pd.read_csv(filepath, encoding=enc, dtype=str)
            return normalize_columns(df)
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise ValueError(f"无法解析文件编码: {filepath}")


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [
        col.strip()
        .replace("﻿", "")
        .replace("　", "")
        .replace("（", "(")
        .replace("）", ")")
        for col in df.columns
    ]
    df = df.dropna(how="all").dropna(axis=1, how="all")
    return df


def detect_csv_type(filename: str) -> str | None:
    name = filename.lower()
    if any(kw in name for kw in ["成交", "trade", "历史"]):
        return "trade_history"
    if any(kw in name for kw in ["资金", "流水", "fund", "flow"]):
        return "fund_flow"
    if any(kw in name for kw in ["持仓", "position", "hold"]):
        return "positions"
    return None


def find_column(df: pd.DataFrame, *keywords: str) -> str | None:
    for col in df.columns:
        col_lower = col.lower().strip()
        if all(kw.lower() in col_lower for kw in keywords):
            return col
    return None


def find_column_fuzzy(df: pd.DataFrame, *keywords: str) -> str | None:
    for col in df.columns:
        col_lower = col.lower().strip()
        if any(kw.lower() in col_lower for kw in keywords):
            return col
    return None


def find_columns_in_files(input_dir: Path) -> dict[str, list[Path]]:
    result: dict[str, list[Path]] = {}
    for f in input_dir.glob("*.csv"):
        csv_type = detect_csv_type(f.name)
        if csv_type:
            result.setdefault(csv_type, []).append(f)
    return result


def safe_float(val: object) -> float:
    if val is None or (isinstance(val, str) and val.strip() == ""):
        return 0.0
    try:
        cleaned = str(val).replace(",", "").replace("¥", "").replace("￥", "").strip()
        if cleaned in ("-", "--", "---", "—"):
            return 0.0
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0


def safe_int(val: object) -> int:
    if val is None or (isinstance(val, str) and val.strip() == ""):
        return 0
    try:
        cleaned = str(val).replace(",", "").strip()
        return int(float(cleaned))
    except (ValueError, TypeError):
        return 0
