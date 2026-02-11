"""SQLite persistence for orchestration state."""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import settings
from ..logger import logger
from .models import CostSummary, RunStatus, StockResult, StockStatus, SwarmRun


class PersistenceManager:
    """Manages SQLite persistence for swarm runs."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize persistence manager.

        Args:
            db_path: Path to SQLite database. Defaults to settings.state_dir/swarm_runs.db
        """
        self.db_path = db_path or (settings.state_dir / "swarm_runs.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS swarm_runs (
                    run_id TEXT PRIMARY KEY,
                    run_name TEXT,
                    tickers TEXT NOT NULL,
                    analysis_period TEXT,
                    quarters TEXT,
                    fiscal_year INTEGER,
                    news_days_back INTEGER,
                    max_retries INTEGER DEFAULT 3,
                    status TEXT DEFAULT 'initialized',
                    total_stocks INTEGER,
                    completed_count INTEGER DEFAULT 0,
                    failed_count INTEGER DEFAULT 0,
                    cost_summary TEXT,
                    created_at TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    elapsed_seconds REAL DEFAULT 0.0
                )
                """
            )

            # Migration: Add new columns if they don't exist
            try:
                conn.execute("ALTER TABLE swarm_runs ADD COLUMN analysis_period TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists

            try:
                conn.execute("ALTER TABLE swarm_runs ADD COLUMN quarters TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS stock_results (
                    run_id TEXT,
                    ticker TEXT,
                    status TEXT DEFAULT 'pending',
                    retry_count INTEGER DEFAULT 0,
                    moat_score REAL,
                    is_watchlist_candidate INTEGER,
                    investment_thesis TEXT,
                    full_output TEXT,
                    tokens_used INTEGER DEFAULT 0,
                    cost_usd REAL DEFAULT 0.0,
                    error_message TEXT,
                    processing_time_seconds REAL,
                    PRIMARY KEY (run_id, ticker)
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cost_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    ticker TEXT,
                    agent_name TEXT,
                    timestamp TEXT,
                    tokens_total INTEGER DEFAULT 0,
                    cost_usd REAL DEFAULT 0.0
                )
                """
            )

            # Track record snapshots table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS report_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    analysis_date TEXT NOT NULL,
                    rating TEXT,
                    price_at_analysis REAL,
                    price_target REAL,
                    moat_score REAL,
                    snapshot_data TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(ticker, analysis_date)
                )
                """
            )

            conn.commit()
            logger.debug(f"Initialized database at {self.db_path}")

    def create_run(self, swarm_run: SwarmRun) -> None:
        """Create a new run in the database.

        Args:
            swarm_run: SwarmRun object to persist
        """
        with sqlite3.connect(self.db_path) as conn:
            # Insert run
            conn.execute(
                """
                INSERT INTO swarm_runs (
                    run_id, run_name, tickers, analysis_period, quarters,
                    fiscal_year, news_days_back, max_retries, status,
                    total_stocks, completed_count, failed_count, cost_summary,
                    created_at, started_at, completed_at, elapsed_seconds
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    swarm_run.run_id,
                    swarm_run.run_name,
                    json.dumps(swarm_run.tickers),
                    swarm_run.analysis_period,
                    json.dumps(swarm_run.quarters),
                    swarm_run.fiscal_year,
                    swarm_run.news_days_back,
                    swarm_run.max_retries,
                    swarm_run.status.value,
                    swarm_run.total_stocks,
                    swarm_run.completed_count,
                    swarm_run.failed_count,
                    json.dumps(swarm_run.cost_summary.model_dump()),
                    swarm_run.created_at.isoformat(),
                    swarm_run.started_at.isoformat() if swarm_run.started_at else None,
                    (
                        swarm_run.completed_at.isoformat()
                        if swarm_run.completed_at
                        else None
                    ),
                    swarm_run.elapsed_seconds,
                ),
            )

            # Initialize stock_results
            for ticker, result in swarm_run.stock_results.items():
                self._insert_stock_result(conn, swarm_run.run_id, result)

            conn.commit()
            logger.info(f"Created run {swarm_run.run_id} with {len(swarm_run.tickers)} stocks")

    def _insert_stock_result(
        self, conn: sqlite3.Connection, run_id: str, result: StockResult
    ) -> None:
        """Insert a stock result into the database."""
        conn.execute(
            """
            INSERT OR REPLACE INTO stock_results (
                run_id, ticker, status, retry_count, moat_score,
                is_watchlist_candidate, investment_thesis, full_output,
                tokens_used, cost_usd, error_message, processing_time_seconds
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                result.ticker,
                result.status.value,
                result.retry_count,
                result.moat_score,
                result.is_watchlist_candidate,
                result.investment_thesis,
                json.dumps(result.full_output) if result.full_output else None,
                result.tokens_used,
                result.cost_usd,
                result.error_message,
                result.processing_time_seconds,
            ),
        )

    def get_run(self, run_id: str) -> Optional[SwarmRun]:
        """Load a run from the database.

        Args:
            run_id: Run ID to load

        Returns:
            SwarmRun object or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM swarm_runs WHERE run_id = ?", (run_id,)
            )
            row = cursor.fetchone()

            if not row:
                return None

            # Load stock results
            stock_results = {}
            cursor = conn.execute(
                "SELECT * FROM stock_results WHERE run_id = ?", (run_id,)
            )
            for stock_row in cursor.fetchall():
                result = StockResult(
                    ticker=stock_row["ticker"],
                    status=StockStatus(stock_row["status"]),
                    retry_count=stock_row["retry_count"],
                    moat_score=stock_row["moat_score"],
                    is_watchlist_candidate=bool(stock_row["is_watchlist_candidate"])
                    if stock_row["is_watchlist_candidate"] is not None
                    else None,
                    investment_thesis=stock_row["investment_thesis"],
                    full_output=json.loads(stock_row["full_output"])
                    if stock_row["full_output"]
                    else None,
                    tokens_used=stock_row["tokens_used"],
                    cost_usd=stock_row["cost_usd"],
                    error_message=stock_row["error_message"],
                    processing_time_seconds=stock_row["processing_time_seconds"],
                )
                stock_results[result.ticker] = result

            # Parse cost summary
            cost_summary = CostSummary(**json.loads(row["cost_summary"]))

            # Convert Row to dict for .get() method support
            row_dict = dict(row)

            return SwarmRun(
                run_id=row["run_id"],
                run_name=row["run_name"],
                tickers=json.loads(row["tickers"]),
                analysis_period=row_dict.get("analysis_period", ""),
                quarters=json.loads(row_dict.get("quarters") or "[]"),
                fiscal_year=row_dict.get("fiscal_year"),
                news_days_back=row["news_days_back"],
                max_retries=row["max_retries"],
                status=RunStatus(row["status"]),
                stock_results=stock_results,
                total_stocks=row["total_stocks"],
                completed_count=row["completed_count"],
                failed_count=row["failed_count"],
                cost_summary=cost_summary,
                created_at=datetime.fromisoformat(row["created_at"]),
                started_at=datetime.fromisoformat(row["started_at"])
                if row["started_at"]
                else None,
                completed_at=datetime.fromisoformat(row["completed_at"])
                if row["completed_at"]
                else None,
                elapsed_seconds=row["elapsed_seconds"],
            )

    def update_run_status(
        self,
        run_id: str,
        status: RunStatus,
        completed_count: Optional[int] = None,
        failed_count: Optional[int] = None,
        elapsed_seconds: Optional[float] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
    ) -> None:
        """Update run status and metadata.

        Args:
            run_id: Run ID to update
            status: New status
            completed_count: Update completed count
            failed_count: Update failed count
            elapsed_seconds: Update elapsed time
            started_at: Update start time
            completed_at: Update completion time
        """
        updates = ["status = ?"]
        params = [status.value]

        if completed_count is not None:
            updates.append("completed_count = ?")
            params.append(completed_count)
        if failed_count is not None:
            updates.append("failed_count = ?")
            params.append(failed_count)
        if elapsed_seconds is not None:
            updates.append("elapsed_seconds = ?")
            params.append(elapsed_seconds)
        if started_at is not None:
            updates.append("started_at = ?")
            params.append(started_at.isoformat())
        if completed_at is not None:
            updates.append("completed_at = ?")
            params.append(completed_at.isoformat())

        params.append(run_id)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                f"UPDATE swarm_runs SET {', '.join(updates)} WHERE run_id = ?",
                params,
            )
            conn.commit()
            logger.debug(f"Updated run {run_id} status to {status.value}")

    def update_stock_result(self, run_id: str, result: StockResult) -> None:
        """Update a stock result.

        Args:
            run_id: Run ID
            result: Updated StockResult
        """
        with sqlite3.connect(self.db_path) as conn:
            self._insert_stock_result(conn, run_id, result)
            conn.commit()
            logger.debug(f"Updated stock result for {result.ticker} in run {run_id}")

    def update_cost_summary(self, run_id: str, cost_summary: CostSummary) -> None:
        """Update cost summary for a run.

        Args:
            run_id: Run ID
            cost_summary: Updated CostSummary
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE swarm_runs SET cost_summary = ? WHERE run_id = ?",
                (json.dumps(cost_summary.model_dump()), run_id),
            )
            conn.commit()

    def get_resumable_runs(self) -> List[SwarmRun]:
        """Get runs that can be resumed (have pending stocks).

        Returns:
            List of SwarmRun objects that can be resumed
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT DISTINCT r.run_id
                FROM swarm_runs r
                JOIN stock_results s ON r.run_id = s.run_id
                WHERE s.status IN ('pending', 'retrying')
                AND r.status IN ('initialized', 'running', 'paused')
                ORDER BY r.created_at DESC
                """
            )
            run_ids = [row["run_id"] for row in cursor.fetchall()]

        return [self.get_run(run_id) for run_id in run_ids if self.get_run(run_id)]

    def get_run_history(self, limit: int = 20) -> List[SwarmRun]:
        """Get recent run history.

        Args:
            limit: Maximum number of runs to return

        Returns:
            List of SwarmRun objects, most recent first
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT run_id FROM swarm_runs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            run_ids = [row["run_id"] for row in cursor.fetchall()]

        return [self.get_run(run_id) for run_id in run_ids if self.get_run(run_id)]

    def log_cost(
        self,
        run_id: str,
        ticker: str,
        agent_name: str,
        tokens_total: int,
        cost_usd: float,
    ) -> None:
        """Log cost entry to cost_log table.

        Args:
            run_id: Run ID
            ticker: Stock ticker
            agent_name: Agent name (fundamentalist, news_hound, quant, manager)
            tokens_total: Total tokens used
            cost_usd: Cost in USD
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO cost_log (
                    run_id, ticker, agent_name, timestamp, tokens_total, cost_usd
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    ticker,
                    agent_name,
                    datetime.now().isoformat(),
                    tokens_total,
                    cost_usd,
                ),
            )
            conn.commit()

    def get_monthly_costs(self, year: int, month: int) -> dict:
        """Aggregate costs for a specific month.

        Args:
            year: Year (e.g., 2024)
            month: Month (1-12)

        Returns:
            Dictionary with total_cost, run_count, stock_count,
            cost_by_day, cost_by_ticker
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Date range for the month
            start_date = f"{year:04d}-{month:02d}-01"
            if month == 12:
                end_date = f"{year + 1:04d}-01-01"
            else:
                end_date = f"{year:04d}-{month + 1:02d}-01"

            # Aggregate from cost_log table
            cursor = conn.execute(
                """
                SELECT
                    SUM(cost_usd) as total_cost,
                    COUNT(DISTINCT run_id) as run_count,
                    COUNT(*) as entry_count
                FROM cost_log
                WHERE timestamp >= ? AND timestamp < ?
                """,
                (start_date, end_date),
            )

            row = cursor.fetchone()
            total_cost = row["total_cost"] or 0.0
            run_count = row["run_count"] or 0

            # Cost by day
            cursor = conn.execute(
                """
                SELECT DATE(timestamp) as date, SUM(cost_usd) as cost
                FROM cost_log
                WHERE timestamp >= ? AND timestamp < ?
                GROUP BY DATE(timestamp)
                """,
                (start_date, end_date),
            )
            cost_by_day = {row["date"]: row["cost"] for row in cursor.fetchall()}

            # Cost by ticker
            cursor = conn.execute(
                """
                SELECT ticker, SUM(cost_usd) as cost
                FROM cost_log
                WHERE timestamp >= ? AND timestamp < ?
                GROUP BY ticker
                """,
                (start_date, end_date),
            )
            cost_by_ticker = {row["ticker"]: row["cost"] for row in cursor.fetchall()}

            # Stock count
            cursor = conn.execute(
                """
                SELECT COUNT(DISTINCT ticker) as stock_count
                FROM cost_log
                WHERE timestamp >= ? AND timestamp < ?
                """,
                (start_date, end_date),
            )
            stock_count = cursor.fetchone()["stock_count"] or 0

            return {
                "total_cost": total_cost,
                "run_count": run_count,
                "stock_count": stock_count,
                "cost_by_day": cost_by_day,
                "cost_by_ticker": cost_by_ticker,
            }

    def get_cost_by_agent(self, year: int, month: int) -> Dict[str, float]:
        """Aggregate costs by agent for a specific month.

        Args:
            year: Year (e.g., 2026)
            month: Month (1-12)

        Returns:
            Dictionary mapping agent_name to total cost USD.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            start_date = f"{year:04d}-{month:02d}-01"
            if month == 12:
                end_date = f"{year + 1:04d}-01-01"
            else:
                end_date = f"{year:04d}-{month + 1:02d}-01"

            cursor = conn.execute(
                """
                SELECT agent_name, SUM(cost_usd) as cost
                FROM cost_log
                WHERE timestamp >= ? AND timestamp < ?
                GROUP BY agent_name
                ORDER BY cost DESC
                """,
                (start_date, end_date),
            )

            return {row["agent_name"]: row["cost"] for row in cursor.fetchall()}

    def store_report_snapshot(
        self,
        ticker: str,
        run_id: str,
        analysis_date: str,
        rating: Optional[str],
        price_at_analysis: float,
        price_target: float,
        moat_score: float,
        snapshot_data: Dict[str, Any]
    ) -> str:
        """Store a report snapshot for track record comparison.

        Args:
            ticker: Stock ticker
            run_id: Run ID that generated this report
            analysis_date: Date of analysis (YYYY-MM-DD)
            rating: 5-tier rating (STRONG BUY/BUY/HOLD/SELL/STRONG SELL)
            price_at_analysis: Stock price at time of analysis
            price_target: Price target from analysis
            moat_score: Overall moat score
            snapshot_data: Full report data as dict

        Returns:
            Snapshot ID
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO report_snapshots (
                    ticker, run_id, analysis_date, rating, price_at_analysis,
                    price_target, moat_score, snapshot_data, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ticker,
                    run_id,
                    analysis_date,
                    rating,
                    price_at_analysis,
                    price_target,
                    moat_score,
                    json.dumps(snapshot_data),
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()
            logger.debug(f"Stored report snapshot for {ticker} on {analysis_date}")

            # Return the ID
            cursor = conn.execute(
                "SELECT id FROM report_snapshots WHERE ticker = ? AND analysis_date = ?",
                (ticker, analysis_date),
            )
            row = cursor.fetchone()
            return str(row[0]) if row else ""

    def get_previous_report(
        self, ticker: str, lookback_days: int = 90
    ) -> Optional[Dict[str, Any]]:
        """Retrieve the most recent previous report for a ticker.

        Args:
            ticker: Stock ticker
            lookback_days: Maximum days to look back for previous report

        Returns:
            Dict with previous report data or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Calculate cutoff date
            cutoff_date = datetime.now() - timedelta(days=lookback_days)

            cursor = conn.execute(
                """
                SELECT *
                FROM report_snapshots
                WHERE ticker = ?
                AND created_at >= ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (ticker, cutoff_date.isoformat()),
            )

            row = cursor.fetchone()

            if not row:
                logger.debug(f"No previous report found for {ticker} within {lookback_days} days")
                return None

            # Parse snapshot data
            snapshot_data = json.loads(row["snapshot_data"]) if row["snapshot_data"] else {}

            return {
                "id": row["id"],
                "ticker": row["ticker"],
                "run_id": row["run_id"],
                "analysis_date": row["analysis_date"],
                "rating": row["rating"],
                "price_at_analysis": row["price_at_analysis"],
                "price_target": row["price_target"],
                "moat_score": row["moat_score"],
                "snapshot_data": snapshot_data,
                "created_at": row["created_at"],
            }
