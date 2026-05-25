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

    def fetch_market_hot_news(
        self, start_date: date, end_date: date
    ) -> list[dict]:
        """拉取市场热点新闻/财经快讯"""
        @self.cache.memoize
        def _fetch(s: str, e: str) -> list[dict]:
            time.sleep(self.rate_limit)
            news_list: list[dict] = []

            # 尝试 akshare 的几种热门新闻接口
            for fetcher in [
                self._try_global_news,
                self._try_cctv_news,
            ]:
                try:
                    result = fetcher(s, e)
                    if result:
                        news_list.extend(result)
                except Exception:
                    continue
                if len(news_list) >= 30:
                    break

            return news_list[:50]

        return _fetch(start_date.isoformat(), end_date.isoformat())

    def _try_global_news(self, s: str, e: str) -> list[dict]:
        """全球财经快讯"""
        try:
            df = ak.stock_info_global_em()
            if df is None or df.empty:
                return []
            df.columns = [col.strip() for col in df.columns]
            time_col = next((c for c in df.columns if "时间" in c or "time" in c.lower()), df.columns[0])
            df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
            mask = (df[time_col] >= pd.Timestamp(s)) & (df[time_col] <= pd.Timestamp(e) + pd.Timedelta(days=1))
            filtered = df[mask]
            return filtered.head(50).to_dict(orient="records")
        except Exception:
            return []

    def _try_cctv_news(self, s: str, e: str) -> list[dict]:
        """CCTV 新闻联播或财联社电报"""
        try:
            df = ak.stock_telegraph_cls()
            if df is None or df.empty:
                return []
            df.columns = [col.strip() for col in df.columns]
            time_col = next((c for c in df.columns if "时间" in c or "time" in c.lower()), df.columns[0])
            df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
            mask = (df[time_col] >= pd.Timestamp(s)) & (df[time_col] <= pd.Timestamp(e) + pd.Timedelta(days=1))
            filtered = df[mask]
            return filtered.head(50).to_dict(orient="records")
        except Exception:
            return []
