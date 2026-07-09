"""
Theme delta — weekly constituent delta pass (cheap model, no web search).

Cron: Saturdays 14:00 UTC so Sunday's ranking sees fresh membership; 14:00
avoids colliding with the monthly pass when the 1st falls on a Saturday.
Steps: gather -> reason (PAID, memoized alone) -> parse+validate -> apply.
End-to-end failure = no changes this cycle + engine_failure journal entry
via on_failure; the outlook and Sleeve B never notice.

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
            "theme delta weekly failed",
            f"theme-delta-weekly failed after retries: {ctx.event.data}",
            source="theme_delta_weekly",
        )

    @inngest_client.create_function(
        fn_id="theme-delta-weekly",
        trigger=inngest_sdk.TriggerCron(cron="0 14 * * 6"),
        name="Theme Delta (weekly constituent pass)",
        retries=1,
        on_failure=_on_failure,
    )
    async def theme_delta_weekly(ctx: "inngest_sdk.Context") -> Dict[str, Any]:
        step = ctx.step

        # Step 1: gather current (active-only) theme state
        async def gather_context() -> Dict[str, Any]:
            from api.lib.db import get_db  # noqa: PLC0415
            from execution.themes.delta import gather_delta_context  # noqa: PLC0415

            db = await get_db()
            return await gather_delta_context(db)

        context = await step.run("gather-context", gather_context)

        # Step 2: the PAID LLM call — its own memoized step so a later
        # apply failure on retry never re-bills this call.
        async def reason() -> str:
            import asyncio  # noqa: PLC0415

            from execution.themes.delta import reason_delta  # noqa: PLC0415

            return await asyncio.to_thread(reason_delta, context)

        raw = await step.run("reason", reason)

        # Step 3: parse + validate tickers (free, pure)
        async def parse_validate() -> Dict[str, Any]:
            from execution.themes.delta import parse_and_validate_delta  # noqa: PLC0415

            return parse_and_validate_delta(raw)

        bundle = await step.run("parse-validate", parse_validate)

        # Step 4: apply plan against current DB state
        async def apply() -> Dict[str, Any]:
            from api.lib.db import get_db  # noqa: PLC0415
            from execution.themes.delta import apply_delta  # noqa: PLC0415

            db = await get_db()
            return await apply_delta(db, bundle)

        summary = await step.run("apply", apply)
        logger.info("theme delta weekly: %s", summary)
        return summary

    return theme_delta_weekly


try:
    theme_delta_weekly = _register_inngest_function()
except Exception:
    theme_delta_weekly = None  # type: ignore[assignment]
