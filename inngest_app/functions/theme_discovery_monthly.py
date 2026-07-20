"""
Theme discovery — monthly SA reasoning pass (Autopilot Phase 3B).

Cron: 1st of month 12:00 UTC (clear of Sunday 20:00 outlook, Monday 15:00
rebalance, Saturday 14:00 delta). Steps: gather -> reason (PAID, memoized
alone) -> parse+validate -> apply. End-to-end failure = no changes this
cycle + engine_failure journal entry via on_failure; the outlook and
Sleeve B never notice.

The reason step wraps the (blocking, synchronous) LLM network call in
asyncio.to_thread — same posture execution_daily.py uses for its blocking
broker/market-data calls (broker_snapshot, snapshot) so the paid call never
blocks the event loop.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


# ── Inngest function (guarded registration, execution_daily.py pattern) ────

def _register_inngest_function():
    import inngest as inngest_sdk  # noqa: PLC0415

    from inngest_app.client import inngest_client  # noqa: PLC0415

    async def _on_failure(ctx: "inngest_sdk.Context") -> None:
        from execution.alerts import send_failure_alert  # noqa: PLC0415

        await send_failure_alert(
            "theme discovery monthly failed",
            f"theme-discovery-monthly failed after retries: {ctx.event.data}",
            source="theme_discovery_monthly",
        )

    @inngest_client.create_function(
        fn_id="theme-discovery-monthly",
        trigger=inngest_sdk.TriggerCron(cron="0 12 1 * *"),
        name="Theme Discovery (monthly reasoning pass)",
        retries=1,
        on_failure=_on_failure,
    )
    async def theme_discovery_monthly(ctx: "inngest_sdk.Context") -> Dict[str, Any]:
        step = ctx.step

        # Step 1: gather current theme state + rankings + research context
        async def gather_context() -> Dict[str, Any]:
            from api.lib.db import get_db  # noqa: PLC0415
            from execution.themes.discovery import gather_monthly_context  # noqa: PLC0415

            db = await get_db()
            return await gather_monthly_context(db)

        context = await step.run("gather-context", gather_context)

        # Step 2: the PAID LLM call — its own memoized step so a later
        # apply failure on retry never re-bills this call.
        async def reason() -> str:
            import asyncio  # noqa: PLC0415

            from execution.themes.discovery import reason_monthly  # noqa: PLC0415

            return await asyncio.to_thread(reason_monthly, context)

        raw = await step.run("reason", reason)

        # Step 3: parse + validate tickers (free). Same broker-universe gate as
        # the weekly delta pass — see theme_delta_weekly.py.
        async def parse_validate() -> Dict[str, Any]:
            from api.lib.db import get_db  # noqa: PLC0415
            from execution.broker.tradable import alpaca_tradable_symbols  # noqa: PLC0415
            from execution.themes.discovery import parse_and_validate_monthly  # noqa: PLC0415

            db = await get_db()
            tradable = await alpaca_tradable_symbols(db)
            return parse_and_validate_monthly(raw, tradable=tradable)

        bundle = await step.run("parse-validate", parse_validate)

        # Step 4: apply plan against current DB state
        async def apply() -> Dict[str, Any]:
            from api.lib.db import get_db  # noqa: PLC0415
            from execution.themes.discovery import apply_monthly  # noqa: PLC0415

            db = await get_db()
            return await apply_monthly(db, bundle)

        summary = await step.run("apply", apply)
        logger.info("theme discovery monthly: %s", summary)
        return summary

    return theme_discovery_monthly


try:
    theme_discovery_monthly = _register_inngest_function()
except Exception:
    theme_discovery_monthly = None  # type: ignore[assignment]
