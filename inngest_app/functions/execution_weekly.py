"""
Weekly Sleeve B rebalance — Autopilot Phase 2.

Cron: Monday 15:00 UTC (inside regular NYSE hours in EST and EDT; after the
Sunday 20:00 outlook and the Monday 03:00 batch).

Pipeline: preflight (account, sleeve state, fresh outlook, market open)
-> bootstrap sleeve on first run -> reconcile -> pure plan (targets, orders,
guardrails) -> one memoized step per order (retries can never double-trade)
-> persist fills + cash ledger -> summary.

Failure posture: any precondition failure -> skip the week + alert.
Doing nothing for a week never hurts a long-horizon portfolio.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


# ── Pure helpers (unit-tested) ───────────────────────────────────────────────

def outlook_is_stale(outlook_run_date_iso: str, now_iso: str) -> bool:
    from execution.constants import OUTLOOK_MAX_AGE_DAYS

    outlook_dt = datetime.fromisoformat(outlook_run_date_iso)
    now_dt = datetime.fromisoformat(now_iso)
    return (now_dt - outlook_dt).days >= OUTLOOK_MAX_AGE_DAYS


def build_rebalance_plan(
    outlook: Dict[str, Any],
    engine_positions: Dict[str, float],
    broker_positions: List[Dict[str, Any]],
    state: Dict[str, Any],
) -> Dict[str, Any]:
    """(outlook, book, state) -> {orders, journal, notes}. Pure."""
    from execution.engine.guardrails import enforce_guardrails
    from execution.engine.orders import diff_to_orders
    from execution.engine.sleeve_b import compute_targets

    held = sorted(engine_positions.keys())
    sleeve_positions = {
        p["symbol"]: p for p in broker_positions if p["symbol"] in engine_positions
    }
    positions_value = sum(p["market_value"] for p in sleeve_positions.values())
    sleeve_equity = state["cashBalance"] + positions_value

    result = compute_targets(outlook, held, sleeve_equity)
    orders = diff_to_orders(result["targets"], sleeve_positions)
    orders, notes = enforce_guardrails(
        orders,
        account_equity=state["accountEquity"],
        cash_available=state["cashBalance"],
        allow_buys=state["status"] == "active",
    )
    journal = {**result["journal"], "guardrail_notes": notes}
    return {"orders": orders, "journal": journal, "notes": notes}


# ── Inngest function (guarded registration) ─────────────────────────────────

def _register_inngest_function():
    import inngest as inngest_sdk  # noqa: PLC0415

    from inngest_app.client import inngest_client  # noqa: PLC0415

    async def _on_failure(ctx: "inngest_sdk.Context") -> None:
        from execution.alerts import send_failure_alert  # noqa: PLC0415

        await send_failure_alert(
            "weekly rebalance failed",
            f"execution-weekly failed after retries: {ctx.event.data}",
            source="execution_weekly",
        )

    @inngest_client.create_function(
        fn_id="execution-weekly",
        trigger=inngest_sdk.TriggerCron(cron="0 15 * * 1"),  # Monday 15:00 UTC
        name="Autopilot Sleeve B Rebalance",
        retries=1,
        on_failure=_on_failure,
    )
    async def execution_weekly(ctx: "inngest_sdk.Context") -> Dict[str, Any]:
        step = ctx.step

        async def run_date_step() -> str:
            return datetime.now(timezone.utc).isoformat()

        run_date_iso = await step.run("run-date", run_date_step)

        # Step 1: preflight — account, outlook freshness, market open
        async def preflight() -> Dict[str, Any]:
            import asyncio  # noqa: PLC0415

            from api.lib.db import get_db  # noqa: PLC0415
            from execution.alerts import send_failure_alert  # noqa: PLC0415
            from execution.broker.alpaca_client import client_from_account  # noqa: PLC0415
            from execution.broker.credentials import get_active_alpaca_account  # noqa: PLC0415
            from execution.constants import SLEEVE_B  # noqa: PLC0415
            from execution.outlook_service import get_latest_outlook  # noqa: PLC0415
            from execution.sleeve_service import get_sleeve_state  # noqa: PLC0415

            db = await get_db()
            account = await get_active_alpaca_account(db)
            if account is None:
                return {"go": False, "reason": "no linked broker account"}

            outlook_row = await get_latest_outlook(db)
            if outlook_row is None:
                await send_failure_alert(
                    "rebalance skipped", "no MarketOutlook row exists",
                    source="execution_weekly",
                )
                return {"go": False, "reason": "no outlook"}
            outlook_iso = outlook_row.runDate.isoformat()
            if outlook_is_stale(outlook_iso, run_date_iso):
                await send_failure_alert(
                    "rebalance skipped", f"latest outlook is stale ({outlook_iso})",
                    source="execution_weekly",
                )
                return {"go": False, "reason": "stale outlook"}

            state = await get_sleeve_state(db, SLEEVE_B)
            if state is not None and state.status == "frozen":
                await send_failure_alert(
                    "rebalance skipped", f"Sleeve B frozen: {state.statusReason}",
                    source="execution_weekly",
                )
                return {"go": False, "reason": "sleeve frozen"}

            client = client_from_account(account)
            if not await asyncio.to_thread(client.is_market_open):
                await send_failure_alert(
                    "rebalance skipped", "market closed (holiday?)",
                    source="execution_weekly",
                )
                return {"go": False, "reason": "market closed"}

            return {
                "go": True,
                "outlook": {
                    "id": outlook_row.id,
                    "regime": outlook_row.regime,
                    "conviction": outlook_row.conviction,
                    "sectorRankings": outlook_row.sectorRankings,
                    "runDate": outlook_iso,
                },
                "has_state": state is not None,
                "sleeve_status": state.status if state else "active",
            }

        pre = await step.run("preflight", preflight)
        if not pre["go"]:
            return {"status": "skipped", "reason": pre["reason"]}

        # Step 2: bootstrap sleeve state on first ever run
        async def bootstrap() -> Dict[str, Any]:
            import asyncio  # noqa: PLC0415

            from api.lib.db import get_db  # noqa: PLC0415
            from execution.broker.alpaca_client import client_from_account  # noqa: PLC0415
            from execution.broker.credentials import get_active_alpaca_account  # noqa: PLC0415
            from execution.constants import BENCHMARK, SLEEVE_B, SLEEVE_B_FRACTION  # noqa: PLC0415
            from execution.sleeve_service import get_sleeve_state, init_sleeve_state  # noqa: PLC0415
            from research_swarm.data.market_data_client import MarketDataClient  # noqa: PLC0415

            db = await get_db()
            state = await get_sleeve_state(db, SLEEVE_B)
            if state is None:
                client = client_from_account(await get_active_alpaca_account(db))
                summary = await asyncio.to_thread(client.get_account_summary)

                def spy_close() -> float:
                    df = MarketDataClient().get_historical_data(BENCHMARK, period="5d")
                    return float(df["Close"].dropna().iloc[-1])

                spy = await asyncio.to_thread(spy_close)
                state = await init_sleeve_state(
                    db, SLEEVE_B,
                    cash=SLEEVE_B_FRACTION * summary["equity"],
                    spy_close=spy,
                    inception_date=datetime.fromisoformat(run_date_iso),
                )
                logger.info("Sleeve B bootstrapped: cash=%s", state.cashBalance)
            return {"cashBalance": state.cashBalance, "status": state.status}

        boot = await step.run("bootstrap-sleeve", bootstrap)

        # Step 3: broker book + reconcile
        async def load_book() -> Dict[str, Any]:
            import asyncio  # noqa: PLC0415

            from api.lib.db import get_db  # noqa: PLC0415
            from execution.alerts import send_failure_alert  # noqa: PLC0415
            from execution.broker.alpaca_client import client_from_account  # noqa: PLC0415
            from execution.broker.credentials import get_active_alpaca_account  # noqa: PLC0415
            from execution.constants import SLEEVE_B  # noqa: PLC0415
            from execution.engine.reconcile import find_mismatches  # noqa: PLC0415
            from execution.sleeve_service import (  # noqa: PLC0415
                get_engine_positions, set_sleeve_status,
            )

            db = await get_db()
            client = client_from_account(await get_active_alpaca_account(db))
            broker_positions = [
                p.to_dict() for p in await asyncio.to_thread(client.get_positions)
            ]
            summary = await asyncio.to_thread(client.get_account_summary)
            engine_rows = await get_engine_positions(db, SLEEVE_B)
            engine_qty = {p.symbol: p.qty for p in engine_rows}

            mismatches = find_mismatches(
                {p["symbol"]: p["qty"] for p in broker_positions}, engine_qty
            )
            if mismatches:
                await set_sleeve_status(db, SLEEVE_B, "frozen", "; ".join(mismatches))
                await send_failure_alert(
                    "rebalance aborted — reconciliation mismatch, Sleeve B frozen",
                    "\n".join(mismatches),
                    source="execution_weekly",
                )
            return {
                "mismatches": mismatches,
                "broker_positions": broker_positions,
                "engine_positions": engine_qty,
                "account_equity": summary["equity"],
            }

        book = await step.run("load-book", load_book)
        if book["mismatches"]:
            return {"status": "frozen", "mismatches": book["mismatches"]}

        # Step 4: pure plan
        async def plan_step() -> Dict[str, Any]:
            return build_rebalance_plan(
                pre["outlook"],
                book["engine_positions"],
                book["broker_positions"],
                {
                    "cashBalance": boot["cashBalance"],
                    "status": boot["status"],
                    "accountEquity": book["account_equity"],
                },
            )

        plan = await step.run("build-plan", plan_step)
        if not plan["orders"]:
            return {"status": "no-op", "journal": plan["journal"]}

        # Step 5: one memoized step per order — a retry never re-submits
        fills: List[Dict[str, Any]] = []
        for i, order in enumerate(plan["orders"]):

            async def submit_order(order=order) -> Dict[str, Any]:
                import asyncio  # noqa: PLC0415

                from api.lib.db import get_db  # noqa: PLC0415
                from execution.broker.alpaca_client import client_from_account  # noqa: PLC0415
                from execution.broker.credentials import get_active_alpaca_account  # noqa: PLC0415

                db = await get_db()
                client = client_from_account(await get_active_alpaca_account(db))
                if order["side"] == "sell":
                    result = await asyncio.to_thread(
                        client.submit_market_sell_qty, order["symbol"], order["qty"]
                    )
                else:
                    result = await asyncio.to_thread(
                        client.submit_market_buy_notional, order["symbol"], order["notional"]
                    )
                return {**result.to_dict(), "requested_notional": order.get("notional")}

            fill = await step.run(
                f"order-{i}-{order['side']}-{order['symbol']}", submit_order
            )
            fills.append(fill)

        # Step 6: persist fills + cash ledger (separate from submission —
        # apply_fill dedupes on brokerOrderId, so a partial-failure retry
        # re-applies nothing)
        async def persist() -> Dict[str, Any]:
            from api.lib.db import get_db  # noqa: PLC0415
            from execution.alerts import send_failure_alert  # noqa: PLC0415
            from execution.constants import SLEEVE_B  # noqa: PLC0415
            from execution.sleeve_service import apply_fill, update_sleeve_cash  # noqa: PLC0415

            db = await get_db()
            cash = boot["cashBalance"]
            unfilled = []
            for fill in fills:
                delta = await apply_fill(
                    db, SLEEVE_B, fill,
                    requested_notional=fill.get("requested_notional"),
                    journal=plan["journal"],
                )
                cash += delta
                if fill["status"] != "filled":
                    unfilled.append(f"{fill['side']} {fill['symbol']}: {fill['status']}")
            await update_sleeve_cash(db, SLEEVE_B, cash)
            if unfilled:
                await send_failure_alert(
                    "rebalance had unfilled orders", "\n".join(unfilled),
                    source="execution_weekly",
                )
            return {"cash_after": round(cash, 2), "unfilled": unfilled}

        persisted = await step.run("persist-fills", persist)

        summary = {
            "status": "rebalanced",
            "orders": len(plan["orders"]),
            "unfilled": persisted["unfilled"],
            "cash_after": persisted["cash_after"],
            "regime": pre["outlook"]["regime"],
        }
        logger.info("Sleeve B rebalance complete: %s", summary)
        return summary

    return execution_weekly


try:
    execution_weekly = _register_inngest_function()
except Exception:
    execution_weekly = None  # type: ignore[assignment]
