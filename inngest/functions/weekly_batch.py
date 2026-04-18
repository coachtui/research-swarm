"""
Weekly batch pipeline: screener → full analysis → signal storage.

Fires every Monday 03:00 UTC (Sunday 11:00 PM ET).
Each ticker is analyzed in a separate Inngest step, giving each up to
15 minutes of execution time. The function is fully durable — if it
restarts, already-completed steps are not re-executed.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from inngest.functions.analyze_stock import inngest

from api.lib.db import get_db
from api.services.analysis_service import run_stock_analysis
from api.services.market_context_service import MarketContextService
from api.services.weekly_signal_service import WeeklySignalService
from research_swarm.data.market_data_client import MarketDataClient
from research_swarm.data.openinsider_client import OpenInsiderClient
from research_swarm.data.screener import StockScreener

logger = logging.getLogger(__name__)

_MAX_CANDIDATES = int(os.getenv("BATCH_MAX_CANDIDATES", "25"))
_QUARTERS = ["Q4_2024", "Q1_2025", "Q2_2025", "Q3_2025"]
_NEWS_DAYS_BACK = 30


def _get_batch_user_id() -> str:
    """Return BATCH_SYSTEM_USER_ID, raising at call time (not module load) if unset."""
    uid = os.getenv("BATCH_SYSTEM_USER_ID", "")
    if not uid:
        raise RuntimeError(
            "BATCH_SYSTEM_USER_ID env var is not set. "
            "Set it to the UUID of your admin user in the User table."
        )
    return uid


@inngest.create_function(
    fn_id="weekly-batch",
    trigger=inngest.trigger.cron(cron="0 3 * * 1"),  # Monday 03:00 UTC = Sunday 11 PM ET
    name="Weekly Batch Analysis",
    retries=1,
)
async def weekly_batch(ctx: Any, step: Any) -> Dict[str, Any]:
    """
    Full weekly analysis pipeline.

    Steps:
      1. Run Stage 1 screener — selects top tickers from universe
      2. Fetch market context (ES/NQ/DOW)
      3. Analyze each selected ticker (one step per ticker)
      4. Store all signals in WeeklySignal table
    """
    run_date = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    # ── Step 1: Screen the universe ──────────────────────────────────────────
    async def run_screener() -> List[str]:
        market_client = MarketDataClient()
        insider_client = OpenInsiderClient()
        screener = StockScreener(
            market_client=market_client,
            insider_client=insider_client,
        )
        universe = StockScreener.load_universe()
        candidates = screener.screen(universe, max_candidates=_MAX_CANDIDATES)
        logger.info("Screener selected %d candidates: %s", len(candidates), candidates)
        return candidates

    candidates: List[str] = await step.run("screen-universe", run_screener)

    if not candidates:
        logger.error("Screener returned no candidates — aborting batch")
        return {"status": "aborted", "reason": "empty_candidates"}

    # ── Step 2: Market context ───────────────────────────────────────────────
    async def fetch_market_context() -> Dict[str, Any]:
        market_client = MarketDataClient()
        service = MarketContextService(market_client=market_client)
        ctx = service.get_context()
        return ctx.to_dict()

    market_ctx_dict: Dict[str, Any] = await step.run(
        "fetch-market-context", fetch_market_context
    )

    # ── Steps 3+N: Analyze each ticker ──────────────────────────────────────
    results: Dict[str, Any] = {}
    batch_user_id = _get_batch_user_id()

    for rank, ticker in enumerate(candidates):
        async def analyze_one(t: str = ticker) -> Dict[str, Any]:
            logger.info("Batch analyzing %s", t)
            return await run_stock_analysis(
                ticker=t,
                quarters=_QUARTERS,
                news_days_back=_NEWS_DAYS_BACK,
                user_id=batch_user_id,
            )

        result = await step.run(f"analyze-{ticker.lower()}", analyze_one)
        results[ticker] = {"result": result, "rank": rank}

    # ── Final step: Extract and store signals ────────────────────────────────
    async def store_all_signals() -> Dict[str, int]:
        from api.services.market_context_service import MarketContext

        market_context = MarketContext(
            es_change_pct=market_ctx_dict.get("es_change_pct"),
            nq_change_pct=market_ctx_dict.get("nq_change_pct"),
            dow_change_pct=market_ctx_dict.get("dow_change_pct"),
        )

        db = await get_db()
        signal_service = WeeklySignalService(db=db)
        stored = 0
        failed = 0

        for ticker, data in results.items():
            try:
                screener_score = float(_MAX_CANDIDATES - data["rank"])
                await signal_service.store_signal(
                    ticker=ticker,
                    result=data["result"],
                    run_date=run_date,
                    screener_score=screener_score,
                    market_context=market_context,
                )
                stored += 1
            except Exception as e:
                logger.error("Failed to store signal for %s: %s", ticker, e)
                failed += 1

        logger.info("Weekly batch complete: stored=%d failed=%d", stored, failed)
        return {"stored": stored, "failed": failed}

    summary = await step.run("store-signals", store_all_signals)

    return {
        "status": "completed",
        "run_date": run_date.isoformat(),
        "candidates": candidates,
        **summary,
    }
