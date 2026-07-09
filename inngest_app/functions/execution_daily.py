"""
Daily execution health cron — Autopilot Phase 2.

Cron: weekdays 21:15 UTC (>= 15 min after the NYSE close in EST and EDT).
Pipeline: linked account -> broker snapshot -> reconcile vs EnginePosition
-> SleeveSnapshot upsert -> circuit-breaker check. This cron NEVER trades.

Failure posture: reconciliation mismatch freezes the sleeve + alerts;
a tripped circuit breaker halts the sleeve + alerts (once, on the
active->halted transition); any unhandled step failure alerts via
on_failure. Never guesses, never trades.

Step results are JSON-serializable and never contain decrypted API keys —
any step that needs the broker rebuilds the client inside the step.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


# ── Pure helpers (unit-tested) ───────────────────────────────────────────────

def build_sleeve_snapshot(
    state_cash: float,
    engine_symbols: List[str],
    broker_positions: List[Dict[str, Any]],
) -> Dict[str, float]:
    """Sleeve equity = internal cash ledger + broker market value of the
    sleeve's symbols (broker prices are the ground truth for value)."""
    positions_value = sum(
        p["market_value"] for p in broker_positions if p["symbol"] in set(engine_symbols)
    )
    return {
        "positions_value": round(positions_value, 2),
        "equity": round(state_cash + positions_value, 2),
    }


# ── Inngest function (guarded registration, weekly_outlook.py pattern) ──────

def _register_inngest_function():
    import inngest as inngest_sdk  # noqa: PLC0415

    from inngest_app.client import inngest_client  # noqa: PLC0415

    async def _on_failure(ctx: "inngest_sdk.Context") -> None:
        from execution.alerts import send_failure_alert  # noqa: PLC0415

        await send_failure_alert(
            "daily execution cron failed",
            f"execution-daily failed after retries: {ctx.event.data}",
            source="execution_daily",
        )

    @inngest_client.create_function(
        fn_id="execution-daily",
        trigger=inngest_sdk.TriggerCron(cron="15 21 * * 1-5"),  # weekdays 21:15 UTC
        name="Autopilot Daily Snapshot",
        retries=1,
        on_failure=_on_failure,
    )
    async def execution_daily(ctx: "inngest_sdk.Context") -> Dict[str, Any]:
        step = ctx.step

        async def run_date_step() -> str:
            return datetime.now(timezone.utc).isoformat()  # replay-safe: captured once

        run_date_iso = await step.run("run-date", run_date_step)

        # Step 1: is there a linked account + sleeve state at all?
        async def load_context() -> Dict[str, Any]:
            from api.lib.db import get_db  # noqa: PLC0415
            from execution.broker.credentials import get_active_alpaca_account  # noqa: PLC0415
            from execution.constants import SLEEVE_B  # noqa: PLC0415
            from execution.sleeve_service import get_engine_positions, get_sleeve_state  # noqa: PLC0415

            db = await get_db()
            account = await get_active_alpaca_account(db)
            if account is None:
                return {"linked": False}
            state = await get_sleeve_state(db, SLEEVE_B)
            positions = await get_engine_positions(db, SLEEVE_B)
            return {
                "linked": True,
                "has_state": state is not None,
                "status": state.status if state else None,
                "cash": state.cashBalance if state else 0.0,
                "inception_equity": state.inceptionEquity if state else 0.0,
                "inception_spy": state.inceptionSpyClose if state else 0.0,
                "engine_positions": {p.symbol: p.qty for p in positions},
            }

        context = await step.run("load-context", load_context)
        if not context["linked"] or not context["has_state"]:
            return {"status": "skipped", "reason": "no linked account or sleeve not bootstrapped"}

        # Step 2: broker snapshot (client built inside the step — no secrets out)
        async def broker_snapshot() -> Dict[str, Any]:
            import asyncio  # noqa: PLC0415

            from api.lib.db import get_db  # noqa: PLC0415
            from execution.broker.alpaca_client import client_from_account  # noqa: PLC0415
            from execution.broker.credentials import get_active_alpaca_account  # noqa: PLC0415

            db = await get_db()
            client = client_from_account(await get_active_alpaca_account(db))
            positions = await asyncio.to_thread(client.get_positions)
            summary = await asyncio.to_thread(client.get_account_summary)
            return {"positions": [p.to_dict() for p in positions], "account": summary}

        broker = await step.run("broker-snapshot", broker_snapshot)

        # Step 3: reconcile — mismatch freezes the sleeve, no snapshot written
        async def reconcile() -> Dict[str, Any]:
            from api.lib.db import get_db  # noqa: PLC0415
            from execution.alerts import send_failure_alert  # noqa: PLC0415
            from execution.constants import SLEEVE_B  # noqa: PLC0415
            from execution.engine.reconcile import find_mismatches  # noqa: PLC0415
            from execution.sleeve_service import set_sleeve_status  # noqa: PLC0415

            broker_qty = {p["symbol"]: p["qty"] for p in broker["positions"]}
            mismatches = find_mismatches(broker_qty, context["engine_positions"])
            if mismatches:
                db = await get_db()
                await set_sleeve_status(db, SLEEVE_B, "frozen", "; ".join(mismatches))
                await send_failure_alert(
                    "position reconciliation mismatch — Sleeve B frozen",
                    "\n".join(mismatches),
                    source="execution_daily",
                )
            return {"mismatches": mismatches}

        recon = await step.run("reconcile", reconcile)
        if recon["mismatches"]:
            return {"status": "frozen", "mismatches": recon["mismatches"]}

        # Step 4: snapshot sleeve equity + SPY benchmark
        async def snapshot() -> Dict[str, Any]:
            import asyncio  # noqa: PLC0415

            from api.lib.db import get_db  # noqa: PLC0415
            from execution.constants import BENCHMARK, SLEEVE_B  # noqa: PLC0415
            from execution.sleeve_service import store_snapshot  # noqa: PLC0415
            from research_swarm.data.market_data_client import MarketDataClient  # noqa: PLC0415

            def spy_close() -> float:
                df = MarketDataClient().get_historical_data(BENCHMARK, period="5d")
                return float(df["Close"].dropna().iloc[-1])

            spy = await asyncio.to_thread(spy_close)
            snap = build_sleeve_snapshot(
                context["cash"],
                list(context["engine_positions"].keys()),
                broker["positions"],
            )
            run_date = datetime.fromisoformat(run_date_iso)
            snapshot_date = run_date.replace(hour=0, minute=0, second=0, microsecond=0)
            db = await get_db()
            await store_snapshot(
                db, SLEEVE_B, snapshot_date,
                equity=snap["equity"], cash=context["cash"],
                positions_value=snap["positions_value"], spy_close=spy,
            )
            return {"equity": snap["equity"], "spy_close": spy}

        snap = await step.run("snapshot", snapshot)

        # Step 5: circuit breaker (alert only on the active->halted transition)
        async def breaker_check() -> Dict[str, Any]:
            from api.lib.db import get_db  # noqa: PLC0415
            from execution.alerts import send_failure_alert  # noqa: PLC0415
            from execution.constants import SLEEVE_B  # noqa: PLC0415
            from execution.engine.circuit_breaker import circuit_breaker_tripped  # noqa: PLC0415
            from execution.sleeve_service import set_sleeve_status  # noqa: PLC0415

            tripped = circuit_breaker_tripped(
                snap["equity"], context["inception_equity"],
                snap["spy_close"], context["inception_spy"],
            )
            if tripped and context["status"] == "active":
                db = await get_db()
                await set_sleeve_status(
                    db, SLEEVE_B, "halted", "circuit breaker: -15pp vs SPY since inception"
                )
                await send_failure_alert(
                    "Sleeve B circuit breaker tripped",
                    f"equity={snap['equity']} inception={context['inception_equity']} "
                    f"spy={snap['spy_close']} inception_spy={context['inception_spy']}. "
                    "New buys halted; POST /api/autopilot/sleeve/B/resume to resume.",
                    source="execution_daily",
                )
            return {"tripped": tripped}

        breaker = await step.run("circuit-breaker", breaker_check)
        return {"status": "ok", "equity": snap["equity"], "breaker_tripped": breaker["tripped"]}

    return execution_daily


try:
    execution_daily = _register_inngest_function()
except Exception:
    execution_daily = None  # type: ignore[assignment]
