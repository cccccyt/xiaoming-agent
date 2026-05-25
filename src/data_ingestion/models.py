from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class TradeRecord(BaseModel):
    trade_date: date
    trade_time: Optional[str] = None
    stock_code: str
    stock_name: str
    direction: Literal["买入", "卖出"]
    quantity: int = Field(gt=0)
    price: float = Field(ge=0)
    amount: float
    commission: float = 0.0
    stamp_tax: float = 0.0
    other_fees: float = 0.0
    net_amount: float
    trade_market: str = ""

    @property
    def is_buy(self) -> bool:
        return self.direction == "买入"


class FundFlowRecord(BaseModel):
    business_date: date
    business_type: str
    amount: float
    balance: float


class PositionRecord(BaseModel):
    stock_code: str
    stock_name: str
    total_shares: int = 0
    available_shares: int = 0
    cost_price: float = 0.0
    current_price: float = 0.0
    market_value: float = 0.0
    floating_pnl: float = 0.0
    pnl_pct: float = 0.0
    snapshot_date: Optional[date] = None


class BehaviorMetrics(BaseModel):
    period: str
    total_trades: int = 0
    total_buys: int = 0
    total_sells: int = 0
    unique_stocks: int = 0
    trading_days: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    total_commission: float = 0.0
    avg_hold_days: float = 0.0
    median_hold_days: float = 0.0
    max_hold_days: int = 0
    min_hold_days: int = 0
    max_consecutive_losses: int = 0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    avg_position_size: float = 0.0
    max_position_size: float = 0.0
    max_position_ratio: float = 0.0
    daily_trade_frequency: float = 0.0
    morning_trade_ratio: float = 0.0
    afternoon_trade_ratio: float = 0.0
    panic_sell_count: int = 0
    chasing_buy_count: int = 0
    avg_turnaround_days: float = 0.0


class PsychologyPattern(BaseModel):
    pattern_type: str
    severity: float
    evidence: list[str]
    frequency: int = 0
    recommendations: list[str]


class MarketContext(BaseModel):
    period: str
    index_trend: str = "未知"
    index_return: float = 0.0
    sector_performance: dict[str, float] = {}
    volatility_regime: str = "未知"
    market_sentiment_label: str = "未知"
    relevant_news: list[dict] = []
    stock_trends: dict[str, dict] = {}  # stock_code -> {name, start_price, end_price, change_pct, highest, lowest}
    hot_news: list[dict] = []  # 市场热点新闻


class LLMAnalysisResult(BaseModel):
    summary: str = ""
    overall_score: int = 0
    detected_patterns: list[PsychologyPattern] = []
    market_alignment: str = ""
    key_issues: list[str] = []
    strengths: list[str] = []
    improvement_suggestions: list[str] = []
    next_month_focus: list[str] = []


class MonthlyAnalysis(BaseModel):
    year_month: str
    trades: list[TradeRecord] = []
    fund_flows: list[FundFlowRecord] = []
    positions: list[PositionRecord] = []
    behavior_metrics: Optional[BehaviorMetrics] = None
    psychology_patterns: list[PsychologyPattern] = []
    market_context: Optional[MarketContext] = None
    llm_result: Optional[LLMAnalysisResult] = None
