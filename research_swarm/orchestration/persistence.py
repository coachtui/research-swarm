"""Neon PostgreSQL persistence for orchestration state using Prisma ORM."""

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from prisma import Prisma

from ..config import settings
from ..logger import logger
from .models import CostSummary, RunStatus, StockResult, StockStatus, SwarmRun


class PersistenceManager:
    """Manages Neon PostgreSQL persistence for swarm runs using Prisma ORM."""

    def __init__(self, user_id: Optional[str] = None):
        """Initialize persistence manager with Prisma client.

        Args:
            user_id: User ID to associate runs with. Required for Neon persistence.
        """
        self.user_id = user_id
        self._db: Optional[Prisma] = None

    def _get_db(self) -> Prisma:
        """Get or create Prisma client and ensure connection."""
        if self._db is None:
            self._db = Prisma()
            # Connect synchronously using asyncio.run
            asyncio.run(self._db.connect())
            logger.debug("Connected to Neon PostgreSQL via Prisma")
        return self._db

    def __del__(self):
        """Cleanup: disconnect Prisma client."""
        if self._db is not None:
            try:
                asyncio.run(self._db.disconnect())
            except Exception:
                pass  # Ignore errors during cleanup

    def create_run(self, swarm_run: SwarmRun) -> None:
        """Create a new run in the database.

        Args:
            swarm_run: SwarmRun object to persist
        """
        if not self.user_id:
            raise ValueError("user_id required for Neon persistence")

        db = self._get_db()

        async def _create():
            # Create run
            await db.run.create(
                data={
                    "id": swarm_run.run_id,
                    "userId": self.user_id,
                    "runName": swarm_run.run_name,
                    "tickers": swarm_run.tickers,
                    "analysisPeriod": swarm_run.analysis_period,
                    "quarters": swarm_run.quarters,
                    "fiscalYear": swarm_run.fiscal_year,
                    "newsDaysBack": swarm_run.news_days_back,
                    "maxRetries": swarm_run.max_retries,
                    "status": swarm_run.status.value,
                    "totalStocks": swarm_run.total_stocks,
                    "completedCount": swarm_run.completed_count,
                    "failedCount": swarm_run.failed_count,
                    "progressPercent": (
                        (swarm_run.completed_count + swarm_run.failed_count)
                        / swarm_run.total_stocks
                        * 100
                        if swarm_run.total_stocks > 0
                        else 0
                    ),
                    "totalCostUsd": swarm_run.cost_summary.total_cost_usd,
                    "costSummary": swarm_run.cost_summary.dict(),
                    "createdAt": swarm_run.created_at,
                    "startedAt": swarm_run.started_at,
                    "completedAt": swarm_run.completed_at,
                    "elapsedSeconds": swarm_run.elapsed_seconds,
                }
            )

            # Create stock results
            for ticker, result in swarm_run.stock_results.items():
                await self._insert_stock_result(swarm_run.run_id, result)

        asyncio.run(_create())
        logger.info(f"Created run {swarm_run.run_id} with {len(swarm_run.tickers)} stocks")

    async def _insert_stock_result(self, run_id: str, result: StockResult) -> None:
        """Insert a stock result into the database."""
        db = self._get_db()

        await db.stockresult.upsert(
            where={"runId_ticker": {"runId": run_id, "ticker": result.ticker}},
            data={
                "create": {
                    "runId": run_id,
                    "ticker": result.ticker,
                    "status": result.status.value,
                    "retryCount": result.retry_count,
                    "moatScore": result.moat_score,
                    "isWatchlistCandidate": result.is_watchlist_candidate,
                    "investmentThesis": result.investment_thesis,
                    "fullOutput": result.full_output,
                    "tokensUsed": result.tokens_used,
                    "costUsd": result.cost_usd,
                    "errorMessage": result.error_message,
                    "processingTimeSeconds": result.processing_time_seconds,
                },
                "update": {
                    "status": result.status.value,
                    "retryCount": result.retry_count,
                    "moatScore": result.moat_score,
                    "isWatchlistCandidate": result.is_watchlist_candidate,
                    "investmentThesis": result.investment_thesis,
                    "fullOutput": result.full_output,
                    "tokensUsed": result.tokens_used,
                    "costUsd": result.cost_usd,
                    "errorMessage": result.error_message,
                    "processingTimeSeconds": result.processing_time_seconds,
                },
            },
        )

    def get_run(self, run_id: str) -> Optional[SwarmRun]:
        """Load a run from the database.

        Args:
            run_id: Run ID to load

        Returns:
            SwarmRun object or None if not found
        """
        db = self._get_db()

        async def _get():
            # Fetch run with stock results
            run = await db.run.find_unique(
                where={"id": run_id}, include={"stockResults": True}
            )

            if not run:
                return None

            # Convert stock results
            stock_results = {}
            for sr in run.stockResults:
                result = StockResult(
                    ticker=sr.ticker,
                    status=StockStatus(sr.status),
                    retry_count=sr.retryCount,
                    moat_score=sr.moatScore,
                    is_watchlist_candidate=sr.isWatchlistCandidate,
                    investment_thesis=sr.investmentThesis,
                    full_output=sr.fullOutput,
                    tokens_used=sr.tokensUsed or 0,
                    cost_usd=sr.costUsd or 0.0,
                    error_message=sr.errorMessage,
                    processing_time_seconds=sr.processingTimeSeconds,
                )
                stock_results[result.ticker] = result

            # Parse cost summary
            cost_summary = (
                CostSummary(**run.costSummary)
                if run.costSummary
                else CostSummary()
            )

            # Build SwarmRun
            return SwarmRun(
                run_id=run.id,
                run_name=run.runName,
                tickers=run.tickers,
                analysis_period=run.analysisPeriod,
                quarters=run.quarters or [],
                fiscal_year=run.fiscalYear,
                news_days_back=run.newsDaysBack,
                max_retries=run.maxRetries,
                status=RunStatus(run.status),
                total_stocks=run.totalStocks,
                completed_count=run.completedCount,
                failed_count=run.failedCount,
                stock_results=stock_results,
                cost_summary=cost_summary,
                created_at=run.createdAt,
                started_at=run.startedAt,
                completed_at=run.completedAt,
                elapsed_seconds=run.elapsedSeconds,
            )

        return asyncio.run(_get())

    def update_run_status(
        self,
        run_id: str,
        status: RunStatus,
        completed_count: Optional[int] = None,
        failed_count: Optional[int] = None,
        elapsed_seconds: Optional[float] = None,
        completed_at: Optional[datetime] = None,
    ) -> None:
        """Update run status and progress.

        Args:
            run_id: Run ID to update
            status: New status
            completed_count: Number of completed stocks
            failed_count: Number of failed stocks
            elapsed_seconds: Total elapsed time
            completed_at: Completion timestamp
        """
        db = self._get_db()

        async def _update():
            # Build update data
            update_data = {"status": status.value}

            if completed_count is not None:
                update_data["completedCount"] = completed_count

            if failed_count is not None:
                update_data["failedCount"] = failed_count

            if elapsed_seconds is not None:
                update_data["elapsedSeconds"] = elapsed_seconds

            if completed_at is not None:
                update_data["completedAt"] = completed_at

            # Calculate progress percent
            if completed_count is not None and failed_count is not None:
                run = await db.run.find_unique(where={"id": run_id})
                if run and run.totalStocks > 0:
                    progress = (completed_count + failed_count) / run.totalStocks * 100
                    update_data["progressPercent"] = progress

            await db.run.update(where={"id": run_id}, data=update_data)

        asyncio.run(_update())
        logger.debug(f"Updated run {run_id} status to {status.value}")

    def update_stock_result(self, run_id: str, result: StockResult) -> None:
        """Update stock result in database.

        Args:
            run_id: Run ID
            result: Stock result to update
        """
        db = self._get_db()

        async def _update():
            await self._insert_stock_result(run_id, result)

        asyncio.run(_update())

    def update_cost_summary(self, run_id: str, cost_summary: CostSummary) -> None:
        """Update cost summary for a run.

        Args:
            run_id: Run ID
            cost_summary: Updated cost summary
        """
        db = self._get_db()

        async def _update():
            await db.run.update(
                where={"id": run_id},
                data={
                    "totalCostUsd": cost_summary.total_cost_usd,
                    "costSummary": cost_summary.dict(),
                },
            )

        asyncio.run(_update())

    def get_resumable_runs(self) -> List[SwarmRun]:
        """Get all runs that can be resumed (status: paused or failed).

        Returns:
            List of resumable SwarmRun objects
        """
        if not self.user_id:
            return []

        db = self._get_db()

        async def _get():
            runs = await db.run.find_many(
                where={
                    "userId": self.user_id,
                    "status": {"in": ["paused", "failed"]},
                },
                order={"createdAt": "desc"},
            )
            return [self.get_run(run.id) for run in runs if run]

        results = asyncio.run(_get())
        return [r for r in results if r is not None]

    def get_run_history(self, limit: int = 20) -> List[SwarmRun]:
        """Get recent run history.

        Args:
            limit: Maximum number of runs to return

        Returns:
            List of SwarmRun objects ordered by creation date (newest first)
        """
        if not self.user_id:
            return []

        db = self._get_db()

        async def _get():
            runs = await db.run.find_many(
                where={"userId": self.user_id},
                order={"createdAt": "desc"},
                take=limit,
            )
            return [self.get_run(run.id) for run in runs]

        results = asyncio.run(_get())
        return [r for r in results if r is not None]

    def log_cost(
        self,
        run_id: str,
        ticker: str,
        agent_name: str,
        tokens_total: int,
        cost_usd: float,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Log cost for an agent operation.

        Args:
            run_id: Run ID
            ticker: Stock ticker
            agent_name: Name of agent (fundamentalist, news_hound, quant, manager)
            tokens_total: Total tokens used
            cost_usd: Cost in USD
            timestamp: When cost occurred (defaults to now)
        """
        if not self.user_id:
            logger.warning("Cannot log cost: user_id not set")
            return

        db = self._get_db()

        async def _log():
            await db.costlog.create(
                data={
                    "userId": self.user_id,
                    "runId": run_id,
                    "ticker": ticker,
                    "agent": agent_name,
                    "tokensTotal": tokens_total,
                    "costUsd": cost_usd,
                    "timestamp": timestamp or datetime.utcnow(),
                }
            )

        asyncio.run(_log())

    def get_monthly_costs(self, year: int, month: int) -> dict:
        """Get cost breakdown for a specific month.

        Args:
            year: Year (e.g., 2024)
            month: Month (1-12)

        Returns:
            Dict with cost statistics
        """
        if not self.user_id:
            return {"total": 0.0, "by_ticker": {}, "by_agent": {}}

        db = self._get_db()

        async def _get():
            # Calculate month range
            start_date = datetime(year, month, 1)
            if month == 12:
                end_date = datetime(year + 1, 1, 1)
            else:
                end_date = datetime(year, month + 1, 1)

            # Query costs
            costs = await db.costlog.find_many(
                where={
                    "userId": self.user_id,
                    "timestamp": {"gte": start_date, "lt": end_date},
                }
            )

            # Aggregate
            total = sum(c.costUsd for c in costs)
            by_ticker = {}
            by_agent = {}

            for cost in costs:
                # By ticker
                if cost.ticker not in by_ticker:
                    by_ticker[cost.ticker] = 0.0
                by_ticker[cost.ticker] += cost.costUsd

                # By agent
                if cost.agent not in by_agent:
                    by_agent[cost.agent] = 0.0
                by_agent[cost.agent] += cost.costUsd

            return {
                "total": total,
                "by_ticker": by_ticker,
                "by_agent": by_agent,
                "num_analyses": len(set(c.ticker for c in costs)),
            }

        return asyncio.run(_get())

    def get_cost_by_agent(self, year: int, month: int) -> Dict[str, float]:
        """Get cost breakdown by agent for a specific month.

        Args:
            year: Year
            month: Month (1-12)

        Returns:
            Dict mapping agent name to total cost
        """
        monthly = self.get_monthly_costs(year, month)
        return monthly.get("by_agent", {})

    def store_report_snapshot(
        self,
        ticker: str,
        run_id: str,
        analysis_date: str,
        rating: Optional[str],
        price_at_analysis: float,
        price_target: float,
        moat_score: float,
        snapshot_data: dict,
    ) -> None:
        """Store a report snapshot for track record.

        Args:
            ticker: Stock ticker
            run_id: Run ID
            analysis_date: Date of analysis (YYYY-MM-DD)
            rating: Buy/Hold/Sell rating
            price_at_analysis: Stock price at time of analysis
            price_target: Target price
            moat_score: Moat score
            snapshot_data: Full snapshot data as dict
        """
        db = self._get_db()

        async def _store():
            await db.reportsnapshot.upsert(
                where={
                    "ticker_analysisDate": {
                        "ticker": ticker,
                        "analysisDate": analysis_date,
                    }
                },
                data={
                    "create": {
                        "ticker": ticker,
                        "runId": run_id,
                        "analysisDate": analysis_date,
                        "rating": rating,
                        "priceAtAnalysis": price_at_analysis,
                        "priceTarget": price_target,
                        "moatScore": moat_score,
                        "snapshotData": snapshot_data,
                    },
                    "update": {
                        "runId": run_id,
                        "rating": rating,
                        "priceAtAnalysis": price_at_analysis,
                        "priceTarget": price_target,
                        "moatScore": moat_score,
                        "snapshotData": snapshot_data,
                    },
                },
            )

        asyncio.run(_store())
        logger.debug(f"Stored report snapshot for {ticker} on {analysis_date}")

    def get_previous_report(
        self, ticker: str, before_date: Optional[str] = None
    ) -> Optional[dict]:
        """Get the most recent previous report for a ticker.

        Args:
            ticker: Stock ticker
            before_date: Only get reports before this date (YYYY-MM-DD)

        Returns:
            Dict with report snapshot data or None if no previous report
        """
        db = self._get_db()

        async def _get():
            # Build query
            where = {"ticker": ticker}
            if before_date:
                where["analysisDate"] = {"lt": before_date}

            # Find most recent
            snapshot = await db.reportsnapshot.find_first(
                where=where, order={"analysisDate": "desc"}
            )

            if not snapshot:
                return None

            return {
                "ticker": snapshot.ticker,
                "run_id": snapshot.runId,
                "analysis_date": snapshot.analysisDate,
                "rating": snapshot.rating,
                "price_at_analysis": snapshot.priceAtAnalysis,
                "price_target": snapshot.priceTarget,
                "moat_score": snapshot.moatScore,
                "snapshot_data": snapshot.snapshotData,
                "created_at": snapshot.createdAt.isoformat(),
            }

        return asyncio.run(_get())
