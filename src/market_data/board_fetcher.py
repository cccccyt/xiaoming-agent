import time
from datetime import date

import akshare as ak
import pandas as pd

from .cache import DataCache


class BoardFetcher:
    def __init__(self, cache: DataCache, rate_limit: float = 0.5):
        self.cache = cache
        self.rate_limit = rate_limit
        self._stock_board_map: dict[str, str] = {}

    @staticmethod
    def _normalize_code(code: str) -> str:
        return code.strip().zfill(6)

    def get_stock_board(self, stock_code: str) -> str | None:
        code = self._normalize_code(stock_code)
        if code in self._stock_board_map:
            return self._stock_board_map[code]

        @self.cache.memoize
        def _fetch_board(c: str) -> str | None:
            time.sleep(self.rate_limit)
            try:
                df = ak.stock_board_industry_cons_em(symbol=c)
                if df is not None and not df.empty and "板块名称" in df.columns:
                    return str(df["板块名称"].iloc[0])
            except Exception:
                pass
            try:
                df = ak.stock_individual_info_em(symbol=c)
                if df is not None and not df.empty:
                    for _, row in df.iterrows():
                        if "行业" in str(row.get("item", "")):
                            return str(row.get("value", ""))
            except Exception:
                pass
            return None

        board = _fetch_board(code)
        if board:
            self._stock_board_map[code] = board
        return board

    def get_batch_boards(self, stock_codes: list[str]) -> dict[str, str]:
        result: dict[str, str] = {}
        for code in stock_codes:
            board = self.get_stock_board(code)
            if board:
                result[code] = board
        return result

    def fetch_board_history(
        self, board_name: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        @self.cache.memoize
        def _fetch(name: str, s: str, e: str) -> list[dict]:
            time.sleep(self.rate_limit)
            try:
                df = ak.stock_board_industry_hist_em(
                    symbol=name, start_date=s, end_date=e
                )
                if df is None or df.empty:
                    return []
                df.columns = [col.strip() for col in df.columns]
                return df.to_dict(orient="records")
            except Exception:
                return []

        data = _fetch(board_name, start_date, end_date)
        return pd.DataFrame(data) if data else pd.DataFrame()
