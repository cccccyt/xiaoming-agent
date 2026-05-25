import argparse
import os
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from .config import get_cache_dir, get_data_dir, get_reports_dir, load_config
from .data_ingestion.csv_reader import find_columns_in_files
from .data_ingestion.fund_flow import parse_fund_flow
from .data_ingestion.models import (
    MonthlyAnalysis,
    PsychologyPattern,
    TradeRecord,
)
from .data_ingestion.positions import parse_positions
from .data_ingestion.trade_history import parse_trade_history
from .analysis.behavior_metrics import compute_behavior_metrics
from .analysis.psychology_detector import PsychologyDetector
from .analysis.market_sentiment import MarketSentimentAnalyzer
from .analysis.llm_analyzer import LLMAnalyzer
from .llm.client import LLMClient
from .llm.schemas import LLMConfig
from .market_data.board_fetcher import BoardFetcher
from .market_data.cache import DataCache
from .market_data.index_fetcher import IndexFetcher
from .market_data.news_fetcher import NewsFetcher
from .market_data.stock_fetcher import StockFetcher
from .reporting.report_generator import ReportGenerator


def inspect_csv(input_dir: Path) -> None:
    csv_files = find_columns_in_files(input_dir)
    if not csv_files:
        print(f"在 {input_dir} 中未找到东方财富 CSV 文件")
        print("请将以下类型的 CSV 文件放入该目录：")
        print("  - 历史成交记录 (文件名包含 '成交'/'trade')")
        print("  - 资金流水 (文件名包含 '资金'/'流水'/'fund')")
        print("  - 持仓记录 (文件名包含 '持仓'/'position')")
        return

    for csv_type, files in csv_files.items():
        print(f"\n## {csv_type} ({len(files)} 个文件)")
        for f in files:
            print(f"  - {f.name}")

    from .data_ingestion.csv_reader import read_csv_with_encoding

    for csv_type, files in csv_files.items():
        print(f"\n### {csv_type} 列名示例")
        df = read_csv_with_encoding(files[0])
        print(f"  列名: {list(df.columns)}")
        print(f"  行数: {len(df)}")
        print(f"  前3行:")
        print(df.head(3).to_string())


def load_trades_by_month(input_dir: Path) -> dict[str, list[TradeRecord]]:
    csv_files = find_columns_in_files(input_dir)
    by_month: dict[str, list[TradeRecord]] = defaultdict(list)

    trade_files = csv_files.get("trade_history", [])
    for f in trade_files:
        try:
            trades = parse_trade_history(f)
            for t in trades:
                month_key = t.trade_date.strftime("%Y-%m")
                by_month[month_key].append(t)
        except Exception as e:
            print(f"  [警告] 解析 {f.name} 失败: {e}")

    return dict(by_month)


def build_monthly_analysis(
    month: str,
    trades: list[TradeRecord],
    config: dict,
) -> MonthlyAnalysis:
    analysis = MonthlyAnalysis(year_month=month, trades=trades)

    analysis.behavior_metrics = compute_behavior_metrics(trades, period=month)

    cache_dir = get_cache_dir(config)
    cache = DataCache(cache_dir, ttl_hours=config.get("market", {}).get("cache_ttl_hours", 24))
    rate_limit = config.get("market", {}).get("rate_limit_seconds", 0.5)

    stock_fetcher = StockFetcher(cache, rate_limit)
    detector = PsychologyDetector(
        thresholds=config.get("psychology_thresholds", {}),
        stock_fetcher=stock_fetcher,
    )
    analysis.psychology_patterns = detector.detect_patterns(
        trades, analysis.behavior_metrics
    )

    index_fetcher = IndexFetcher(cache, rate_limit)
    board_fetcher = BoardFetcher(cache, rate_limit)
    news_fetcher = NewsFetcher(cache, rate_limit)
    sentiment = MarketSentimentAnalyzer(index_fetcher, board_fetcher, news_fetcher)
    analysis.market_context = sentiment.build_market_context(trades, month, config)

    return analysis


def resolve_llm_client(config: dict) -> LLMClient | None:
    llm_cfg = config.get("llm", {})
    claude_cfg = config.get("claude", {})

    api_key_env = claude_cfg.get("api_key_env", "ANTHROPIC_AUTH_TOKEN")
    base_url_env = claude_cfg.get("base_url_env", "ANTHROPIC_BASE_URL")

    api_key = os.environ.get(api_key_env, "")
    base_url = os.environ.get(base_url_env, "")
    model = os.environ.get("ANTHROPIC_MODEL", llm_cfg.get("model", "deepseek-v4-pro[1m]"))

    if not api_key:
        return None

    llm_config = LLMConfig(
        provider="claude",
        model=model,
        temperature=llm_cfg.get("temperature", 0.2),
        max_tokens=llm_cfg.get("max_tokens", 4096),
        api_key=api_key,
        base_url=base_url,
    )
    return LLMClient(llm_config)


def cli() -> None:
    parser = argparse.ArgumentParser(
        prog="xiaoming-agent",
        description="交易心理分析 Agent — 基于东方财富 CSV 的交易心态复盘工具",
    )
    parser.add_argument(
        "--month",
        type=str,
        help="指定分析月份，格式 YYYY-MM（如 2024-01）",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="分析所有可用月份",
    )
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="检查 CSV 文件格式（不做分析）",
    )
    parser.add_argument(
        "--progress",
        action="store_true",
        help="生成跨月进步报告",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="不调用 LLM，仅生成规则引擎分析",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="配置文件路径，默认 config/config.yaml",
    )

    args = parser.parse_args()
    config = load_config()
    input_dir = get_data_dir(config)
    reports_dir = get_reports_dir(config)

    if args.inspect:
        inspect_csv(input_dir)
        return

    if args.progress:
        all_trades = load_trades_by_month(input_dir)
        if not all_trades:
            print(f"未在 {input_dir} 中找到可解析的交易记录")
            sys.exit(1)

        llm_client = resolve_llm_client(config)
        print(f"共发现 {len(all_trades)} 个月份: {sorted(all_trades.keys())}")
        print("正在加载历史分析结果...")

        monthly_analyses: list[MonthlyAnalysis] = []
        monthly_scores: list[dict] = []

        for month in sorted(all_trades.keys()):
            report_file = reports_dir / f"{month}.md"
            if report_file.exists():
                analysis = build_monthly_analysis(month, all_trades[month], config)
                if llm_client and not args.no_llm:
                    print(f"  [{month}] 调用 LLM 深度分析...")
                    analyzer = LLMAnalyzer(llm_client)
                    analysis.llm_result = analyzer.analyze_month(
                        analysis.trades,
                        analysis.behavior_metrics,
                        analysis.market_context,
                        analysis.psychology_patterns,
                        month,
                    )
                monthly_analyses.append(analysis)
                monthly_scores.append(
                    {
                        "year_month": month,
                        "score": analysis.llm_result.overall_score if analysis.llm_result else 0,
                    }
                )

        llm_progress = None
        if llm_client and not args.no_llm and len(monthly_scores) >= 2:
            print("  正在生成进步报告...")
            analyzer = LLMAnalyzer(llm_client)
            llm_progress = analyzer.analyze_progress(monthly_scores)

        generator = ReportGenerator(reports_dir)
        out = generator.generate_progress_report(monthly_analyses, llm_progress)
        print(f"进步报告已生成: {out}")
        return

    all_trades = load_trades_by_month(input_dir)
    if not all_trades:
        print(f"未在 {input_dir} 中找到可解析的交易记录")
        print("请将东方财富导出的 CSV 文件放入该目录，然后重试")
        print(f"  历史成交: 文件名包含 '成交' 或 'trade'")
        print(f"  资金流水: 文件名包含 '资金' 或 '流水' 或 'fund'")
        print(f"  持仓记录: 文件名包含 '持仓' 或 'position'")
        print(f"\n运行 'xiaoming-agent --inspect' 检查 CSV 格式")
        sys.exit(1)

    months = [args.month] if args.month else (sorted(all_trades.keys()) if args.all else [sorted(all_trades.keys())[-1]])

    if not args.month and not args.all:
        print(f"未指定月份，默认分析最近月份: {months[0]}")
        print(f"可用月份: {sorted(all_trades.keys())}")
        print(f"使用 --month YYYY-MM 指定月份，或 --all 分析全部")

    llm_client = resolve_llm_client(config)
    if llm_client:
        print(f"LLM: DeepSeek (via Anthropic API) / {llm_client.config.model}")
    elif not args.no_llm:
        print("未检测到 LLM API Key，仅使用规则引擎分析")
        print("设置环境变量 ANTHROPIC_BASE_URL 和 ANTHROPIC_AUTH_TOKEN 启用 AI 分析")

    for month in months:
        trades = all_trades[month]
        print(f"\n{'=' * 50}")
        print(f"分析 {month}: {len(trades)} 笔交易")
        print("=" * 50)

        print("  [1/4] 计算行为指标...")
        analysis = build_monthly_analysis(month, trades, config)
        m = analysis.behavior_metrics
        print(
            f"        胜率 {m.win_rate}%, 总盈亏 {m.total_pnl:+,.2f}, "
            f"平均持仓 {m.avg_hold_days}天"
        )

        print(
            f"  [2/4] 检测心理偏差: {len(analysis.psychology_patterns)} 个模式"
        )
        for p in analysis.psychology_patterns:
            print(f"        {p.pattern_type} (严重度: {p.severity:.2f})")

        print(f"  [3/4] 市场环境: {analysis.market_context.index_trend}, "
              f"指数 {analysis.market_context.index_return:+.1f}%")

        if llm_client and not args.no_llm:
            print(f"  [4/4] LLM 深度分析中...")
            analyzer = LLMAnalyzer(llm_client)
            try:
                analysis.llm_result = analyzer.analyze_month(
                    analysis.trades,
                    analysis.behavior_metrics,
                    analysis.market_context,
                    analysis.psychology_patterns,
                    month,
                )
                print(f"        综合评分: {analysis.llm_result.overall_score}/100")
            except Exception as e:
                print(f"        LLM 分析失败: {e}")
        else:
            print(f"  [4/4] 跳过 LLM 分析 (--no-llm)")

        generator = ReportGenerator(reports_dir)
        out = generator.generate_monthly_report(analysis)
        print(f"\n报告已生成: {out}")


if __name__ == "__main__":
    cli()
