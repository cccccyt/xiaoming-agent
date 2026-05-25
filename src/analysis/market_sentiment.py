from datetime import date, timedelta

from ..data_ingestion.models import (
    MarketContext,
    TradeRecord,
)
from ..market_data.board_fetcher import BoardFetcher
from ..market_data.index_fetcher import IndexFetcher
from ..market_data.news_fetcher import NewsFetcher
from ..market_data.stock_fetcher import StockFetcher


class MarketSentimentAnalyzer:
    def __init__(
        self,
        index_fetcher: IndexFetcher,
        board_fetcher: BoardFetcher,
        news_fetcher: NewsFetcher,
        stock_fetcher: StockFetcher | None = None,
    ):
        self.index_fetcher = index_fetcher
        self.board_fetcher = board_fetcher
        self.news_fetcher = news_fetcher
        self.stock_fetcher = stock_fetcher

    def build_market_context(
        self,
        trades: list[TradeRecord],
        period: str,
    ) -> MarketContext:
        if not trades:
            return MarketContext(period=period)

        dates = sorted(t.trade_date for t in trades)
        start_date = dates[0]
        end_date = dates[-1]

        # 大盘指数趋势
        index_info = self.index_fetcher.compute_index_trend(
            "sh000001", start_date, end_date
        )

        # 行业板块表现
        stock_codes = list(set(t.stock_code for t in trades))
        boards = self.board_fetcher.get_batch_boards(stock_codes)
        board_set = list(set(boards.values()))
        sector_perf: dict[str, float] = {}
        for bname in board_set[:5]:
            b_start = start_date.strftime("%Y%m%d")
            b_end = end_date.strftime("%Y%m%d")
            df = self.board_fetcher.fetch_board_history(bname, b_start, b_end)
            if not df.empty:
                close_col = "收盘" if "收盘" in df.columns else df.columns[3]
                closes = df[close_col].astype(float).dropna()
                if len(closes) >= 2:
                    sector_perf[bname] = round(
                        (closes.iloc[-1] - closes.iloc[0]) / closes.iloc[0] * 100, 2
                    )

        # 个股走势
        stock_trends: dict[str, dict] = {}
        if self.stock_fetcher:
            lookback_start = (start_date - timedelta(days=5)).strftime("%Y%m%d")
            period_end_str = end_date.strftime("%Y%m%d")
            for code in stock_codes:
                try:
                    df = self.stock_fetcher.fetch_daily_history(
                        code, lookback_start, period_end_str
                    )
                    if df.empty:
                        continue
                    close_col = "收盘" if "收盘" in df.columns else df.columns[5]
                    closes = df[close_col].astype(float).dropna()
                    if len(closes) < 2:
                        continue
                    # 取交易期间的首尾价格
                    df["日期_dt"] = df["日期"].astype(str)
                    name = boards.get(code, "")
                    if not name:
                        for t in trades:
                            if t.stock_code == code:
                                name = t.stock_name
                                break
                    stock_trends[code] = {
                        "name": name,
                        "start_price": round(float(closes.iloc[0]), 2),
                        "end_price": round(float(closes.iloc[-1]), 2),
                        "change_pct": round(
                            (float(closes.iloc[-1]) - float(closes.iloc[0]))
                            / float(closes.iloc[0]) * 100, 2
                        ),
                        "highest": round(float(closes.max()), 2),
                        "lowest": round(float(closes.min()), 2),
                    }
                except Exception:
                    continue

        # 个股新闻
        news_by_stock = self.news_fetcher.fetch_batch_news(
            stock_codes, start_date, end_date
        )
        relevant_news: list[dict] = []
        for code, news_list in news_by_stock.items():
            for n in news_list[:3]:
                n["_stock_code"] = code
                relevant_news.append(n)
        relevant_news = relevant_news[:15]

        # 热点新闻
        hot_news = self.news_fetcher.fetch_market_hot_news(start_date, end_date)

        # 市场情绪判断
        sentiment = "中性"
        if index_info["return_pct"] > 3:
            sentiment = "乐观"
        elif index_info["return_pct"] < -3:
            sentiment = "悲观"

        return MarketContext(
            period=period,
            index_trend=index_info["trend"],
            index_return=index_info["return_pct"],
            sector_performance=sector_perf,
            volatility_regime=index_info["regime"],
            market_sentiment_label=sentiment,
            relevant_news=relevant_news,
            stock_trends=stock_trends,
            hot_news=hot_news,
        )
