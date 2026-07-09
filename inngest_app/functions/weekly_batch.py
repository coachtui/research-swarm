"""
Tiered weekly batch: screener → quant snapshots → escalation → capped swarm.

Fires Monday 03:00 UTC (Sun 11 PM EDT / 10 PM EST), 7 hours after the Sunday 20:00 UTC
MarketOutlook cron, so a fresh outlook exists.

Funnel (docs/superpowers/specs/2026-07-08-tiered-batch-design.md):
  191 names, free screener
    → top BATCH_MAX_CANDIDATES ∪ watchlisted: free quant rows (tier="quant")
    → weighted escalation scoring (free)
    → ≤ BATCH_MAX_SWARM_RUNS paid swarm analyses (rows upgraded to "full").
Fresh user reports (<7d) are reused at zero cost and consume no cap slot.
Failed swarm slots are NOT refunded — runs stay deterministic and bounded.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_MAX_CANDIDATES = int(os.getenv("BATCH_MAX_CANDIDATES", "20"))
_MAX_SWARM_RUNS = int(os.getenv("BATCH_MAX_SWARM_RUNS", "5"))
_ESCALATION_THRESHOLD = float(os.getenv("BATCH_ESCALATION_THRESHOLD", "2.0"))
_OUTLOOK_MAX_AGE_DAYS = 8
_FRESH_REPORT_MAX_AGE_DAYS = 7
_TOP_SECTORS = 3
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


def _register_inngest_function():
    """Register the Inngest function. Called at module load only when the
    inngest client is importable (i.e. not during unit-test collection)."""
    import inngest as inngest_sdk  # noqa: PLC0415 — pip SDK (module-level Trigger* classes)

    from inngest_app.client import inngest_client  # noqa: PLC0415

    if inngest_client is None:
        raise RuntimeError("inngest pip SDK not available — client is None")

    from api.lib.db import get_db  # noqa: PLC0415
    from api.services.analysis_service import run_stock_analysis  # noqa: PLC0415
    from api.services.market_context_service import MarketContextService  # noqa: PLC0415
    from api.services.weekly_signal_service import WeeklySignalService  # noqa: PLC0415
    from research_swarm.data.escalation import (  # noqa: PLC0415
        EscalationCandidate,
        EscalationContext,
        select_escalations,
    )
    from research_swarm.data.market_data_client import MarketDataClient  # noqa: PLC0415
    from research_swarm.data.openinsider_client import OpenInsiderClient  # noqa: PLC0415
    from research_swarm.data.screener import StockScreener  # noqa: PLC0415

    @inngest_client.create_function(
        fn_id="weekly-batch",
        trigger=inngest_sdk.TriggerCron(cron="0 3 * * 1"),  # Monday 03:00 UTC (Sun 11 PM EDT / 10 PM EST)
        name="Weekly Batch Analysis (Tiered)",
        retries=1,
    )
    async def weekly_batch(ctx: "inngest_sdk.Context") -> Dict[str, Any]:
        step = ctx.step  # steps live on ctx in the current SDK

        # Capture run_date in a step so Inngest replays crossing UTC midnight
        # reuse the memoized value instead of orphaning the quant rows.
        run_date_iso: str = await step.run(
            "capture-run-date",
            lambda: datetime.now(timezone.utc)
            .replace(hour=0, minute=0, second=0, microsecond=0)
            .isoformat(),
        )
        run_date = datetime.fromisoformat(run_date_iso)

        # ── Step 1: latest market outlook → favored sectors ─────────────────
        async def load_outlook() -> Dict[str, Any]:
            db = await get_db()
            outlook = await db.marketoutlook.find_first(order={"runDate": "desc"})
            if outlook is None:
                logger.warning("No MarketOutlook row — outlook trigger disabled")
                return {"favored_sectors": [], "outlook_run_date": None}
            age = datetime.now(timezone.utc) - outlook.runDate.replace(
                tzinfo=timezone.utc
            )
            if age > timedelta(days=_OUTLOOK_MAX_AGE_DAYS):
                logger.warning(
                    "MarketOutlook is %s old — outlook trigger disabled", age
                )
                return {"favored_sectors": [], "outlook_run_date": None}
            rankings = sorted(
                outlook.sectorRankings, key=lambda r: r["score"], reverse=True
            )
            favored = [r["sector"] for r in rankings[:_TOP_SECTORS]]
            return {
                "favored_sectors": favored,
                "outlook_run_date": outlook.runDate.isoformat(),
            }

        outlook: Dict[str, Any] = await step.run("load-outlook", load_outlook)

        # ── Step 2: screen all 191 names; advance top N ∪ watchlisted ────────
        async def run_screener() -> List[Dict[str, Any]]:
            screener = StockScreener(
                market_client=MarketDataClient(),
                insider_client=OpenInsiderClient(),
            )
            universe = StockScreener.load_universe()
            scored = await asyncio.to_thread(screener.screen_all, universe)

            db = await get_db()
            wl_rows = await db.watchlist.find_many(distinct=["ticker"])
            watchlisted = {w.ticker.upper() for w in wl_rows}

            top = scored[:_MAX_CANDIDATES]
            top_tickers = {st.ticker for st in top}
            extra = [
                st for st in scored
                if st.ticker in watchlisted and st.ticker not in top_tickers
            ]
            advancing = top + extra
            sector_map = StockScreener.load_sector_map()
            logger.info(
                "Screener advancing %d tickers (%d watchlist extras)",
                len(advancing), len(extra),
            )
            return [
                {
                    "ticker": st.ticker,
                    "score": st.score,
                    "sector": sector_map.get(st.ticker),
                    "on_watchlist": st.ticker in watchlisted,
                    "has_insider_buying": st.signals.has_insider_buying,
                    "weekly_price_change_pct": st.signals.weekly_price_change_pct,
                    "days_to_earnings": st.signals.days_to_earnings,
                    "days_since_earnings": st.signals.days_since_earnings,
                }
                for st in advancing
            ]

        candidates: List[Dict[str, Any]] = await step.run(
            "screen-universe", run_screener
        )

        if not candidates:
            logger.error("Screener returned no candidates — aborting batch")
            return {"status": "aborted", "reason": "empty_candidates"}

        # ── Step 3: free quant snapshots (tier="quant") ──────────────────────
        async def write_quant_snapshots() -> Dict[str, Any]:
            db = await get_db()
            service = WeeklySignalService(db=db)
            market_client = MarketDataClient()
            market_context = await asyncio.to_thread(
                MarketContextService(market_client=market_client).get_context
            )

            priors: Dict[str, Dict[str, Any]] = {}
            stored_tickers: List[str] = []
            stored = failed = 0
            for c in candidates:
                try:
                    prior_ctx = await service.get_prior_context(
                        c["ticker"], before=run_date
                    )
                    priors[c["ticker"]] = prior_ctx
                    current_price = await asyncio.to_thread(
                        market_client.get_current_price, c["ticker"]
                    )
                    await service.store_quant_snapshot(
                        ticker=c["ticker"],
                        run_date=run_date,
                        screener_score=c["score"],
                        current_price=current_price,
                        quant_signals={
                            "has_insider_buying": c["has_insider_buying"],
                            "weekly_price_change_pct": c["weekly_price_change_pct"],
                            "days_to_earnings": c["days_to_earnings"],
                            "days_since_earnings": c["days_since_earnings"],
                            "on_watchlist": c["on_watchlist"],
                        },
                        market_context=market_context,
                        prior_ctx=prior_ctx,
                    )
                    stored += 1
                    stored_tickers.append(c["ticker"])
                except Exception as e:
                    logger.error("Quant snapshot failed for %s: %s", c["ticker"], e)
                    failed += 1
            return {
                "stored": stored,
                "failed": failed,
                "priors": priors,
                "stored_tickers": stored_tickers,
            }

        quant: Dict[str, Any] = await step.run(
            "quant-snapshots", write_quant_snapshots
        )

        # ── Step 4: weighted escalation (free) ───────────────────────────────
        async def compute_escalation() -> List[Dict[str, Any]]:
            db = await get_db()
            service = WeeklySignalService(db=db)
            context = EscalationContext(
                favored_sectors=frozenset(outlook["favored_sectors"])
            )
            escalation_candidates = []
            # Only tickers whose quant row was actually written may escalate;
            # otherwise upgrade_to_full would fail after the swarm spend.
            stored_set = set(quant["stored_tickers"])
            for c in candidates:
                if c["ticker"] not in stored_set:
                    continue
                prior = quant["priors"].get(c["ticker"], {})
                fresh = await service.find_fresh_result(
                    c["ticker"], max_age_days=_FRESH_REPORT_MAX_AGE_DAYS
                )
                escalation_candidates.append(
                    EscalationCandidate(
                        ticker=c["ticker"],
                        screener_score=c["score"],
                        sector=c.get("sector"),
                        prior_screener_score=prior.get("prior_screener_score"),
                        prior_verdict=prior.get("prior_verdict"),
                        days_since_earnings=c.get("days_since_earnings"),
                        on_watchlist=c.get("on_watchlist", False),
                        has_fresh_report=fresh is not None,
                    )
                )
            decisions = select_escalations(
                escalation_candidates,
                context,
                cap=_MAX_SWARM_RUNS,
                threshold=_ESCALATION_THRESHOLD,
            )
            for d in decisions:
                await service.record_escalation(
                    ticker=d.ticker, run_date=run_date,
                    score=d.score, reasons=d.reasons,
                )
            logger.info(
                "Escalation: %d swarm, %d reuse, %d hold",
                sum(1 for d in decisions if d.action == "swarm"),
                sum(1 for d in decisions if d.action == "reuse"),
                sum(1 for d in decisions if d.action == "hold"),
            )
            return [
                {"ticker": d.ticker, "score": d.score,
                 "reasons": d.reasons, "action": d.action}
                for d in decisions
            ]

        decisions: List[Dict[str, Any]] = await step.run(
            "compute-escalation", compute_escalation
        )

        reuse_list = [d for d in decisions if d["action"] == "reuse"]
        swarm_list = [d for d in decisions if d["action"] == "swarm"]
        outcomes: Dict[str, str] = {}

        # ── Steps 5a: zero-cost reuse of fresh user reports ──────────────────
        for d in reuse_list:
            async def reuse_one(dd: Dict[str, Any] = d) -> str:
                db = await get_db()
                service = WeeklySignalService(db=db)
                result = await service.find_fresh_result(
                    dd["ticker"], max_age_days=_FRESH_REPORT_MAX_AGE_DAYS
                )
                if result is None:  # report aged out / vanished — stay quant
                    return "reuse_missing"
                ok = await service.upgrade_to_full(
                    ticker=dd["ticker"], run_date=run_date, result=result,
                    escalation_score=dd["score"],
                    escalation_reasons=dd["reasons"],
                )
                return "reused" if ok else "reuse_unusable"

            try:
                outcomes[d["ticker"]] = await step.run(
                    f"reuse-{d['ticker'].lower()}", reuse_one
                )
            except Exception as e:  # noqa: BLE001 — one ticker must not sink the run
                logger.error("Reuse step failed permanently for %s: %s", d["ticker"], e)
                outcomes[d["ticker"]] = "step_failed"

        # ── Steps 5b: paid swarm analyses (the ONLY paid stage) ──────────────
        if swarm_list:
            batch_user_id = _get_batch_user_id()
            for d in swarm_list:
                # Analyze (paid) and persist (free) are SEPARATE steps: the
                # paid result is memoized once it succeeds, so a persistence
                # bug can never re-run the analysis on retry (2026-07-08
                # incident: schema-drift crash in persist double-billed every
                # swarm ticker when both lived in one step).
                async def analyze_one(dd: Dict[str, Any] = d) -> Dict[str, Any]:
                    logger.info("Batch analyzing %s", dd["ticker"])
                    return await run_stock_analysis(
                        ticker=dd["ticker"],
                        quarters=_QUARTERS,
                        news_days_back=_NEWS_DAYS_BACK,
                        user_id=batch_user_id,
                    )

                try:
                    result = await step.run(
                        f"analyze-{d['ticker'].lower()}", analyze_one
                    )
                except Exception as e:  # noqa: BLE001 — one ticker must not sink the run
                    logger.error("Analyze step failed permanently for %s: %s", d["ticker"], e)
                    outcomes[d["ticker"]] = "step_failed"
                    continue

                async def persist_one(
                    dd: Dict[str, Any] = d, res: Dict[str, Any] = result
                ) -> str:
                    db = await get_db()
                    service = WeeklySignalService(db=db)
                    ok = await service.upgrade_to_full(
                        ticker=dd["ticker"], run_date=run_date, result=res,
                        escalation_score=dd["score"],
                        escalation_reasons=dd["reasons"],
                    )
                    return "full" if ok else "analysis_failed"

                try:
                    outcomes[d["ticker"]] = await step.run(
                        f"persist-{d['ticker'].lower()}", persist_one
                    )
                except Exception as e:  # noqa: BLE001 — one ticker must not sink the run
                    logger.error("Persist step failed permanently for %s: %s", d["ticker"], e)
                    outcomes[d["ticker"]] = "step_failed"

        # ── Final step: fire batch/completed for (dormant) downstream fns ────
        # send_event is itself a step tool — never wrap it in step.run
        # (nested steps are a non-retriable SDK error).
        await step.send_event(
            "batch-completed-event",
            inngest_sdk.Event(
                name="batch/completed",
                data={
                    "run_date": run_date.isoformat(),
                    "ticker_count": sum(
                        1 for v in outcomes.values() if v in ("full", "reused")
                    ),
                },
            ),
        )

        return {
            "status": "completed",
            "run_date": run_date.isoformat(),
            "candidates": len(candidates),
            "quant_stored": quant["stored"],
            "quant_failed": quant["failed"],
            "swarm": len(swarm_list),
            "reused": len(reuse_list),
            "outcomes": outcomes,
        }

    return weekly_batch


try:
    weekly_batch = _register_inngest_function()
except Exception:
    # inngest pip package not available (e.g. during unit tests) — no-op.
    weekly_batch = None  # type: ignore[assignment]
