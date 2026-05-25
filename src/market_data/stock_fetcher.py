import time
from datetime import date

import akshare as ak
import pandas as pd

from .cache import DataCache


class StockFetcher:
    def __init__(self, cache: DataCache, rate_limit: float = 0.5):
        self.cache = cache
        self.rate_limit = rate_limit

    @staticmethod
    def _normalize_code(code: str) -> str:
        return code.strip().zfill(6)

    def fetch_daily_history(
        self, stock_code: str, start_date: str, end_date: str, adjust: str = "qfq"
    ) -> pd.DataFrame:
        code = self._normalize_code(stock_code)

        @self.cache.memoize
        def _fetch(c: str, s: str, e: str, adj: str) -> list[dict]:
            time.sleep(self.rate_limit)
            try:
                df = ak.stock_zh_a_hist(
                    symbol=c, period="daily", start_date=s, end_date=e, adjust=adj
                )
                if df is None or df.empty:
                    return []
                df.columns = [col.strip() for col in df.columns]
                return df.to_dict(orient="records")
            except Exception:
                return []

        data = _fetch(code, start_date, end_date, adjust)
        return pd.DataFrame(data) if data else pd.DataFrame()

    def get_price_change(
        self, stock_code: str, before_date: date, lookback_days: int = 5
    ) -> float:
        end_str = before_date.strftime("%Y%m%d")
        start_str = (before_date - pd.Timedelta(days=lookback_days * 2)).strftime(
            "%Y%m%d"
        )
        df = self.fetch_daily_history(stock_code, start_str, end_str)
        if df.empty:
            return 0.0

        close_col = "收盘" if "收盘" in df.columns else df.columns[5]
        closes = pd.to_numeric(df[close_col], errors="coerce").dropna()
        if len(closes) < 2:
            return 0.0

        target_date_str = before_date.strftime("%Y-%m-%d")
        if "日期" in df.columns:
            df["日期"] = pd.to_datetime(df["日期"])
            before = df[df["日期"] <= pd.Timestamp(target_date_str)]
            if before.empty:
                return 0.0
            closes = pd.to_numeric(before[close_col], errors="coerce").dropna()

        if len(closes) < lookback_days + 1:
            return 0.0

        recent = closes.iloc[-1]
        earlier = closes.iloc[-(lookback_days + 1)]
        if earlier == 0:
            return 0.0
        return round((recent - earlier) / earlier * 100, 2)
