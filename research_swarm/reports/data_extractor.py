"""Extract and transform SwarmRun data into report data."""

from typing import Dict, Any

from ..orchestration import PersistenceManager
from ..orchestration.models import StockResult, StockStatus
from .models import ReportData, StockReportData


class DataExtractor:
    """Extracts data from persistence layer and transforms it for reports."""

    def __init__(self, persistence: PersistenceManager):
        """Initialize data extractor.

        Args:
            persistence: PersistenceManager instance for loading run data
        """
        self.persistence = persistence

    def extract(self, run_id: str, top_picks_count: int = 3) -> ReportData:
        """Extract report data from a SwarmRun.

        Args:
            run_id: Run ID to extract data for
            top_picks_count: Number of top picks to include

        Returns:
            ReportData object ready for report generation

        Raises:
            ValueError: If run not found or has no completed stocks
        """
        # 1. Load SwarmRun from persistence
        run = self.persistence.get_run(run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found")

        # 2. Transform each completed StockResult → StockReportData
        stocks = []
        for ticker, result in run.stock_results.items():
            if result.status == StockStatus.COMPLETED and result.full_output:
                try:
                    stock_data = self._extract_stock(result)
                    stocks.append(stock_data)
                except Exception as e:
                    # Skip stocks with extraction errors but log them
                    print(f"Warning: Failed to extract {ticker}: {e}")
                    continue

        if not stocks:
            raise ValueError(f"Run {run_id} has no completed stocks with data")

        # 3. Sort by moat_score for top_picks
        sorted_stocks = sorted(stocks, key=lambda s: s.moat_score, reverse=True)
        top_picks = sorted_stocks[:top_picks_count]

        # 4. Filter watchlist candidates (moat >= 8.0)
        watchlist = [s for s in stocks if s.is_watchlist_candidate]

        # 5. Calculate averages
        avg_moat = sum(s.moat_score for s in stocks) / len(stocks) if stocks else 0.0

        # 6. Build cost breakdown by ticker
        cost_by_ticker = {
            ticker: result.cost_usd
            for ticker, result in run.stock_results.items()
            if result.status == StockStatus.COMPLETED
        }

        # 7. Get analysis date from first completed stock
        analysis_date = run.created_at.strftime("%Y-%m-%d")

        return ReportData(
            run_id=run.run_id,
            run_name=run.run_name,
            analysis_date=analysis_date,
            fiscal_year=run.fiscal_year,
            stocks=stocks,
            top_picks=top_picks,
            watchlist_candidates=watchlist,
            total_stocks=run.total_stocks,
            completed_count=run.completed_count,
            failed_count=run.failed_count,
            average_moat_score=avg_moat,
            total_cost_usd=run.cost_summary.total_cost_usd,
            total_elapsed_seconds=run.elapsed_seconds,
            cost_by_ticker=cost_by_ticker,
        )

    def _extract_stock(self, result: StockResult) -> StockReportData:
        """Extract stock report data from a StockResult.

        Args:
            result: StockResult from orchestration

        Returns:
            StockReportData for report generation

        Raises:
            KeyError: If required fields are missing from full_output
        """
        if not result.full_output:
            raise ValueError(f"StockResult for {result.ticker} has no full_output")

        output = result.full_output  # ManagerOutput dict

        # Extract moat breakdown
        moat_breakdown_dict = output.get("moat_breakdown", {})
        moat_breakdown = {
            "financial_health": moat_breakdown_dict.get("financial_health", 0.0),
            "sentiment_catalysts": moat_breakdown_dict.get("sentiment_catalysts", 0.0),
            "technical_strength": moat_breakdown_dict.get("technical_strength", 0.0),
            "supply_chain_position": moat_breakdown_dict.get(
                "supply_chain_position", 0.0
            ),
        }

        # Extract supply chain from quant_output
        quant = output.get("quant_output", {})
        sc_graph = quant.get("supply_chain_graph", {})

        return StockReportData(
            ticker=result.ticker,
            moat_score=result.moat_score or 0.0,
            moat_breakdown=moat_breakdown,
            is_watchlist_candidate=result.is_watchlist_candidate or False,
            investment_thesis=output.get("investment_thesis", ""),
            key_insights=output.get("key_insights", []),
            risk_factors=output.get("risk_factors", []),
            synthesis_narrative=output.get("synthesis_narrative", ""),
            supply_chain_nodes=sc_graph.get("nodes", []),
            supply_chain_edges=sc_graph.get("edges", []),
            hidden_dependencies=sc_graph.get("hidden_dependencies", []),
            processing_time=result.processing_time_seconds or 0.0,
            cost_usd=result.cost_usd,
        )
