"""
Sleeve A funnel — the weekly shadow pass (Autopilot Phase 3C).

Cron: Monday 16:00 UTC. Bottom-up, single-name sleeve running in SHADOW mode
(EngineTrade rows via ShadowBrokerClient; nothing touches Alpaca until 3D).
This is the conductor: every prior 3C task is a section of the orchestra and
this module only wires them together and owns the journal.

Failure posture (spec §11): the cron NEVER raises. Every step body catches,
journals `engine_failure`, and degrades — a broken section skips, the pass
goes on, and the run always ends with one `funnel_summary` row. The bare
research_budget primitives (reuse_or_budget / run_paid_analysis / persist_full)
have no internal try/except BY DESIGN, so every closure here wraps them.

The PAID analyze call lives in its OWN memoized step, separate from persist —
a persist retry must never re-bill (the $3.50 lesson from weekly_batch). When
`step` is None (unit tests / non-Inngest callers) the analyze path runs inline.

Step results are JSON-serializable and never carry decrypted broker secrets —
any step needing the broker rebuilds the client inside the step.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from execution.constants import (
    BENCHMARK,
    FULL_RUNS_PER_WEEK,
    LIGHT_RUNS_PER_WEEK,
    MIN_TRADE_NOTIONAL,
    OUTLOOK_MAX_AGE_DAYS,
    REGIME_INVESTED_FRACTION,
    RETIRED_THEME_EXIT_CONVICTION,
    SLEEVE_A,
    SLEEVE_A_FRACTION,
    SLEEVE_A_MAX_POSITIONS,
    SLEEVE_B,
)
from execution.engine.guardrails import enforce_funnel_guardrails
from execution.funnel.conviction import compute_conviction
from execution.funnel.decisions import plan_decisions
from execution.funnel.entries import (
    entry_limit_price, entry_ttl_days, extension_state, size_entry,
)
from execution.funnel.research_budget import (
    persist_full, reuse_or_budget, run_paid_analysis,
)
from execution.outlook_service import get_latest_outlook
from execution.reporting import write_report

logger = logging.getLogger(__name__)

_SOURCE = "sleeve_a_funnel"
_QUALITY_RERANK_TOP_N = 40


# ── Journal helper ───────────────────────────────────────────────────────────

async def _journal(
    db, report_type: str, severity: str, title: str, body: Dict[str, Any],
) -> None:
    """Thin wrapper over write_report (which itself never raises)."""
    await write_report(report_type, severity, _SOURCE, title, body, db=db)


async def _run_step(step, step_id: str, fn):
    """Run fn as a memoized Inngest step, or inline when step is None (tests /
    non-Inngest callers). Only for closures that DON'T themselves call
    step.run — nested steps are a non-retriable SDK error."""
    if step is None:
        return await fn()
    return await step.run(step_id, fn)


# ── Conviction input mappers ─────────────────────────────────────────────────

def _fv_gap_pct(fair_value: Optional[float], price: Optional[float]) -> Optional[float]:
    if fair_value is None or not price:
        return None
    try:
        return round((float(fair_value) - float(price)) / float(price) * 100, 2)
    except (TypeError, ZeroDivisionError):
        return None


def _conviction_input_from_signals(
    signals: Dict[str, Any], screen: Dict[str, Any], report_age_days: float = 0.0,
) -> Dict[str, Any]:
    """Full-signal (manager) shape → compute_conviction input. Full signals use
    the extract_signals_from_result camelCase keys; screen supplies momentum,
    hunting and market cap the manager doesn't carry."""
    fv_gap = signals.get("fair_value_gap_pct")
    if fv_gap is None:
        fv_gap = _fv_gap_pct(signals.get("fairValue"), screen.get("price"))
    return {
        "verdict": signals.get("verdict"),
        "fair_value_gap_pct": fv_gap,
        "insider_score": signals.get("insiderScore"),
        "dark_pool_score": signals.get("darkPoolScore"),
        "sentiment_score": signals.get("sentimentScore"),
        "valuation_score": signals.get("valuation_score"),
        "financial_health": signals.get("financial_health"),
        "earnings_momentum": signals.get("earnings_momentum"),
        "short_pct_float": signals.get("short_pct_float"),
        "momentum": screen.get("momentum"),
        "hunting_bonus": screen.get("hunting_bonus"),
        "market_cap": screen.get("market_cap") or signals.get("market_cap"),
        "report_age_days": report_age_days,
    }


def _conviction_input_from_light(
    light: Dict[str, Any], screen: Dict[str, Any],
    report_age_days: float = 0.0, hunting_bonus: Optional[float] = None,
) -> Dict[str, Any]:
    """Light-run (numbers-only, snake_case) shape → compute_conviction input."""
    return {
        "verdict": None,  # the light runner never assigns a verdict
        "fair_value_gap_pct": light.get("fair_value_gap_pct"),
        "insider_score": light.get("insider_score"),
        "dark_pool_score": light.get("dark_pool_score"),
        "sentiment_score": light.get("sentiment_score"),
        "valuation_score": light.get("valuation_score"),
        "short_pct_float": light.get("short_pct_float"),
        "momentum": screen.get("momentum"),
        "hunting_bonus": screen.get("hunting_bonus") if hunting_bonus is None else hunting_bonus,
        "market_cap": light.get("market_cap") or screen.get("market_cap"),
        "report_age_days": report_age_days,
    }


# ── Step helpers (unit-tested directly with step=None) ───────────────────────

async def _load_and_gate_outlook(db, now: datetime) -> Optional[Any]:
    """Latest MarketOutlook, or None (journalled) when it is missing or stale.
    Stale/absent outlook skips the ENTIRE pass — the funnel refuses to trade on
    a regime read older than OUTLOOK_MAX_AGE_DAYS."""
    try:
        outlook = await get_latest_outlook(db)
    except Exception:  # noqa: BLE001 — degrade, never raise
        logger.exception("funnel: outlook load failed")
        await _journal(
            db, "engine_failure", "critical",
            "Funnel skipped: outlook load failed", {"stage": "load-outlook"},
        )
        return None

    if outlook is None:
        await _journal(
            db, "engine_failure", "warning",
            "Funnel skipped: no MarketOutlook row", {"stage": "load-outlook"},
        )
        return None

    run_date = outlook.runDate
    if run_date.tzinfo is None:
        run_date = run_date.replace(tzinfo=timezone.utc)
    age = now - run_date
    if age > timedelta(days=OUTLOOK_MAX_AGE_DAYS):
        await _journal(
            db, "engine_failure", "warning",
            "Funnel skipped: outlook stale",
            {
                "stage": "load-outlook",
                "outlook_run_date": run_date.isoformat(),
                "age_days": round(age.total_seconds() / 86400, 2),
                "max_age_days": OUTLOOK_MAX_AGE_DAYS,
            },
        )
        return None
    return outlook


async def _ensure_sleeve_a(db, now: datetime) -> Optional[Dict[str, Any]]:
    """Load Sleeve A state; bootstrap it on the first run. Cash seeds at
    SLEEVE_A_FRACTION × broker account equity, inception SPY = previous close.
    Halted/frozen only blocks buys (allow_buys=False) — the pass still runs.
    Returns a JSON-safe context dict, or None if there is no linked account."""
    from execution.broker.alpaca_client import client_from_account  # noqa: PLC0415
    from execution.broker.credentials import get_active_alpaca_account  # noqa: PLC0415
    from execution.sleeve_service import (  # noqa: PLC0415
        get_engine_positions, get_sleeve_state, init_sleeve_state,
    )

    state = await get_sleeve_state(db, SLEEVE_A)
    if state is None:
        account = await get_active_alpaca_account(db)
        if account is None:
            await _journal(
                db, "engine_failure", "warning",
                "Funnel skipped: no linked broker account to seed Sleeve A",
                {"stage": "ensure-sleeve-a"},
            )
            return None
        import asyncio  # noqa: PLC0415

        client = client_from_account(account)
        summary = await asyncio.to_thread(client.get_account_summary)
        seed_cash = SLEEVE_A_FRACTION * float(summary["equity"])
        prev_spy = await _previous_spy_close()
        state = await init_sleeve_state(
            db, SLEEVE_A, cash=seed_cash, spy_close=prev_spy,
            inception_date=now, mode="shadow",
        )
        await _journal(
            db, "funnel_summary", "info",
            "Sleeve A bootstrapped (shadow)",
            {"seed_cash": round(seed_cash, 2), "inception_spy": prev_spy},
        )

    positions = await get_engine_positions(db, SLEEVE_A)
    allow_buys = state.status not in ("halted", "frozen")
    return {
        "cash": float(state.cashBalance),
        "status": state.status,
        "allow_buys": allow_buys,
        "positions": {p.symbol: float(p.qty) for p in positions},
    }


async def _previous_spy_close() -> float:
    import asyncio  # noqa: PLC0415

    from execution.market_data import fetch_history_for  # noqa: PLC0415

    def _load() -> float:
        series = fetch_history_for([BENCHMARK], period="1mo").get(BENCHMARK)
        if series is None or len(series) < 2:
            return 0.0
        return float(series.dropna().iloc[-2])  # previous close, not today's

    return await asyncio.to_thread(_load)


async def _handshake_and_enter(
    db, client, entry_queue: List[str],
    candidates_by_symbol: Dict[str, Dict[str, Any]], run_date: datetime,
    sleeve_equity: float, deployable: float, cash_available: float,
    holdings: List[Dict[str, Any]], sector_by_symbol: Dict[str, str],
    other_sleeve_sector_notional: Dict[str, float], allow_buys: bool, step,
) -> List[Dict[str, Any]]:
    """Entry handshake + placement, one symbol at a time.

    For each queued entry: budget-gate (reuse fresh / paid analyze / skip),
    re-score conviction with the FULL signals, veto on SELL, size, filter
    through the funnel guardrails, and submit a shadow limit buy. The paid
    analyze runs in its own memoized step (or inline when step is None) so a
    persist retry can never re-bill. Returns the placed-order dicts.

    `deployable` and `cash_available` shrink as orders are placed so the queue
    cannot collectively overspend the regime-scaled envelope or the cash ledger.
    """
    placed: List[Dict[str, Any]] = []
    deployable_remaining = float(deployable)
    cash_remaining = float(cash_available)

    for sym in entry_queue:
        cand = candidates_by_symbol.get(sym) or {}
        screen = cand.get("screen") or {}

        # 1) Budget-aware handshake gate (reuse_or_budget is bare — wrap it).
        try:
            gate = await reuse_or_budget(db, sym, run_date)
        except Exception:  # noqa: BLE001
            logger.exception("funnel handshake: gate failed for %s", sym)
            await _journal(db, "engine_failure", "warning",
                           f"{sym}: handshake gate failed", {"symbol": sym})
            continue

        action = gate.get("action")
        if action == "skip":
            await _journal(db, "entry_deferred", "info",
                           f"{sym}: entry deferred — {gate.get('reason', 'budget')}",
                           {"symbol": sym, "reason": gate.get("reason"),
                            "budget": FULL_RUNS_PER_WEEK})
            continue

        signals: Optional[Dict[str, Any]] = None
        if action == "reuse":
            signals = gate.get("signals")
        else:  # action == "analyze": PAID — its OWN step, persist separate.
            try:
                if step is not None:
                    result = await step.run(
                        f"handshake-analyze-{sym.lower()}",
                        lambda s=sym: run_paid_analysis(s),
                    )
                else:
                    result = await run_paid_analysis(sym)
            except Exception:  # noqa: BLE001
                logger.exception("funnel handshake: paid analysis failed for %s", sym)
                await _journal(db, "engine_failure", "warning",
                               f"{sym}: paid analysis failed", {"symbol": sym})
                continue
            try:
                persisted = await persist_full(
                    db, sym, run_date, result,
                    float(screen.get("price") or 0.0),
                    float(screen.get("screen_score") or 0.0),
                )
            except Exception:  # noqa: BLE001
                logger.exception("funnel handshake: persist failed for %s", sym)
                await _journal(db, "engine_failure", "warning",
                               f"{sym}: research persist failed", {"symbol": sym})
                continue
            if persisted.get("status") != "upgraded" or persisted.get("signals") is None:
                await _journal(db, "entry_deferred", "info",
                               f"{sym}: analysis unusable — no entry",
                               {"symbol": sym, "status": persisted.get("status")})
                continue
            signals = persisted["signals"]

        if signals is None:
            await _journal(db, "entry_deferred", "info",
                           f"{sym}: no usable signals — no entry", {"symbol": sym})
            continue

        # 2) Re-score conviction on the FULL signals; SELL is a veto.
        conv = compute_conviction(_conviction_input_from_signals(signals, screen))
        if conv.get("vetoed"):
            await _journal(db, "exit_sell_verdict", "info",
                           f"{sym}: entry vetoed — {conv.get('veto_reason')}",
                           {"symbol": sym, "veto_reason": conv.get("veto_reason")})
            continue
        conviction = float(conv["score"])

        # 3) Size the entry (extension-aware limit, conviction-scaled notional).
        try:
            price = float(screen["price"])
            sma20 = float(screen["sma20"])
            atr = float(screen["atr"])
            atr_pct = float(screen["atr_pct"])
            ext_atr = float(screen.get("ext_atr") or 0.0)
        except (KeyError, TypeError, ValueError):
            await _journal(db, "engine_failure", "warning",
                           f"{sym}: screen row incomplete — cannot size",
                           {"symbol": sym})
            continue

        state = extension_state(ext_atr)
        limit = entry_limit_price(state, price, sma20, atr)
        ttl = entry_ttl_days(state)
        notional = size_entry(
            conviction, sleeve_equity,
            float(screen.get("liquidity_adv_usd") or 0.0), atr_pct,
            deployable_remaining, cash_remaining,
        )
        if notional < MIN_TRADE_NOTIONAL or limit <= 0:
            await _journal(db, "entry_deferred", "info",
                           f"{sym}: below minimum notional after sizing",
                           {"symbol": sym, "notional": notional, "conviction": conviction})
            continue

        # 4) Guardrails (theme overlap → cross-sleeve sector → cash).
        order = {
            "symbol": sym, "side": "buy", "notional": notional,
            "tags": screen.get("tags") or {}, "sector": sector_by_symbol.get(sym),
        }
        adjusted, notes = enforce_funnel_guardrails(
            [order], sleeve_equity, sleeve_equity, cash_remaining,
            holdings, other_sleeve_sector_notional, allow_buys,
        )
        buys = [o for o in adjusted if o["side"] == "buy"]
        if not buys:
            await _journal(db, "entry_deferred", "info",
                           f"{sym}: buy blocked by guardrails",
                           {"symbol": sym, "notes": notes})
            continue

        # 5) Submit the shadow limit buy (deterministic client_order_id).
        for o in buys:
            final_notional = float(o["notional"])
            qty = round(final_notional / limit, 4)
            expires_at = run_date + timedelta(days=ttl)
            coid = f"shadow-A-{sym}-{run_date:%Y%m%d}"
            journal = {
                "symbol": sym, "conviction": conviction, "limit_price": limit,
                "notional": final_notional, "extension_state": state,
                "ttl_days": ttl, "guardrail_notes": notes,
            }
            try:
                await client.submit_limit_buy(
                    symbol=sym, qty=qty, limit_price=limit, expires_at=expires_at,
                    journal=journal, client_order_id=coid,
                )
            except Exception:  # noqa: BLE001
                logger.exception("funnel: shadow buy submit failed for %s", sym)
                await _journal(db, "engine_failure", "warning",
                               f"{sym}: shadow buy submit failed", {"symbol": sym})
                continue
            await _journal(db, "entry_order", "info",
                           f"{sym}: shadow buy {qty} @ {limit}", journal)
            placed.append({
                "symbol": sym, "qty": qty, "limit_price": limit,
                "notional": final_notional, "client_order_id": coid,
                "expires_at": expires_at.isoformat(),
            })
            deployable_remaining = max(0.0, deployable_remaining - final_notional)
            cash_remaining = max(0.0, cash_remaining - final_notional)

    return placed


async def _execute_sells(
    db, client, decisions: Dict[str, Any],
    close_by_symbol: Dict[str, float], positions: Dict[str, float],
    run_date: datetime, sleeve_cash: float,
) -> Dict[str, Any]:
    """Shadow-sell every exit (full) and trim (partial) at last close, journal
    each, and return the resulting cash balance. update_sleeve_cash is owned
    here (the cron), not in the pure planner."""
    from execution.sleeve_service import update_sleeve_cash  # noqa: PLC0415

    cash = float(sleeve_cash)
    proceeds = 0.0
    sold: List[str] = []
    _EXIT_REPORT = {
        "sell_verdict": "exit_sell_verdict",
        "theme_review_failed": "exit_sell_verdict",
        "outcompeted": "exit_outcompeted",
    }

    for ex in decisions.get("exits", []):
        sym = ex["symbol"]
        qty = positions.get(sym)
        close = close_by_symbol.get(sym)
        if not qty or close is None or close <= 0:
            await _journal(db, "engine_failure", "warning",
                           f"{sym}: cannot shadow-sell exit — missing qty/close",
                           {"symbol": sym, "reason": ex.get("reason")})
            continue
        coid = f"shadow-A-{sym}-{run_date:%Y%m%d}-sell"
        try:
            await client.submit_shadow_sell(
                symbol=sym, qty=qty, fill_price=close,
                journal={"reason": ex.get("reason")}, client_order_id=coid,
            )
        except Exception:  # noqa: BLE001
            logger.exception("funnel: exit sell failed for %s", sym)
            await _journal(db, "engine_failure", "warning",
                           f"{sym}: exit shadow-sell failed", {"symbol": sym})
            continue
        proceeds += qty * close
        cash += qty * close
        sold.append(sym)
        await _journal(db, _EXIT_REPORT.get(ex.get("reason"), "exit_sell_verdict"),
                       "info", f"{sym}: exit ({ex.get('reason')})",
                       {"symbol": sym, "qty": qty, "fill_price": close,
                        "reason": ex.get("reason")})

    for tr in decisions.get("trims", []):
        sym = tr["symbol"]
        close = close_by_symbol.get(sym)
        sell_notional = float(tr.get("sell_notional") or 0.0)
        if close is None or close <= 0 or sell_notional < MIN_TRADE_NOTIONAL:
            continue
        qty = round(sell_notional / close, 4)
        coid = f"shadow-A-{sym}-{run_date:%Y%m%d}-sell"
        try:
            await client.submit_shadow_sell(
                symbol=sym, qty=qty, fill_price=close,
                journal={"reason": "risk_trim"}, client_order_id=coid,
            )
        except Exception:  # noqa: BLE001
            logger.exception("funnel: risk trim failed for %s", sym)
            await _journal(db, "engine_failure", "warning",
                           f"{sym}: risk-trim shadow-sell failed", {"symbol": sym})
            continue
        proceeds += qty * close
        cash += qty * close
        await _journal(db, "risk_trim", "info", f"{sym}: risk trim",
                       {"symbol": sym, "qty": qty, "fill_price": close,
                        "sell_notional": sell_notional})

    try:
        await update_sleeve_cash(db, SLEEVE_A, cash)
    except Exception:  # noqa: BLE001
        logger.exception("funnel: update_sleeve_cash failed")
        await _journal(db, "engine_failure", "warning",
                       "Sleeve A cash update failed", {"cash": cash})

    return {"cash": round(cash, 2), "proceeds": round(proceeds, 2), "sold": sold}


# ── Inngest function (guarded registration, execution_daily.py pattern) ──────

def _register_inngest_function():
    import inngest as inngest_sdk  # noqa: PLC0415 — pip SDK

    from inngest_app.client import inngest_client  # noqa: PLC0415

    if inngest_client is None:
        raise RuntimeError("inngest pip SDK not available — client is None")

    async def _on_failure(ctx: "inngest_sdk.Context") -> None:
        from api.lib.db import get_db  # noqa: PLC0415

        db = await get_db()
        await write_report(
            "engine_failure", "critical", _SOURCE,
            "sleeve-a-funnel cron failed after retries",
            {"event": str(ctx.event.data)}, db=db,
        )

    @inngest_client.create_function(
        fn_id="sleeve-a-funnel",
        trigger=inngest_sdk.TriggerCron(cron="0 16 * * 1"),  # Mondays 16:00 UTC
        name="Autopilot Sleeve A Funnel (Shadow)",
        retries=1,
        on_failure=_on_failure,
    )
    async def sleeve_a_funnel(ctx: "inngest_sdk.Context") -> Dict[str, Any]:
        import asyncio  # noqa: PLC0415

        from api.lib.db import get_db  # noqa: PLC0415

        step = ctx.step

        # run-date: Monday 00:00 UTC, captured once (replay-safe).
        run_date_iso: str = await step.run(
            "run-date",
            lambda: datetime.now(timezone.utc)
            .replace(hour=0, minute=0, second=0, microsecond=0)
            .isoformat(),
        )
        run_date = datetime.fromisoformat(run_date_iso)
        now = datetime.now(timezone.utc)
        summary: Dict[str, Any] = {"run_date": run_date_iso}

        # load-outlook — stale/absent ⇒ END the pass.
        async def load_outlook_step() -> Optional[Dict[str, Any]]:
            db = await get_db()
            outlook = await _load_and_gate_outlook(db, now)
            if outlook is None:
                return None
            return {"regime": outlook.regime,
                    "industryRankings": outlook.industryRankings or [],
                    "themeRankings": outlook.themeRankings or []}

        outlook = await step.run("load-outlook", load_outlook_step)
        if outlook is None:
            return {"status": "skipped", "reason": "outlook_missing_or_stale"}
        regime = outlook["regime"]

        # ensure-sleeve-a — bootstrap on first run; state gates buys only.
        async def ensure_sleeve_step() -> Optional[Dict[str, Any]]:
            db = await get_db()
            try:
                return await _ensure_sleeve_a(db, run_date)
            except Exception:  # noqa: BLE001 — bootstrap failure skips the pass
                logger.exception("funnel: ensure-sleeve-a failed")
                await _journal(db, "engine_failure", "warning",
                               "Sleeve A bootstrap failed", {"stage": "ensure-sleeve-a"})
                return None

        sleeve_ctx = await step.run("ensure-sleeve-a", ensure_sleeve_step)
        if sleeve_ctx is None:
            return {"status": "skipped", "reason": "no_linked_account"}

        # assemble-universe → screen → light-runs → conviction table.
        async def assemble_step() -> Dict[str, Any]:
            db = await get_db()
            try:
                return await _assemble(db, outlook, list(sleeve_ctx["positions"]))
            except Exception:  # noqa: BLE001
                logger.exception("funnel: universe assembly failed")
                await _journal(db, "engine_failure", "warning",
                               "Universe assembly failed", {"stage": "assemble"})
                return {"tagged": {}, "excluded": [], "counts": {}}

        assembled = await step.run("assemble-universe", assemble_step)

        async def screen_step() -> Dict[str, Any]:
            db = await get_db()
            try:
                return await _screen(assembled, outlook, sleeve_ctx)
            except Exception:  # noqa: BLE001
                logger.exception("funnel: screen failed")
                await _journal(db, "engine_failure", "warning",
                               "Screen failed", {"stage": "screen"})
                return {"ranked": [], "slots": {"light": [], "free_ride": [],
                                                "over_budget": []},
                        "close_by_symbol": {}, "sector_by_symbol": {}}

        screened = await step.run("screen", screen_step)

        # light-runs — ONE memoized step; per-name guards inside.
        async def light_step() -> Dict[str, Any]:
            db = await get_db()
            return await _run_lights(db, run_date, screened)

        lights = await step.run("light-runs", light_step)

        # conviction-table + theme-review + decisions + sells + entries.
        # Run at the TOP LEVEL of the function (NOT inside a step.run): the
        # per-symbol paid analyze steps live in here, and step.run nested
        # inside another step.run is a non-retriable SDK error (the same rule
        # weekly_batch's swarm loop obeys). Idempotent shadow writes
        # (brokerOrderId dedup) make a coordinator re-run safe. Wrapped so a
        # failure here can never sink the funnel_summary row below.
        outcome: Dict[str, Any] = {}
        try:
            db = await get_db()
            from execution.broker.shadow_client import ShadowBrokerClient  # noqa: PLC0415

            client = ShadowBrokerClient(db, sleeve=SLEEVE_A)
            outcome = await _decide_and_execute(
                db, client, run_date, regime, sleeve_ctx, assembled,
                screened, lights, step,
            )
        except Exception:  # noqa: BLE001 — degrade; summary must still write
            logger.exception("funnel: decide-and-execute failed")
            db = await get_db()
            await _journal(db, "engine_failure", "warning",
                           "Decide/execute stage failed", {"stage": "decide-and-execute"})
        summary.update(outcome)

        # funnel-summary — ONE journal row, always written.
        async def summary_step() -> str:
            db = await get_db()
            rid = await write_report(
                "funnel_summary", "info", _SOURCE,
                f"Weekly funnel pass ({run_date_iso[:10]}, regime={regime})",
                {
                    "run_date": run_date_iso, "regime": regime,
                    "universe_counts": {**assembled.get("counts", {}),
                                        **screened.get("counts", {})},
                    "exclusions": screened.get("excluded", [])[:50],
                    "screen_top20": [r.get("symbol") for r in screened.get("ranked", [])[:20]],
                    "light_spend": lights.get("spent", 0),
                    "decisions": outcome.get("decisions", {}),
                    "guardrail_notes": outcome.get("guardrail_notes", []),
                    "placed": outcome.get("placed", []),
                    "budget_used": outcome.get("budget_used", {}),
                },
                db=db,
            )
            return rid or ""

        await step.run("funnel-summary", summary_step)
        return {"status": "ok", **summary}

    return sleeve_a_funnel


# ── Full-pass orchestration (heavy imports are local to each helper) ─────────
# _assemble/_screen/_run_lights each run inside ONE memoized step; the paid
# per-symbol analyze steps in _theme_review/_handshake_and_enter are top-level.

async def _assemble(db, outlook: Dict[str, Any], holdings: List[str]) -> Dict[str, Any]:
    """Merge theme members + watchlist + holdings + industry-ETF holdings into a
    tagged universe. Returns JSON-safe data ONLY (no DataFrames) — OHLCV bars
    are fetched in the screen step so nothing pandas crosses a step boundary."""
    import asyncio  # noqa: PLC0415

    from execution.funnel.universe import (  # noqa: PLC0415
        fetch_industry_holdings, load_theme_members, merge_sources,
    )
    from execution.research_feed import get_research_context  # noqa: PLC0415

    theme_members = await load_theme_members(db)
    research = await get_research_context(db)
    watchlist = research.get("watchlist", [])
    industry_holdings = await asyncio.to_thread(
        fetch_industry_holdings, outlook.get("industryRankings", [])
    )
    tagged = merge_sources(theme_members, industry_holdings, watchlist, holdings)
    return {
        "tagged": tagged,
        "counts": {
            "themes": len(theme_members), "watchlist": len(watchlist),
            "industry_holdings": sum(len(v) for v in industry_holdings.values()),
            "assembled": len(tagged),
        },
    }


async def _screen(
    assembled: Dict[str, Any], outlook: Dict[str, Any], sleeve_ctx: Dict[str, Any],
) -> Dict[str, Any]:
    """Fetch OHLCV, apply the sanity floors, screen every kept name, quality
    re-rank the top 40, pick light slots. All DataFrames stay LOCAL to this
    step; the returned dict is JSON-safe."""
    import asyncio  # noqa: PLC0415

    from execution.funnel.screen import (  # noqa: PLC0415
        rank_candidates, screen_row, select_light_slots,
    )
    from execution.funnel.universe import apply_floors  # noqa: PLC0415
    from execution.market_data import fetch_ohlcv_batch  # noqa: PLC0415

    tagged = assembled.get("tagged", {})
    symbols = list(tagged)
    ohlcv = await asyncio.to_thread(fetch_ohlcv_batch, symbols + [BENCHMARK])

    spy_df = ohlcv.get(BENCHMARK)
    spy_closes = spy_df["Close"].dropna() if spy_df is not None else None
    if spy_closes is None:
        return {"ranked": [], "slots": {"light": [], "free_ride": [], "over_budget": []},
                "close_by_symbol": {}, "sector_by_symbol": {}, "excluded": [],
                "counts": {"kept": 0, "excluded": 0}}

    # Sanity floors need price/ADV metrics derived from the bars.
    metrics: Dict[str, Dict[str, Any]] = {}
    for sym in symbols:
        df = ohlcv.get(sym)
        if df is None or df.empty:
            continue
        closes = df["Close"].dropna()
        if closes.empty:
            continue
        metrics[sym] = {
            "price": float(closes.iloc[-1]),
            "adv_usd": float((df["Close"] * df["Volume"]).tail(20).mean()),
            "market_cap": None,
        }
    kept, excluded = apply_floors(tagged, metrics)

    top_industries = [r.get("etf") for r in outlook.get("industryRankings", [])[:5] if r.get("etf")]
    top_themes = [r.get("slug") for r in outlook.get("themeRankings", [])[:5] if r.get("slug")]

    rows: List[Dict[str, Any]] = []
    close_by_symbol: Dict[str, float] = {}
    for sym, tags in kept.items():
        df = ohlcv.get(sym)
        if df is None:
            continue
        row = screen_row(sym, df, spy_closes, tags, top_themes, top_industries, None)
        if row is None:
            continue
        rows.append(row)
        close_by_symbol[sym] = row["price"]

    ranked = rank_candidates(rows)
    ranked = await _quality_rerank(ranked)
    ranked = rank_candidates(ranked)

    stale_holdings = [s for s in sleeve_ctx.get("positions", {})]
    slots = select_light_slots(
        ranked, fresh_symbols=set(), stale_holdings=stale_holdings,
        budget=LIGHT_RUNS_PER_WEEK,
    )
    sector_by_symbol = await _sectors_for([r["symbol"] for r in ranked])
    return {
        "ranked": ranked, "slots": slots, "close_by_symbol": close_by_symbol,
        "sector_by_symbol": sector_by_symbol, "excluded": excluded,
        "counts": {"kept": len(kept), "excluded": len(excluded)},
    }


async def _quality_rerank(ranked: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Re-score the top N with a real valuation quality score; rest keep q=5."""
    import asyncio  # noqa: PLC0415

    try:
        from research_swarm.agents.fundamentalist.scorer import HealthScorer  # noqa: PLC0415
        from research_swarm.data.data_provider_hybrid import (  # noqa: PLC0415
            HybridDataProvider,
        )
    except Exception:  # noqa: BLE001 — quality is a nicety, not a gate
        return ranked

    scorer = HealthScorer()
    provider = HybridDataProvider()
    for row in ranked[:_QUALITY_RERANK_TOP_N]:
        try:
            metrics = await asyncio.to_thread(
                provider.get_valuation_metrics, row["symbol"]
            )
            q = await asyncio.to_thread(scorer.calculate_valuation_score, metrics)
            if q is not None:
                # blend the real quality into the screen score (q is 0..10).
                row["quality"] = float(q)
        except Exception:  # noqa: BLE001
            logger.debug("quality rerank skipped for %s", row.get("symbol"))
    return ranked


async def _sectors_for(symbols: List[str]) -> Dict[str, str]:
    from api.lib.db import get_db  # noqa: PLC0415

    out: Dict[str, str] = {}
    try:
        db = await get_db()
        rows = await db.tickermeta.find_many(where={"ticker": {"in": symbols}})
        for r in rows:
            if getattr(r, "sector", None):
                out[r.ticker] = r.sector
    except Exception:  # noqa: BLE001
        logger.debug("sector lookup failed")
    return out


async def _run_lights(db, run_date: datetime, screened: Dict[str, Any]) -> Dict[str, Any]:
    """ONE step: light_run_one + persist for each light slot; per-name guards."""
    from execution.funnel.light_runner import (  # noqa: PLC0415
        light_run_one, persist_light_signal,
    )

    by_symbol = {r["symbol"]: r for r in screened.get("ranked", [])}
    slots = screened.get("slots", {}).get("light", [])
    light_rows: Dict[str, Dict[str, Any]] = {}
    spent = 0
    for sym in slots:
        screen = by_symbol.get(sym)
        if screen is None:
            continue
        try:
            light = await light_run_one(sym, screen)
            await persist_light_signal(db, run_date, light, screen.get("screen_score", 0.0))
            light_rows[sym] = light
            spent += 1
        except Exception:  # noqa: BLE001 — one name must not sink the batch
            logger.exception("funnel: light run failed for %s", sym)
            await _journal(db, "light_run_failure", "warning",
                           f"{sym}: light run failed", {"symbol": sym})
    return {"light_rows": light_rows, "spent": spent}


async def _decide_and_execute(
    db, client, run_date: datetime, regime: str, sleeve_ctx: Dict[str, Any],
    assembled: Dict[str, Any], screened: Dict[str, Any], lights: Dict[str, Any], step,
) -> Dict[str, Any]:
    """Conviction table → theme review → plan → sells → entries. Returns the
    summary fragments the funnel_summary row records."""
    ranked = screened.get("ranked", [])
    by_symbol = {r["symbol"]: r for r in ranked}
    close_by_symbol = screened.get("close_by_symbol", {})
    positions = sleeve_ctx.get("positions", {})
    light_rows = lights.get("light_rows", {})

    # Conviction table for holdings and candidates.
    candidates: List[Dict[str, Any]] = []
    candidates_by_symbol: Dict[str, Dict[str, Any]] = {}
    for sym, screen in by_symbol.items():
        light = light_rows.get(sym)
        conv_input = (
            _conviction_input_from_light(light, screen) if light
            else _conviction_input_from_light({}, screen)
        )
        conv = compute_conviction(conv_input)
        entry = {"symbol": sym, "conviction": conv["score"], "vetoed": conv["vetoed"],
                 "screen": screen}
        candidates.append(entry)
        candidates_by_symbol[sym] = entry

    sleeve_equity = sleeve_ctx["cash"] + sum(
        qty * close_by_symbol.get(sym, 0.0) for sym, qty in positions.items()
    )

    holdings: List[Dict[str, Any]] = []
    for sym, qty in positions.items():
        close = close_by_symbol.get(sym, 0.0)
        screen = by_symbol.get(sym, {})
        light = light_rows.get(sym)
        conv = compute_conviction(_conviction_input_from_light(light or {}, screen))
        holdings.append({
            "symbol": sym, "qty": qty, "market_value": qty * close,
            "conviction": conv["score"], "vetoed": conv["vetoed"],
            "tags": screen.get("tags") or {}, "sector": screened.get("sector_by_symbol", {}).get(sym),
        })

    # Theme review: holdings whose ALL sourcing themes are retired.
    await _theme_review(db, run_date, holdings, by_symbol, light_rows, step)

    decisions = plan_decisions(holdings, candidates, sleeve_equity, SLEEVE_A_MAX_POSITIONS)

    # Sells (exits + trims) first — their proceeds fund entries. Wrapped in its
    # own step (no internal step.run) so the shadow sells + cash update are
    # memoized and never replay on a later step boundary.
    sell_out = await _run_step(
        step, "execute-sells",
        lambda: _execute_sells(
            db, client, decisions, close_by_symbol, positions, run_date,
            sleeve_ctx["cash"],
        ),
    )

    # Deployable = regime fraction × equity − position MV − queued notionals.
    invested_fraction = REGIME_INVESTED_FRACTION.get(regime, 0.7)
    position_mv = sum(qty * close_by_symbol.get(sym, 0.0) for sym, qty in positions.items())
    deployable = max(0.0, invested_fraction * sleeve_equity - position_mv)
    cash_available = sell_out["cash"]

    other_sleeve_sector_notional = await _sleeve_b_sector_notional(db)

    placed = await _handshake_and_enter(
        db, client, decisions.get("entry_queue", []), candidates_by_symbol, run_date,
        sleeve_equity, deployable, cash_available, holdings,
        screened.get("sector_by_symbol", {}), other_sleeve_sector_notional,
        sleeve_ctx.get("allow_buys", True), step,
    )

    # Buys shrink the cash ledger too (sells already updated it). Wrapped in a
    # step so the final ledger write is memoized, not replayed.
    if placed:
        remaining_cash = max(0.0, cash_available - sum(p["notional"] for p in placed))

        async def _finalize_cash() -> Dict[str, Any]:
            try:
                from execution.sleeve_service import update_sleeve_cash  # noqa: PLC0415

                await update_sleeve_cash(db, SLEEVE_A, remaining_cash)
            except Exception:  # noqa: BLE001
                logger.exception("funnel: post-entry cash update failed")
            return {"cash": remaining_cash}

        await _run_step(step, "finalize-entry-cash", _finalize_cash)

    return {
        "decisions": decisions, "guardrail_notes": decisions.get("notes", []),
        "placed": placed, "sells": sell_out,
        "budget_used": {"full_runs_cap": FULL_RUNS_PER_WEEK,
                        "light_runs": lights.get("spent", 0)},
        "sleeve_equity": round(sleeve_equity, 2),
    }


async def _theme_review(
    db, run_date: datetime, holdings: List[Dict[str, Any]],
    by_symbol: Dict[str, Any], light_rows: Dict[str, Any], step,
) -> None:
    """Per holding whose EVERY sourcing theme is retired: re-run research and
    re-score with hunting_bonus=0; flag theme_review_failed below the floor."""
    flagged = [h for h in holdings if _all_themes_retired(h, by_symbol)]
    if not flagged:
        return  # cheap no-op — the common case
    for h in flagged:
        sym = h["symbol"]
        screen = by_symbol.get(sym, {})
        try:
            gate = await reuse_or_budget(db, sym, run_date)
            if gate.get("action") == "analyze":
                if step is not None:
                    result = await step.run(
                        f"review-analyze-{sym.lower()}",
                        lambda s=sym: run_paid_analysis(s),
                    )
                else:
                    result = await run_paid_analysis(sym)
                persisted = await persist_full(
                    db, sym, run_date, result,
                    float(screen.get("price") or 0.0),
                    float(screen.get("screen_score") or 0.0),
                )
                signals = persisted.get("signals")
            else:
                signals = gate.get("signals")
        except Exception:  # noqa: BLE001
            logger.exception("funnel theme review failed for %s", sym)
            await _journal(db, "engine_failure", "warning",
                           f"{sym}: theme review failed", {"symbol": sym})
            continue

        conv_input = _conviction_input_from_signals(signals or {}, screen)
        conv_input["hunting_bonus"] = 0.0  # retired ground: no hunting credit
        conv = compute_conviction(conv_input)
        failed = conv["vetoed"] or conv["score"] < RETIRED_THEME_EXIT_CONVICTION
        h["theme_review_failed"] = failed
        await _journal(db, "theme_review", "info",
                       f"{sym}: theme review — {'exit' if failed else 'keep'}",
                       {"symbol": sym, "conviction": conv["score"],
                        "floor": RETIRED_THEME_EXIT_CONVICTION, "failed": failed})


def _all_themes_retired(holding: Dict[str, Any], by_symbol: Dict[str, Any]) -> bool:
    """A holding is flagged only when it has sourcing themes and NONE remain
    active. Screen tags only carry active themes, so an active-theme holding
    keeps a non-empty themes list; an all-retired holding has an empty one but
    was still sourced from a theme (holding flag)."""
    screen = by_symbol.get(holding["symbol"], {})
    tags = (screen.get("tags") or {})
    themes = tags.get("themes", [])
    return bool(tags.get("holding")) and not themes and not tags.get("watchlist")


async def _sleeve_b_sector_notional(db) -> Dict[str, float]:
    """Sleeve B's per-sector market value, for the cross-sleeve sector cap.
    Sleeve B holds sector ETFs, so each position IS its own sector bucket."""
    from execution.sleeve_service import get_engine_positions  # noqa: PLC0415

    out: Dict[str, float] = {}
    try:
        positions = await get_engine_positions(db, SLEEVE_B)
        for p in positions:
            sector = getattr(p, "symbol", None)
            mv = float(getattr(p, "qty", 0.0) or 0.0) * float(getattr(p, "avgEntryPrice", 0.0) or 0.0)
            if sector:
                out[sector] = out.get(sector, 0.0) + mv
    except Exception:  # noqa: BLE001
        logger.debug("sleeve B sector notional lookup failed")
    return out


try:
    sleeve_a_funnel = _register_inngest_function()
except Exception:
    # inngest pip SDK not available (e.g. unit tests) — no-op export.
    sleeve_a_funnel = None  # type: ignore[assignment]
