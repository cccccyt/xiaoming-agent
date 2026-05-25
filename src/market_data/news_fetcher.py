import time
from datetime import date, timedelta
from pathlib import Path

import akshare as ak
import pandas as pd

from .cache import DataCache


class NewsFetcher:
    def __init__(self, cache: DataCache, rate_limit: float = 0.5):
        self.cache = cache
        self.rate_limit = rate_limit

    @staticmethod
    def _normalize_code(code: str) -> str:
        code = code.strip().zfill(6)
        return code

    def fetch_stock_news(
        self, stock_code: str, start_date: date, end_date: date
    ) -> list[dict]:
        code = self._normalize_code(stock_code)

        @self.cache.memoize
        def _fetch(c: str, s: str, e: str) -> list[dict]:
            time.sleep(self.rate_limit)
            try:
                df = ak.stock_news_em(symbol=c)
                if df is None or df.empty:
                    return []
                df.columns = [col.strip() for col in df.columns]
                time_col = (
                    "发布时间" if "发布时间" in df.columns else df.columns[0]
                )
                df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
                mask = (df[time_col] >= pd.Timestamp(s)) & (
                    df[time_col] <= pd.Timestamp(e) + pd.Timedelta(days=1)
                )
                filtered = df[mask]
                return filtered.to_dict(orient="records")
            except Exception:
                return []

        return _fetch(code, start_date.isoformat(), end_date.isoformat())

    def fetch_batch_news(
        self,
        stock_codes: list[str],
        start_date: date,
        end_date: date,
    ) -> dict[str, list[dict]]:
        result: dict[str, list[dict]] = {}
        for code in stock_codes:
            news = self.fetch_stock_news(code, start_date, end_date)
            if news:
                result[code] = news
        return result
