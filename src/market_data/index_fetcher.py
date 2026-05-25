import time
from datetime import date

import akshare as ak
import pandas as pd

from .cache import DataCache


class IndexFetcher:
    INDEX_MAP = {
        "sh000001": "上证指数",
        "sz399001": "深证成指",
        "sz399006": "创业板指",
        "sh000688": "科创50",
        "sh000300": "沪深300",
    }

    def __init__(self, cache: DataCache, rate_limit: float = 0.5):
        self.cache = cache
        self.rate_limit = rate_limit

    def fetch_index_history(
        self, symbol: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        @self.cache.memoize
        def _fetch(sym: str, s: str, e: str) -> list[dict]:
            time.sleep(self.rate_limit)
            try:
                df = ak.stock_zh_index_daily_em(symbol=sym, start_date=s, end_date=e)
                if df is None or df.empty:
                    return []
                df.columns = [col.strip() for col in df.columns]
                return df.to_dict(orient="records")
            except Exception:
                return []

        data = _fetch(symbol, start_date, end_date)
        return pd.DataFrame(data) if data else pd.DataFrame()

    def compute_index_trend(
        self, symbol: str, period_start: date, period_end: date
    ) -> dict:
        start_str = period_start.strftime("%Y%m%d")
        end_str = period_end.strftime("%Y%m%d")
        df = self.fetch_index_history(symbol, start_str, end_str)

        if df.empty:
            return {
                "symbol": symbol,
                "name": self.INDEX_MAP.get(symbol, symbol),
                "trend": "未知",
                "return_pct": 0.0,
                "volatility": 0.0,
                "regime": "未知",
            }

        close_col = "收盘" if "收盘" in df.columns else df.columns[3]
        closes = pd.to_numeric(df[close_col], errors="coerce").dropna()
        if len(closes) < 2:
            return {
                "symbol": symbol,
                "name": self.INDEX_MAP.get(symbol, symbol),
                "trend": "未知",
                "return_pct": 0.0,
                "volatility": 0.0,
                "regime": "未知",
            }

        ret = (closes.iloc[-1] - closes.iloc[0]) / closes.iloc[0] * 100
        daily_returns = closes.pct_change().dropna()
        vol = daily_returns.std() * 100

        if ret > 5:
            trend = "上涨"
        elif ret < -5:
            trend = "下跌"
        else:
            trend = "震荡"

        if vol < 1:
            regime = "低波动"
        elif vol < 2.5:
            regime = "中波动"
        else:
            regime = "高波动"

        return {
            "symbol": symbol,
            "name": self.INDEX_MAP.get(symbol, symbol),
            "trend": trend,
            "return_pct": round(ret, 2),
            "volatility": round(vol, 2),
            "regime": regime,
        }
