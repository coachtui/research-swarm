"""
Cron scheduler for portfolio engine cycles.

Uses APScheduler (AsyncIOScheduler) to run:
  - Monthly (1st of month, 06:00 UTC): drawdown adds, euphoria trims, thesis breaks
  - Quarterly (Jan/Apr/Jul/Oct 1st, 08:00 UTC): durability re-rank, compounder scores
  - Annual (Jan 1, 10:00 UTC): full rebalance and structural hygiene

Scheduler starts in FastAPI lifespan (non-blocking background task).
Guarded by ENABLE_CRON env var — off by default in development.

Usage (in api/index.py lifespan):
    from api.services.cron_scheduler import start_scheduler, stop_scheduler

    asyncio.create_task(start_scheduler())
    # ...
    await stop_scheduler()
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_scheduler = None


async def start_scheduler() -> None:
    """Initialize and start the cron scheduler. No-op if ENABLE_CRON is not set."""
    global _scheduler

    if os.getenv("ENABLE_CRON", "").lower() not in ("1", "true", "yes"):
        logger.info("Cron scheduler disabled (set ENABLE_CRON=true to enable)")
        return

    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.warning("apscheduler not installed — cron scheduler disabled")
        return

    _scheduler = AsyncIOScheduler()

    # Monthly: 1st of month at 06:00 UTC
    _scheduler.add_job(
        _run_monthly_cycle,
        CronTrigger(day=1, hour=6, minute=0),
        id="monthly_engine_cycle",
        name="Monthly Engine Cycle",
        misfire_grace_time=3600,
    )

    # Quarterly: 1st of Jan/Apr/Jul/Oct at 08:00 UTC
    _scheduler.add_job(
        _run_quarterly_cycle,
        CronTrigger(month="1,4,7,10", day=1, hour=8, minute=0),
        id="quarterly_engine_cycle",
        name="Quarterly Engine Cycle",
        misfire_grace_time=3600,
    )

    # Annual: Jan 1 at 10:00 UTC
    _scheduler.add_job(
        _run_annual_cycle,
        CronTrigger(month=1, day=1, hour=10, minute=0),
        id="annual_engine_cycle",
        name="Annual Engine Cycle",
        misfire_grace_time=3600,
    )

    _scheduler.start()
    logger.info("Portfolio engine cron scheduler started (3 jobs registered)")


async def stop_scheduler() -> None:
    """Stop the scheduler gracefully."""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Portfolio engine cron scheduler stopped")


# ── Cycle Runners ────────────────────────────────────────────────────────────


async def _run_cycle(cycle_type: str) -> None:
    """Generic cycle runner — iterates all portfolios."""
    from api.lib.db import get_db
    from api.services.portfolio_engine import run_portfolio_engine

    logger.info("Starting %s engine cycle for all portfolios", cycle_type)

    try:
        db = await get_db()
        portfolios = await db.portfolio.find_many(
            include={"positions": True},
        )

        success = 0
        failed = 0
        for p in portfolios:
            if not p.positions:
                continue
            try:
                result = await run_portfolio_engine(p.id, cycle_type)
                actions = result.get("actions_created", 0)
                logger.info(
                    "%s cycle: portfolio %s — %d actions",
                    cycle_type, p.id[:8], actions,
                )
                success += 1
            except Exception as e:
                logger.error(
                    "%s cycle failed for portfolio %s: %s",
                    cycle_type, p.id[:8], e, exc_info=True,
                )
                failed += 1

        logger.info(
            "%s engine cycle complete: %d succeeded, %d failed (of %d total)",
            cycle_type, success, failed, len(portfolios),
        )
    except Exception as e:
        logger.error("Fatal error in %s cycle: %s", cycle_type, e, exc_info=True)


async def _run_monthly_cycle() -> None:
    await _run_cycle("monthly")


async def _run_quarterly_cycle() -> None:
    await _run_cycle("quarterly")


async def _run_annual_cycle() -> None:
    await _run_cycle("annual")
