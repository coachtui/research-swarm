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
from typing import Any, Dict, List, Tuple

from execution.constants import TRAILING_STOP_ATR_MULT

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


def stop_levels(high_water: float, today_close: float, atr: float) -> Tuple[float, float]:
    """ATR trailing stop, ratchets up only. Caller seeds `high_water` from
    the position's stored highWaterClose, falling back to entry price when
    that column is still null (first day after fill)."""
    hw = max(high_water, today_close)
    return hw, round(hw - TRAILING_STOP_ATR_MULT * atr, 2)


async def _persist_position_provenance(db, order: Any) -> None:
    """Copy sourceTags / convictionScore / reportRef from a filled buy's order
    journal onto its EnginePosition row (C1a). The columns were migrated but
    left dead; the weekly theme review needs the persisted sourceTags to flag
    only theme-sourced holdings. Best-effort — never sinks the fills sweep."""
    from execution.constants import SLEEVE_A  # noqa: PLC0415

    try:
        journal = getattr(order, "journal", None) or {}
        if not isinstance(journal, dict):
            return
        data: Dict[str, Any] = {}
        tags = journal.get("sourceTags")
        if isinstance(tags, dict):
            from prisma import Json  # noqa: PLC0415

            data["sourceTags"] = Json(tags)
        conviction = journal.get("convictionScore")
        if conviction is not None:
            data["convictionScore"] = float(conviction)
        report_ref = journal.get("reportRef")
        if report_ref is not None:
            data["reportRef"] = report_ref
        if not data:
            return
        await db.engineposition.update(
            where={"sleeve_symbol": {"sleeve": SLEEVE_A, "symbol": order.symbol}},
            data=data,
        )
    except Exception:  # noqa: BLE001 — provenance is audit, not a gate
        logger.exception("sleeve-a-fills: provenance persist failed for %s",
                         getattr(order, "symbol", "?"))


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

        # Step 3: reconcile — mismatch freezes the sleeve, no snapshot written.
        # Alert + journal only on the active->frozen transition: a sleeve
        # that's already frozen must not re-alert every day (Phase 2 rider).
        #
        # SHARED-ACCOUNT SCOPING (owner ruling 2026-07-10): Sleeve A now holds
        # real stocks in the SAME paper account, so broker["positions"] carries
        # A's names too. Reconcile B against ONLY B's scope — its engine book ∪
        # its sector-ETF universe — so an A stock can never freeze B. (The
        # separate sleeve-a-reconcile step below does the mirror for A.)
        async def reconcile() -> Dict[str, Any]:
            from api.lib.db import get_db  # noqa: PLC0415
            from execution.alerts import send_failure_alert  # noqa: PLC0415
            from execution.constants import SECTOR_ETFS, SLEEVE_B  # noqa: PLC0415
            from execution.engine.reconcile import reconcile_sleeve  # noqa: PLC0415
            from execution.reporting import write_report  # noqa: PLC0415
            from execution.sleeve_service import (  # noqa: PLC0415
                get_sleeve_state, set_sleeve_status,
            )

            broker_qty = {p["symbol"]: p["qty"] for p in broker["positions"]}
            mismatches = reconcile_sleeve(
                broker_qty, context["engine_positions"], SECTOR_ETFS.keys()
            )
            if mismatches:
                db = await get_db()
                state = await get_sleeve_state(db, SLEEVE_B)
                was_frozen = state is not None and state.status == "frozen"
                await set_sleeve_status(db, SLEEVE_B, "frozen", "; ".join(mismatches))
                if not was_frozen:
                    await send_failure_alert(
                        "position reconciliation mismatch — Sleeve B frozen",
                        "\n".join(mismatches),
                        source="execution_daily",
                    )
                    await write_report(
                        "breaker_event", "critical", "execution_daily",
                        "Sleeve B frozen: reconciliation mismatch",
                        {"transition": "active->frozen", "mismatches": mismatches},
                        db=db,
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
            from execution.reporting import write_report  # noqa: PLC0415
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
                await write_report(
                    "breaker_event", "critical", "execution_daily",
                    "Sleeve B circuit breaker tripped",
                    {
                        "transition": "active->halted",
                        "rule": "-15pp vs SPY since inception",
                        "equity": snap["equity"],
                        "inception_equity": context["inception_equity"],
                        "spy_close": snap["spy_close"],
                        "inception_spy": context["inception_spy"],
                    },
                    db=db,
                )
            return {"tripped": tripped}

        breaker = await step.run("circuit-breaker", breaker_check)

        # ── Sleeve A fills FIRST: settle what the engine itself ordered, so
        # the reconcile below compares the broker to a CURRENT book. Settling
        # only ever touches symbols with an EngineTrade row, so it cannot
        # adopt a position it cannot explain (2026-07-28 incident).
        async def sleeve_a_fills_step() -> Dict[str, Any]:
            db = None
            from execution.reporting import write_report  # noqa: PLC0415
            try:
                import asyncio  # noqa: PLC0415

                from api.lib.db import get_db  # noqa: PLC0415
                from execution.broker import sleeve_a_broker  # noqa: PLC0415
                from execution.constants import SLEEVE_A  # noqa: PLC0415
                from execution.market_data import fetch_ohlcv_batch  # noqa: PLC0415
                from execution.sleeve_service import (  # noqa: PLC0415
                    get_sleeve_state, update_sleeve_cash,
                )

                db = await get_db()
                state = await get_sleeve_state(db, SLEEVE_A)
                if state is None:
                    return {"active": False}
                if state.status in ("halted", "frozen"):
                    # Already frozen from a previous pass -> settle nothing new.
                    # This used to gate on the reconcile result, but fills now
                    # run BEFORE it: reconciling against a book that has not
                    # booked today's fills compares the broker to a stale
                    # snapshot and freezes over orders the engine placed itself
                    # (2026-07-28 incident).
                    return {"active": True, "filled": 0, "missed": 0}

                # shadow -> ShadowBrokerClient; live -> AlpacaFunnelBroker.
                broker = await sleeve_a_broker(db, state)
                if broker is None:  # live mode, no linked account (M2)
                    await write_report(
                        "engine_failure", "warning", "execution_daily",
                        "Sleeve A live mode but no linked broker account",
                        {"stage": "sleeve-a-fills"}, db=db,
                    )
                    return {"active": True, "error": True}
                orders = await broker.get_open_orders()
                if not orders:
                    return {"active": True, "filled": 0, "missed": 0}

                symbols = sorted({o.symbol for o in orders})
                ohlcv = await asyncio.to_thread(fetch_ohlcv_batch, symbols, "5d")

                now = datetime.fromisoformat(run_date_iso)
                cash_delta_total = 0.0
                filled = 0
                missed = 0
                for order in orders:
                    df = ohlcv.get(order.symbol)
                    if df is None or df.empty:
                        continue  # no bar today — retry next run
                    today = df.iloc[-1]
                    settled = await broker.settle_open_order(
                        order, day_high=float(today["High"]), day_low=float(today["Low"]),
                        now=now,
                    )
                    if settled["status"] == "filled":
                        filled += 1
                        cash_delta_total += settled["cash_delta"]
                        # Provenance (C1a): copy the buy's sourceTags /
                        # convictionScore / reportRef from the order journal onto
                        # the freshly-settled position row — reviving the dead
                        # migrated columns so the weekly theme review reads
                        # PERSISTED tags. Only for buys (a sell closes the row).
                        if order.side == "buy":
                            await _persist_position_provenance(db, order)
                        await write_report(
                            "entry_filled", "info", "execution_daily",
                            f"Sleeve A fill: {order.symbol}",
                            # ACTUAL fill values from the settle result (M3) —
                            # a live GTC limit can fill below the limit price;
                            # shadow settles at the limit so it's unchanged.
                            {"symbol": order.symbol, "side": order.side,
                             "qty": settled.get("filled_qty", order.qty),
                             "fill_price": settled.get("fill_price", order.limitPrice)},
                            db=db,
                        )
                    elif settled["status"] == "expired":
                        missed += 1
                        await write_report(
                            "entry_missed", "info", "execution_daily",
                            f"Sleeve A order expired unfilled: {order.symbol}",
                            {"symbol": order.symbol, "side": order.side,
                             "qty": order.qty, "limit_price": order.limitPrice},
                            db=db,
                        )
                if cash_delta_total != 0.0:
                    new_cash = float(state.cashBalance) + cash_delta_total
                    if new_cash < 0.0:
                        # Belt-and-suspenders (I3b): a shadow ledger must never
                        # go negative (no leverage). Floor at 0 and make the
                        # overshoot visible — the weekly pass's committed-capital
                        # accounting should already prevent this.
                        await write_report(
                            "engine_failure", "warning", "execution_daily",
                            "Sleeve A cash floored at 0 — fills exceeded ledger",
                            {"stage": "sleeve-a-fills",
                             "would_be_cash": round(new_cash, 2),
                             "cash_delta": round(cash_delta_total, 2)},
                            db=db,
                        )
                        new_cash = 0.0
                    await update_sleeve_cash(db, SLEEVE_A, new_cash)
                return {"active": True, "filled": filled, "missed": missed}
            except Exception:  # noqa: BLE001 — degrade, Sleeve B result must still return
                logger.exception("sleeve-a-fills failed")
                await write_report(
                    "engine_failure", "warning", "execution_daily",
                    "Sleeve A fills sweep failed", {"stage": "sleeve-a-fills"}, db=db,
                )
                # active=True: a fills failure must NOT cascade — stops,
                # snapshot and breaker still run (only sleeve-absent skips).
                return {"active": True, "error": True}

        fills = await step.run("sleeve-a-fills", sleeve_a_fills_step)

        # ── Sleeve A reconcile (shared-account mirror of Step 3 for B) ──
        # The broker snapshot now carries Sleeve A's real stocks too. Reconcile
        # A against ONLY A's engine book (no expected universe — A holds no
        # fixed instrument set), so a Sleeve B ETF can never freeze A and an
        # A-side mismatch freezes A ONLY. On the active->frozen transition,
        # alert + journal once (Phase 2 re-alert rider); a frozen A halts its
        # own new trading below but still snapshots for visibility.
        async def sleeve_a_reconcile_step() -> Dict[str, Any]:
            db = None
            from execution.reporting import write_report  # noqa: PLC0415
            try:
                from api.lib.db import get_db  # noqa: PLC0415
                from execution.alerts import send_failure_alert  # noqa: PLC0415
                from execution.constants import SECTOR_ETFS, SLEEVE_A  # noqa: PLC0415
                from execution.engine.reconcile import reconcile_sleeve  # noqa: PLC0415
                from execution.sleeve_service import (  # noqa: PLC0415
                    get_engine_positions, get_sleeve_state, set_sleeve_status,
                )

                db = await get_db()
                state = await get_sleeve_state(db, SLEEVE_A)
                engine_qty = {
                    p.symbol: p.qty for p in await get_engine_positions(db, SLEEVE_A)
                }
                broker_qty = {p["symbol"]: p["qty"] for p in broker["positions"]}

                # Visibility check (I2): per-sleeve scoping means a broker
                # symbol claimed by NEITHER sleeve — not in either engine book,
                # not a sector ETF — is invisible to both reconciles. Journal
                # it loudly (a human must explain it) but freeze NOBODY: an
                # unexplained extra can't corrupt either sleeve's own books.
                claimed = (
                    set(engine_qty) | set(context["engine_positions"]) | set(SECTOR_ETFS)
                )
                unclaimed = sorted(s for s in broker_qty if s not in claimed)
                if unclaimed:
                    await write_report(
                        "engine_failure", "warning", "execution_daily",
                        f"unclaimed broker positions: {unclaimed}",
                        {"stage": "sleeve-a-reconcile", "unclaimed": unclaimed},
                        db=db,
                    )
                extra = {"unclaimed": unclaimed} if unclaimed else {}

                if state is None:
                    return {"active": False, "frozen": False, **extra}
                mismatches = reconcile_sleeve(broker_qty, engine_qty)
                if mismatches:
                    was_frozen = state.status == "frozen"
                    await set_sleeve_status(db, SLEEVE_A, "frozen", "; ".join(mismatches))
                    if not was_frozen:
                        await send_failure_alert(
                            "position reconciliation mismatch — Sleeve A frozen",
                            "\n".join(mismatches),
                            source="execution_daily",
                        )
                        await write_report(
                            "breaker_event", "critical", "execution_daily",
                            "Sleeve A frozen: reconciliation mismatch",
                            {"transition": "active->frozen", "mismatches": mismatches},
                            db=db,
                        )
                    return {"active": True, "frozen": True,
                            "mismatches": mismatches, **extra}
                return {"active": True, "frozen": False, **extra}
            except Exception:  # noqa: BLE001 — degrade, Sleeve B result must still return
                logger.exception("sleeve-a-reconcile failed")
                await write_report(
                    "engine_failure", "warning", "execution_daily",
                    "Sleeve A reconcile failed", {"stage": "sleeve-a-reconcile"}, db=db,
                )
                # Its own failure must not block A's other duties (mirror the
                # fills-step degrade contract): treat as not-frozen.
                return {"active": True, "frozen": False, "error": True}

        a_recon = await step.run("sleeve-a-reconcile", sleeve_a_reconcile_step)

        # ── Sleeve A: shadow fills, ATR trailing stops, snapshot + breaker ──
        # No-op entirely when SleeveState A doesn't exist yet (the weekly
        # funnel hasn't bootstrapped it). That existence check happens ONCE,
        # in sleeve-a-fills; the later three steps trust the `active` flag
        # it returns rather than re-querying. `active` means "downstream
        # Sleeve A steps should run": it is False ONLY for sleeve-absent —
        # a fills-step FAILURE returns active=True so a transient fills
        # error never cascades into skipped stops/snapshot/breaker (each is
        # harmless against an actually-absent sleeve: stops sees no
        # positions, snapshot re-checks state itself). Each step is
        # independently try/except-wrapped and journals `engine_failure` on
        # its own failure — Sleeve B's result above is already computed and
        # must reach the caller even if every Sleeve A duty below blows up.
        #
        # Cash semantics: this fills step is the SOLE cash mover for shadow
        # buys. The weekly funnel reserves NOTHING at submit (it instead
        # subtracts open-order notionals from its spendable envelope), so a
        # fill deducts exactly once here and an expiry deducts nothing —
        # there is no reservation to refund.


        async def sleeve_a_stops_step() -> Dict[str, Any]:
            if not fills["active"]:
                return {"active": False}
            db = None
            from execution.reporting import write_report  # noqa: PLC0415
            try:
                import asyncio  # noqa: PLC0415

                from api.lib.db import get_db  # noqa: PLC0415
                from execution.broker import sleeve_a_broker  # noqa: PLC0415
                from execution.constants import SLEEVE_A  # noqa: PLC0415
                from execution.funnel.screen import compute_atr  # noqa: PLC0415
                from execution.market_data import fetch_ohlcv_batch  # noqa: PLC0415
                from execution.sleeve_service import (  # noqa: PLC0415
                    get_engine_positions, get_sleeve_state,
                )

                db = await get_db()
                if a_recon.get("frozen"):
                    # reconciliation mismatch this morning -> no new exits.
                    return {"active": True, "exits": 0}
                positions = await get_engine_positions(db, SLEEVE_A)
                if not positions:
                    return {"active": True, "exits": 0}

                symbols = sorted({p.symbol for p in positions})
                ohlcv = await asyncio.to_thread(fetch_ohlcv_batch, symbols)

                # shadow -> ShadowBrokerClient; live -> AlpacaFunnelBroker.
                state = await get_sleeve_state(db, SLEEVE_A)
                broker = await sleeve_a_broker(db, state)
                if broker is None:  # live mode, no linked account (M2)
                    await write_report(
                        "engine_failure", "warning", "execution_daily",
                        "Sleeve A live mode but no linked broker account",
                        {"stage": "sleeve-a-stops"}, db=db,
                    )
                    return {"active": False, "error": True}
                for pos in positions:
                    df = ohlcv.get(pos.symbol)
                    if df is None or len(df) < 15:  # need 15 rows for ATR(14)
                        continue  # not enough bars today — retry next run
                    atr = compute_atr(df)
                    if atr is None:
                        continue
                    today = df.iloc[-1]
                    today_close = float(today["Close"])
                    hw_in = (
                        pos.highWaterClose if pos.highWaterClose is not None
                        else pos.avgEntryPrice
                    )
                    new_hw, _stop = stop_levels(hw_in, today_close, atr)
                    await db.engineposition.update(
                        where={"sleeve_symbol": {"sleeve": SLEEVE_A, "symbol": pos.symbol}},
                        data={"highWaterClose": new_hw, "stopPrice": None},
                    )
                    # Thesis-hold (spec 2026-07-10): price levels never sell.
                    # The high-water ratchet stays — it anchors the DCA ladder.
                return {"active": True, "exits": 0}
            except Exception:  # noqa: BLE001 — degrade, Sleeve B result must still return
                logger.exception("sleeve-a-stops failed")
                await write_report(
                    "engine_failure", "warning", "execution_daily",
                    "Sleeve A trailing stop sweep failed", {"stage": "sleeve-a-stops"}, db=db,
                )
                return {"active": False, "error": True}

        stops = await step.run("sleeve-a-stops", sleeve_a_stops_step)

        async def sleeve_a_snapshot_step() -> Dict[str, Any]:
            if not fills["active"]:
                return {"active": False}
            db = None
            from execution.reporting import write_report  # noqa: PLC0415
            try:
                import asyncio  # noqa: PLC0415

                from api.lib.db import get_db  # noqa: PLC0415
                from execution.constants import SLEEVE_A  # noqa: PLC0415
                from execution.market_data import fetch_ohlcv_batch  # noqa: PLC0415
                from execution.sleeve_service import (  # noqa: PLC0415
                    get_engine_positions, get_sleeve_state, store_snapshot,
                )

                db = await get_db()
                state = await get_sleeve_state(db, SLEEVE_A)
                if state is None:
                    return {"active": False}
                positions = await get_engine_positions(db, SLEEVE_A)
                symbols = sorted({p.symbol for p in positions})
                ohlcv = await asyncio.to_thread(fetch_ohlcv_batch, symbols) if symbols else {}

                # A missing bar must SKIP the snapshot, not zero the holding:
                # valuing a held position at 0 understates equity and could
                # falsely trip the -15pp breaker. No snapshot today -> the
                # breaker step below no-ops (it gates on this step).
                missing = [
                    s for s in symbols
                    if s not in ohlcv or ohlcv[s] is None or ohlcv[s].empty
                ]
                if missing:
                    await write_report(
                        "engine_failure", "warning", "execution_daily",
                        f"Sleeve A snapshot skipped — missing bars: {missing}",
                        {"stage": "sleeve-a-snapshot", "missing": missing},
                        db=db,
                    )
                    return {"active": False, "skipped": True, "missing": missing}

                positions_value = 0.0
                for p in positions:
                    positions_value += p.qty * float(ohlcv[p.symbol]["Close"].iloc[-1])

                cash = float(state.cashBalance)
                equity = round(cash + positions_value, 2)
                run_date = datetime.fromisoformat(run_date_iso)
                snapshot_date = run_date.replace(hour=0, minute=0, second=0, microsecond=0)
                # Same SPY close the Sleeve B snapshot above already fetched —
                # both sleeves benchmark against literally the same number.
                await store_snapshot(
                    db, SLEEVE_A, snapshot_date, equity=equity, cash=cash,
                    positions_value=round(positions_value, 2), spy_close=snap["spy_close"],
                )
                return {
                    "active": True, "equity": equity, "spy_close": snap["spy_close"],
                    "inception_equity": state.inceptionEquity,
                    "inception_spy": state.inceptionSpyClose, "status": state.status,
                }
            except Exception:  # noqa: BLE001 — degrade, Sleeve B result must still return
                logger.exception("sleeve-a-snapshot failed")
                await write_report(
                    "engine_failure", "warning", "execution_daily",
                    "Sleeve A snapshot failed", {"stage": "sleeve-a-snapshot"}, db=db,
                )
                return {"active": False, "error": True}

        a_snap = await step.run("sleeve-a-snapshot", sleeve_a_snapshot_step)

        async def sleeve_a_breaker_step() -> Dict[str, Any]:
            if not a_snap.get("active"):
                return {"active": False}
            db = None
            from execution.reporting import write_report  # noqa: PLC0415
            try:
                from api.lib.db import get_db  # noqa: PLC0415
                from execution.constants import SLEEVE_A  # noqa: PLC0415
                from execution.engine.circuit_breaker import circuit_breaker_tripped  # noqa: PLC0415
                from execution.sleeve_service import set_sleeve_status  # noqa: PLC0415

                tripped = circuit_breaker_tripped(
                    a_snap["equity"], a_snap["inception_equity"],
                    a_snap["spy_close"], a_snap["inception_spy"],
                )
                if tripped and a_snap["status"] == "active":
                    db = await get_db()
                    await set_sleeve_status(
                        db, SLEEVE_A, "halted",
                        "circuit breaker: -15pp vs SPY since inception",
                    )
                    await write_report(
                        "breaker_event", "critical", "execution_daily",
                        "Sleeve A circuit breaker tripped",
                        {
                            "transition": "active->halted",
                            "rule": "-15pp vs SPY since inception",
                            "equity": a_snap["equity"],
                            "inception_equity": a_snap["inception_equity"],
                            "spy_close": a_snap["spy_close"],
                            "inception_spy": a_snap["inception_spy"],
                        },
                        db=db,
                    )
                return {"active": True, "tripped": tripped}
            except Exception:  # noqa: BLE001 — degrade, Sleeve B result must still return
                logger.exception("sleeve-a-breaker failed")
                await write_report(
                    "engine_failure", "warning", "execution_daily",
                    "Sleeve A breaker check failed", {"stage": "sleeve-a-breaker"}, db=db,
                )
                return {"active": False, "error": True}

        a_breaker = await step.run("sleeve-a-breaker", sleeve_a_breaker_step)

        return {
            "status": "ok", "equity": snap["equity"], "breaker_tripped": breaker["tripped"],
            "sleeve_a": {
                "active": fills["active"], "reconcile": a_recon, "fills": fills,
                "stops": stops, "snapshot": a_snap, "breaker": a_breaker,
            },
        }

    return execution_daily


try:
    execution_daily = _register_inngest_function()
except Exception:
    execution_daily = None  # type: ignore[assignment]
