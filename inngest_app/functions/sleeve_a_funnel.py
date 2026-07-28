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
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from execution.constants import (
    BENCHMARK,
    CONCENTRATION_REVIEW_WEIGHT,
    DCA_TRANCHE_FRACTION,
    EARNINGS_DIVERGENCE_DD,
    FRESH_REPORT_DAYS,
    FULL_RUNS_PER_WEEK,
    HOLDING_STALE_WEEKS,
    LIGHT_RUNS_PER_WEEK,
    MIN_TRADE_NOTIONAL,
    OUTLOOK_MAX_AGE_DAYS,
    REDUCE_TRANCHE_FRACTION,
    SLEEVE_A_INVESTED_FRACTION,
    RETIRED_THEME_EXIT_CONVICTION,
    SCREEN_WEIGHTS,
    SLEEVE_A,
    SLEEVE_A_FRACTION,
    SLEEVE_A_MAX_POSITIONS,
    SLEEVE_B,
    TRIM_FALLBACK_TARGET,
)
from execution.engine.guardrails import enforce_funnel_guardrails
from execution.funnel.conviction import compute_conviction
from execution.funnel.decisions import plan_decisions
from execution.funnel.entries import (
    entry_limit_price, entry_ttl_days, extension_state, size_entry,
)
from execution.funnel.research_budget import (
    _FUNNEL_MARKER, full_runs_used, persist_full, reuse_or_budget,
    run_paid_analysis,
)
from execution.funnel.review_triggers import collect_triggers, drawdown
from execution.outlook_service import get_latest_outlook
from execution.reporting import write_report
from execution.thesis.memo import gather_memo_packet, persist_memo, reason_memo
from execution.thesis.parser import MemoParseError, parse_memo_response
from execution.thesis.planner import plan_from_memo

logger = logging.getLogger(__name__)

_SOURCE = "sleeve_a_funnel"
_QUALITY_RERANK_TOP_N = 40
# A theme the memo just MOVED into one of these stages puts every holding
# sourced from it up for review (spec §2/§7.3) — the transition fires it, not
# the state, so a theme that was already crowded last week stays silent. A
# stage change NEVER trades by itself; it earns the review whose verdict is the
# only trim/exit authority.
_MEMO_REVIEW_STAGES = ("crowded", "priced")


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
    signals: Dict[str, Any], screen: Dict[str, Any],
    base: Optional[Dict[str, Any]] = None, report_age_days: float = 0.0,
) -> Dict[str, Any]:
    """Overlay full-run (manager) signals ONTO a light/screen-derived base.

    extract_signals_from_result returns ONLY verdict/fairValue/insiderScore/
    darkPoolScore/sentimentScore — NOT valuation_score, financial_health,
    earnings_momentum, short_pct_float or market_cap. Building conviction from
    the full signals alone therefore drops the small-cap haircut and the
    fundamentals exactly at the entry recompute (I1). So we start from the base
    (the light-row/screen conviction input, which carries market_cap,
    valuation_score, short_pct_float, momentum, hunting) and let the full-run
    fields override only where present."""
    merged = dict(base or {})
    merged.setdefault("momentum", screen.get("momentum"))
    merged.setdefault("hunting_bonus", screen.get("hunting_bonus"))
    merged.setdefault("market_cap", screen.get("market_cap"))
    if report_age_days:
        merged["report_age_days"] = report_age_days
    merged.setdefault("report_age_days", 0.0)

    if signals.get("verdict") is not None:
        merged["verdict"] = signals.get("verdict")
    fv_gap = signals.get("fair_value_gap_pct")
    if fv_gap is None:
        fv_gap = _fv_gap_pct(signals.get("fairValue"), screen.get("price"))
    if fv_gap is not None:
        merged["fair_value_gap_pct"] = fv_gap
    for src, dst in (
        ("insiderScore", "insider_score"),
        ("darkPoolScore", "dark_pool_score"),
        ("sentimentScore", "sentiment_score"),
    ):
        if signals.get(src) is not None:
            merged[dst] = signals.get(src)
    return merged


def _conviction_input_from_light(
    light: Dict[str, Any], screen: Dict[str, Any],
    report_age_days: float = 0.0, hunting_bonus: Optional[float] = None,
    verdict: Optional[str] = None,
) -> Dict[str, Any]:
    """Light-run (numbers-only, snake_case) shape → compute_conviction input.
    `verdict` is threaded from the symbol's most recent full WeeklySignal row
    (the light runner itself never assigns one) so a holding whose last full
    run said SELL is vetoed and staleness decays with real report age (C2)."""
    return {
        "verdict": verdict,
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


def _age_days(created: Any, now: datetime) -> Optional[float]:
    """Whole days between a WeeklySignal.createdAt and now (tz-safe)."""
    if created is None:
        return None
    try:
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return float((now - created).days)
    except (TypeError, AttributeError):
        return None


async def _load_latest_signals(
    db, symbols: List[str], now: datetime,
) -> Dict[str, Dict[str, Any]]:
    """ONE query for ALL symbols → per-symbol {verdict, report_age_days,
    prior_verdict, last_review_price}.

    verdict/prior_verdict/last_review_price all come from the most recent
    tier='full' row (the categorical call only a paid run makes): verdict is
    this pass's call, prior_verdict is last pass's (the buy→hold downgrade edge
    that releases a REDUCE tranche), last_review_price is the currentPrice that
    full run recorded (the run-up review anchor). report_age_days comes from
    the most recent row of ANY tier — a light run that refreshed the numbers
    this week counts as fresh for the staleness multiplier (§7.1) and the
    free-ride slot (§5)."""
    out: Dict[str, Dict[str, Any]] = {}
    syms = list({s for s in symbols if s})
    if not syms:
        return out
    try:
        rows = await db.weeklysignal.find_many(
            where={"ticker": {"in": syms}},
            order=[{"runDate": "desc"}, {"createdAt": "desc"}],
        )
    except Exception:  # noqa: BLE001 — degrade; missing ages are neutral
        logger.exception("funnel: latest-signals query failed")
        return out
    for r in rows:
        sym = getattr(r, "ticker", None)
        if sym is None:
            continue
        entry = out.setdefault(
            sym, {"verdict": None, "report_age_days": None,
                  "prior_verdict": None, "last_review_price": None,
                  "position_size_rec": None,
                  "_have_age": False, "_have_verdict": False},
        )
        if not entry["_have_age"]:
            entry["report_age_days"] = _age_days(getattr(r, "createdAt", None), now)
            entry["_have_age"] = True
        if not entry["_have_verdict"] and getattr(r, "tier", None) == "full":
            entry["verdict"] = getattr(r, "verdict", None)
            entry["prior_verdict"] = getattr(r, "priorVerdict", None)
            entry["last_review_price"] = getattr(r, "currentPrice", None)
            entry["position_size_rec"] = getattr(r, "positionSizeRec", None)
            entry["_have_verdict"] = True
    for entry in out.values():
        entry.pop("_have_age", None)
        entry.pop("_have_verdict", None)
    return out


def _light_slot_policy(
    ranked: List[Dict[str, Any]], positions: Dict[str, Any],
    latest: Dict[str, Dict[str, Any]],
) -> tuple:
    """Spec §5 slot policy. stale_holdings = a holding whose newest report is
    older than HOLDING_STALE_WEEKS (or has NO row) — it claims a light slot.
    fresh_symbols = any ranked name refreshed within FRESH_REPORT_DAYS — it
    rides free (no slot burned). Returns (fresh_symbols, stale_holdings)."""
    stale_days = HOLDING_STALE_WEEKS * 7
    stale_holdings: List[str] = []
    for sym in positions:
        age = (latest.get(sym) or {}).get("report_age_days")
        if age is None or age > stale_days:
            stale_holdings.append(sym)
    fresh_symbols = {
        r["symbol"] for r in ranked
        if (latest.get(r["symbol"]) or {}).get("report_age_days") is not None
        and (latest.get(r["symbol"]) or {}).get("report_age_days") < FRESH_REPORT_DAYS
    }
    return fresh_symbols, stale_holdings


# ── Step helpers (unit-tested directly with step=None) ───────────────────────

def _outlook_context(outlook: Any) -> Dict[str, Any]:
    """JSON-safe outlook context for the pass. industryRankings/themeRankings
    are DICTS shaped {"rankings": [...], "rotations": [...], "missing": [...]}
    (built by industry_strength.py / theme_strength.py; themes/discovery.py
    also reads .get("rankings")) — unwrap the rankings LIST here so every
    downstream consumer (the top-industries/top-themes scoring slices in
    _screen) sees a plain list.

    sectorRankings is ALREADY a plain list on the row (see schema.prisma:910)
    and needs no unwrap; the weekly thesis memo requires sector RS as a
    crowdedness input (spec §3.1), so it is passed straight through."""
    return {
        "regime": outlook.regime,
        "industryRankings": (outlook.industryRankings or {}).get("rankings", []),
        "themeRankings": (outlook.themeRankings or {}).get("rankings", []),
        "sectorRankings": getattr(outlook, "sectorRankings", None) or [],
    }


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
        if not prev_spy or prev_spy <= 0.0:
            # REFUSE to bootstrap on a missing SPY close: seeding
            # inceptionSpyClose=0.0 silently disables the −15pp breaker forever.
            # Skip this pass; retry next Monday when the close is available.
            await _journal(
                db, "engine_failure", "warning",
                "Funnel skipped: previous SPY close unavailable — refusing to "
                "seed Sleeve A with inceptionSpyClose=0.0 (would disable breaker)",
                {"stage": "ensure-sleeve-a", "prev_spy": prev_spy},
            )
            return None
        state = await init_sleeve_state(
            db, SLEEVE_A, cash=seed_cash, spy_close=prev_spy,
            inception_date=now, mode="shadow",
        )
        # NOT funnel_summary: the pass emits exactly ONE funnel_summary (the
        # final step). rebalance_summary is the closest registered notice type.
        await _journal(
            db, "rebalance_summary", "info",
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
    # Cap accumulation (I5): enforce_funnel_guardrails sums theme/sector usage
    # across the LIST it is given, so each placed order must be appended to the
    # baseline the NEXT call sees — two same-theme entries in one pass would
    # otherwise each be checked against a fresh baseline and jointly bust 35%.
    running_holdings: List[Dict[str, Any]] = list(holdings)

    for sym in entry_queue:
        cand = candidates_by_symbol.get(sym) or {}
        screen = cand.get("screen") or {}
        base_input = cand.get("conv_input")

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

        # 2) Re-score conviction: overlay the FULL signals onto the light/screen
        #    base so the small-cap haircut + fundamentals survive the recompute
        #    (I1). SELL is a veto.
        conv = compute_conviction(
            _conviction_input_from_signals(signals, screen, base=base_input)
        )
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
            running_holdings, other_sleeve_sector_notional, allow_buys,
        )
        buys = [o for o in adjusted if o["side"] == "buy"]
        if not buys:
            await _journal(db, "entry_deferred", "info",
                           f"{sym}: buy blocked by guardrails",
                           {"symbol": sym, "notes": notes})
            continue

        # 5) Submit the shadow limit buy (deterministic client_order_id).
        source_tags = screen.get("tags") or {}
        report_ref = await _latest_full_signal_id(db, sym)
        sector = sector_by_symbol.get(sym)
        for o in buys:
            final_notional = float(o["notional"])
            qty = round(final_notional / limit, 4)
            expires_at = run_date + timedelta(days=ttl)
            coid = f"shadow-A-{sym}-{run_date:%Y%m%d}"
            # Provenance (C1a): the journal carries sourceTags/convictionScore/
            # reportRef so the daily fills step can copy them onto the position
            # row — reviving the dead migrated columns and giving the weekly
            # theme review persisted tags to read.
            journal = {
                "symbol": sym, "conviction": conviction, "limit_price": limit,
                "notional": final_notional, "extension_state": state,
                "ttl_days": ttl, "guardrail_notes": notes,
                "sourceTags": source_tags, "convictionScore": conviction,
                "reportRef": report_ref,
                "dist_200wma": screen.get("dist_200wma"),
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
            # Feed this order into the baseline the next guardrail call sees.
            running_holdings.append({
                "symbol": sym, "market_value": final_notional,
                "tags": source_tags, "sector": sector,
            })
            deployable_remaining = max(0.0, deployable_remaining - final_notional)
            cash_remaining = max(0.0, cash_remaining - final_notional)

    return placed


async def _execute_sells(
    db, client, decisions: Dict[str, Any],
    close_by_symbol: Dict[str, float], positions: Dict[str, float],
    run_date: datetime, sleeve_cash: float,
) -> Dict[str, Any]:
    """Sell every exit (full) and trim (partial) — last close is the hint;
    live brokers fill at the real market price and cash credits the ACTUAL
    fill. Journal each, return the resulting cash balance. update_sleeve_cash
    is owned here (the cron), not in the pure planner."""
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
            res = await client.submit_sell(
                symbol=sym, qty=qty, price_hint=close,
                journal={"reason": ex.get("reason")}, client_order_id=coid,
            )
        except Exception:  # noqa: BLE001
            logger.exception("funnel: exit sell failed for %s", sym)
            await _journal(db, "engine_failure", "warning",
                           f"{sym}: exit shadow-sell failed", {"symbol": sym})
            continue
        # Credit the ACTUAL fill (I1): live sells fill at the real market
        # price, not last close. Shadow returns hint values — unchanged.
        fq = float(res.filled_qty or 0.0)
        fp = res.filled_avg_price
        if fq <= 0 or fp is None:
            await _journal(db, "engine_failure", "warning",
                           f"{sym}: exit sell did not fill (status={res.status})",
                           {"symbol": sym, "qty": qty, "status": res.status,
                            "reason": ex.get("reason")})
            continue
        proceeds += fq * float(fp)
        cash += fq * float(fp)
        sold.append(sym)
        await _journal(db, _EXIT_REPORT.get(ex.get("reason"), "exit_sell_verdict"),
                       "info", f"{sym}: exit ({ex.get('reason')})",
                       {"symbol": sym, "qty": fq, "fill_price": float(fp),
                        "reason": ex.get("reason")})

    # reason → EngineReport type. A concentration trim journals risk_trim; a
    # verdict-downgrade REDUCE tranche journals its own thesis_reduce type so
    # the owner can tell a risk-driven trim from a thesis-driven staged release.
    _TRIM_REPORT = {"risk_trim": "risk_trim", "thesis_reduce": "thesis_reduce"}
    for tr in decisions.get("trims", []):
        sym = tr["symbol"]
        close = close_by_symbol.get(sym)
        sell_notional = float(tr.get("sell_notional") or 0.0)
        if close is None or close <= 0 or sell_notional < MIN_TRADE_NOTIONAL:
            continue
        reason = tr.get("reason") or "risk_trim"
        report_type = _TRIM_REPORT.get(reason, "risk_trim")
        qty = round(sell_notional / close, 4)
        coid = f"shadow-A-{sym}-{run_date:%Y%m%d}-sell"
        try:
            res = await client.submit_sell(
                symbol=sym, qty=qty, price_hint=close,
                journal={"reason": reason}, client_order_id=coid,
            )
        except Exception:  # noqa: BLE001
            logger.exception("funnel: trim (%s) failed for %s", reason, sym)
            await _journal(db, "engine_failure", "warning",
                           f"{sym}: {reason} shadow-sell failed", {"symbol": sym})
            continue
        fq = float(res.filled_qty or 0.0)
        fp = res.filled_avg_price
        if fq <= 0 or fp is None:
            await _journal(db, "engine_failure", "warning",
                           f"{sym}: {reason} sell did not fill (status={res.status})",
                           {"symbol": sym, "qty": qty, "status": res.status})
            continue
        proceeds += fq * float(fp)
        cash += fq * float(fp)
        await _journal(db, report_type, "info", f"{sym}: {reason}",
                       {"symbol": sym, "qty": fq, "fill_price": float(fp),
                        "sell_notional": sell_notional, "reason": reason,
                        "origin": tr.get("origin"), "triggers": tr.get("triggers")})

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
            return _outlook_context(outlook)

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
                latest = await _load_latest_signals(
                    db,
                    list(assembled.get("tagged", {})) + list(sleeve_ctx["positions"]),
                    now,
                )
                tradable = await _alpaca_tradable_symbols(db)
                return await _screen(assembled, outlook, sleeve_ctx, latest, tradable)
            except Exception:  # noqa: BLE001
                logger.exception("funnel: screen failed")
                await _journal(db, "engine_failure", "warning",
                               "Screen failed", {"stage": "screen"})
                return {"ranked": [], "slots": {"light": [], "free_ride": [],
                                                "over_budget": []},
                        "close_by_symbol": {}, "sector_by_symbol": {},
                        "excluded": [], "counts": {"kept": 0, "excluded": 0}}

        screened = await step.run("screen", screen_step)

        # light-runs — ONE memoized step; per-name guards inside.
        async def light_step() -> Dict[str, Any]:
            db = await get_db()
            try:
                return await _run_lights(db, run_date, screened)
            except Exception:  # noqa: BLE001
                logger.exception("funnel: light-runs step failed")
                await _journal(db, "engine_failure", "warning",
                               "Light runs failed", {"stage": "light-runs"})
                return {"light_rows": {}, "spent": 0}

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
            from execution.broker import sleeve_a_broker  # noqa: PLC0415
            from execution.sleeve_service import get_sleeve_state  # noqa: PLC0415

            # shadow -> ShadowBrokerClient (3D replay); live -> AlpacaFunnelBroker.
            state = await get_sleeve_state(db, SLEEVE_A)
            client = await sleeve_a_broker(db, state)
            if client is None:  # live mode, no linked account (M2)
                await _journal(db, "engine_failure", "warning",
                               "Sleeve A live mode but no linked broker account",
                               {"stage": "decide-and-execute"})
            else:
                outcome = await _decide_and_execute(
                    db, client, run_date, regime, sleeve_ctx, assembled,
                    screened, lights, step, outlook=outlook,
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
                    "memo": outcome.get(
                        "memo", {"status": "noop", "entries_planned": 0,
                                 "rejected": 0}),
                    "decisions": outcome.get("decisions", {}),
                    "guardrail_notes": outcome.get("guardrail_notes", []),
                    "placed": outcome.get("placed", []),
                    "reviews": outcome.get("reviews", {}),
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
    """Merge theme members + watchlist + holdings into a tagged universe.
    No formula-picked (industry-RS) channel: a symbol enters only via theme
    membership, the watchlist, or being already held. Returns JSON-safe data
    ONLY (no DataFrames) — OHLCV bars are fetched in the screen step so
    nothing pandas crosses a step boundary."""
    from execution.funnel.universe import (  # noqa: PLC0415
        load_theme_members, merge_sources,
    )
    from execution.research_feed import get_research_context  # noqa: PLC0415

    theme_members = await load_theme_members(db)
    research = await get_research_context(db)
    watchlist = research.get("watchlist", [])
    tagged = merge_sources(theme_members, {}, watchlist, holdings)
    return {
        "tagged": tagged,
        # active theme slugs this week — a holding's stored sourcing theme is
        # "retired" (§7.4) precisely when it is absent from this set.
        "active_themes": list(theme_members.keys()),
        "counts": {
            "themes": len(theme_members), "watchlist": len(watchlist),
            "assembled": len(tagged),
        },
    }


async def _alpaca_tradable_symbols(db) -> Optional[set]:
    """Alpaca's active+tradable US-equity universe (None on any failure — a
    data outage degrades to 'don't gate', matching this module's other
    outage guards, rather than freezing the whole screen). Lives in
    execution.broker.tradable so the theme passes share one definition."""
    from execution.broker.tradable import alpaca_tradable_symbols  # noqa: PLC0415

    return await alpaca_tradable_symbols(db)


async def _screen(
    assembled: Dict[str, Any], outlook: Dict[str, Any], sleeve_ctx: Dict[str, Any],
    latest_signals: Optional[Dict[str, Dict[str, Any]]] = None,
    tradable_symbols: Optional[set] = None,
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
    kept, excluded = apply_floors(tagged, metrics, tradable_symbols)

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

    # 200-week MA advisory distance (Task 9): a DEDICATED small weekly fetch
    # for holdings + the top-ranked candidate pool ONLY — never the full
    # screening universe (that's the daily OHLCV fetch above). "Top-ranked
    # candidate pool" = the same ranked[:_QUALITY_RERANK_TOP_N] window the
    # quality re-rank already uses as the funnel's candidate cap. Guarded:
    # any failure degrades to dist_200wma=None on every intended row and
    # journals engine_failure — advisory input, never blocks the pass (3A
    # degrade-never-block posture, mirroring _sectors_for's local-db journal).
    by_symbol_for_wma = {r["symbol"]: r for r in ranked}
    wma_symbols = list(dict.fromkeys(
        list(sleeve_ctx.get("positions", {}))
        + [r["symbol"] for r in ranked[:_QUALITY_RERANK_TOP_N]]
    ))
    try:
        from execution.market_data import (  # noqa: PLC0415
            dist_200wma, fetch_weekly_closes,
        )

        weekly = await asyncio.to_thread(fetch_weekly_closes, wma_symbols)
        for sym in wma_symbols:
            row = by_symbol_for_wma.get(sym)
            if row is not None:
                row["dist_200wma"] = dist_200wma(weekly.get(sym))
    except Exception:  # noqa: BLE001 — advisory input degrades, never blocks
        logger.exception("funnel: 200-week MA fetch failed")
        for sym in wma_symbols:
            row = by_symbol_for_wma.get(sym)
            if row is not None:
                row["dist_200wma"] = None
        try:
            from api.lib.db import get_db  # noqa: PLC0415

            db = await get_db()
            await _journal(
                db, "engine_failure", "warning",
                "200-week MA fetch failed — dist_200wma unavailable this pass",
                {"stage": "screen-200wma", "symbols": len(wma_symbols)},
            )
        except Exception:  # noqa: BLE001
            pass

    fresh_symbols, stale_holdings = _light_slot_policy(
        ranked, sleeve_ctx.get("positions", {}), latest_signals or {},
    )
    slots = select_light_slots(
        ranked, fresh_symbols=fresh_symbols, stale_holdings=stale_holdings,
        budget=LIGHT_RUNS_PER_WEEK,
    )
    sector_by_symbol = await _sectors_for([r["symbol"] for r in ranked])
    # Harden for the Inngest JSON step boundary: pandas arithmetic can leave
    # numpy scalars in the rows, which don't JSON-serialize — force plain float.
    try:
        import numpy as np  # noqa: PLC0415

        _np_scalar: Any = np.generic
    except Exception:  # noqa: BLE001
        _np_scalar = ()
    for row in ranked:
        for k, v in row.items():
            if isinstance(v, bool):
                continue
            if isinstance(v, (int, float)) or isinstance(v, _np_scalar):
                row[k] = float(v)
    close_by_symbol = {s: float(p) for s, p in close_by_symbol.items()}
    return {
        "ranked": ranked, "slots": slots, "close_by_symbol": close_by_symbol,
        "sector_by_symbol": sector_by_symbol, "excluded": excluded,
        "counts": {"kept": len(kept), "excluded": len(excluded)},
    }


async def _quality_rerank(ranked: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Re-score the top N with a real valuation quality score; rest keep q=5.

    calculate_valuation_score returns Tuple[float, Dict] — the tuple must be
    UNPACKED (float(tuple) raises per-row, swallowed at debug) and the row's
    screen_score must be RE-BLENDED with the quality delta, else the re-sort in
    _screen changes nothing and the 40 network calls are wasted (I2). Quality is
    a cheap tiebreaker (§5): delta × SCREEN_WEIGHTS['quality'] is exact."""
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
            q, _detail = await asyncio.to_thread(
                scorer.calculate_valuation_score, metrics
            )
            if q is not None:
                old_q = float(row.get("quality", 5.0))
                new_q = max(0.0, min(10.0, float(q)))
                row["quality"] = new_q
                row["screen_score"] = round(
                    float(row["screen_score"])
                    + SCREEN_WEIGHTS["quality"] * (new_q - old_q),
                    3,
                )
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
        # A silent loss of the cross-sleeve sector cap must be VISIBLE.
        logger.exception("funnel: TickerMeta sector lookup failed")
        try:
            db = await get_db()
            await _journal(db, "engine_failure", "warning",
                           "TickerMeta sector lookup failed — cross-sleeve sector "
                           "cap may be under-enforced this pass",
                           {"stage": "sectors-for", "symbols": len(symbols)})
        except Exception:  # noqa: BLE001
            pass
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


def _parse_trim_target(meta: Dict[str, Any]) -> Optional[float]:
    """Pull an explicit target weight from the review's positionSizeRec string
    (e.g. "trim to 8%") for a concentration trim. Honored only when
    0 < x < CONCENTRATION_REVIEW_WEIGHT — a review that says "hold 25%" is not
    a trim instruction. None ⇒ the caller uses TRIM_FALLBACK_TARGET."""
    rec = meta.get("position_size_rec")
    if not rec:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", str(rec))
    if not m:
        return None
    try:
        x = float(m.group(1)) / 100.0
    except ValueError:
        return None
    return x if 0.0 < x < CONCENTRATION_REVIEW_WEIGHT else None


# ── Thesis memo (spec §3) — the ONLY buy authority ───────────────────────────

async def _memo_pipeline(
    db, outlook: Dict[str, Any], book: List[Dict[str, Any]],
    candidates: Dict[str, Dict[str, Any]], run_date: datetime, step,
) -> Optional[Dict[str, Any]]:
    """Gather → memo (PAID, own memoized step) → parse → plan → persist.

    Returns the plan dict — `plan_from_memo`'s keys plus `prior_stages` (each
    thesis's stage BEFORE this memo, so the caller can trigger on the stage
    TRANSITION rather than the stage state) — or None for an unusable memo,
    which the caller treats as a no-op week (spec §7): entries skipped,
    everything else (fills, reviews already triggered, exits) proceeds.
    NEVER raises.

    Gather + the paid call are memoized TOGETHER under "thesis-memo", persist
    separately under "memo-persist", so a persist retry can never re-bill.
    Parse and plan are pure, so re-deriving them from the memoized raw on every
    replay yields an identical plan (which is what pins stage A's trigger set
    across replays).
    """
    import asyncio  # noqa: PLC0415

    async def _gather_and_reason() -> Dict[str, Any]:
        # Gather lives INSIDE the paid step, not before it. Inngest re-executes
        # the function body at every step boundary (a dozen-plus per run given
        # the steps that follow), so an unmemoized gather re-queries theme state
        # every time — and a transient gather blip on a post-memo replay would
        # discard a memo already PAID for and already persisted, returning None
        # while the stage writes stayed committed and the summary said "noop".
        # This closure calls no step.run of its own, so it is not a nested step.
        packet = await gather_memo_packet(db, outlook, book, candidates)
        # Each thesis's stage BEFORE the memo moves it. Memoized alongside the
        # raw so the transition set is identical on every replay.
        prior = {t["slug"]: t.get("stage") for t in (packet.get("theses") or [])
                 if t.get("slug")}
        raw = await asyncio.to_thread(reason_memo, packet)
        return {"raw": raw, "prior_stages": prior}

    try:
        memo_out = await _run_step(step, "thesis-memo", _gather_and_reason)
        raw = memo_out["raw"]
        prior_stages = memo_out["prior_stages"]
    except Exception:  # noqa: BLE001
        logger.exception("thesis memo: gather/paid call failed")
        await _journal(db, "engine_failure", "critical",
                       "memo gather/LLM step failed — no-op week",
                       {"stage": "thesis-memo"})
        return None
    try:
        memo = parse_memo_response(raw)
        held = {p["symbol"] for p in book}
        plan = plan_from_memo(memo, held, set(candidates))
    except Exception as exc:  # noqa: BLE001 — MemoParseError, or any residual
        # LOUDER than the theme parsers by design: a drifted top-level shape is
        # a no-op week, never a quiet zero-entry week that looks normal.
        kind = ("schema drift" if isinstance(exc, MemoParseError)
                else "unusable memo")
        logger.exception("thesis memo: %s", kind)
        await _journal(db, "engine_failure", "critical",
                       f"memo {kind} — no-op week: {exc}",
                       {"stage": "memo-parse", "raw_head": str(raw)[:2000]})
        return None

    for r in plan["rejected"]:
        await _journal(db, "entry_rejected", "info",
                       f"{r['ticker']}: memo entry rejected — {r['reason']}", r)

    week = run_date.date().isoformat()

    async def _persist() -> Dict[str, Any]:
        await persist_memo(db, week, raw, memo)
        for slug, stage in plan["stage_updates"].items():
            try:
                await db.themebasket.update(where={"slug": slug},
                                            data={"stage": stage})
            except Exception:  # noqa: BLE001
                logger.exception("stage persist failed for %s", slug)
        return {"persisted": True}

    try:
        await _run_step(step, "memo-persist", _persist)
    except Exception:  # noqa: BLE001 — a persist failure must not void the plan
        logger.exception("thesis memo: persist step failed")
        await _journal(db, "engine_failure", "warning",
                       "memo persist failed — plan still honored",
                       {"stage": "memo-persist"})
    plan["prior_stages"] = prior_stages
    return plan


async def _decide_and_execute(
    db, client, run_date: datetime, regime: str, sleeve_ctx: Dict[str, Any],
    assembled: Dict[str, Any], screened: Dict[str, Any], lights: Dict[str, Any], step,
    outlook: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Conviction table → theme review → plan → sells → entries. Returns the
    summary fragments the funnel_summary row records."""
    now = datetime.now(timezone.utc)
    ranked = screened.get("ranked", [])
    by_symbol = {r["symbol"]: r for r in ranked}
    close_by_symbol = screened.get("close_by_symbol", {})
    positions = sleeve_ctx.get("positions", {})
    light_rows = lights.get("light_rows", {})

    # Latest WeeklySignal per symbol (ONE query): the most recent full-tier
    # verdict (SELL → veto/exit) + report age (staleness decay). Without this
    # the conviction table is built from light data only — verdict hard-None,
    # age 0 — killing the SELL-verdict exit and the staleness multiplier (C2).
    latest = await _load_latest_signals(
        db, list(by_symbol) + list(positions), now,
    )

    # Persisted provenance (C1a): the theme-review check reads the sourceTags
    # STORED on the EnginePosition at fill time, not the weekly screen tags —
    # industry-sourced holdings (industries rotate out weekly by design) must
    # never trip a phantom paid review.
    stored_tags = await _load_position_source_tags(db)
    active_themes = set(assembled.get("active_themes", []))

    # Conviction table for holdings and candidates. Keep each candidate's conv
    # input so the entry-handshake recompute can overlay full signals ONTO it
    # (I1) instead of rebuilding from the signal-only shape.
    candidates: List[Dict[str, Any]] = []
    candidates_by_symbol: Dict[str, Dict[str, Any]] = {}
    for sym, screen in by_symbol.items():
        light = light_rows.get(sym)
        meta = latest.get(sym) or {}
        age = meta.get("report_age_days") or 0.0
        conv_input = _conviction_input_from_light(
            light or {}, screen, report_age_days=age, verdict=meta.get("verdict"),
        )
        conv = compute_conviction(conv_input)
        entry = {"symbol": sym, "conviction": conv["score"], "vetoed": conv["vetoed"],
                 "screen": screen, "conv_input": conv_input}
        candidates.append(entry)
        candidates_by_symbol[sym] = entry

    sleeve_equity = sleeve_ctx["cash"] + sum(
        qty * close_by_symbol.get(sym, 0.0) for sym, qty in positions.items()
    )

    def _build_holdings() -> List[Dict[str, Any]]:
        """Rebuild the holdings table from the CURRENT `latest` verdicts. Called
        once up front and again after stage B so a fresh review's verdict flows
        into vetoed/conviction → plan_decisions (SELL/AVOID exits ride the
        existing sell_verdict path). Reads `latest` as a free variable so the
        stage-B refresh is picked up on the second call."""
        result: List[Dict[str, Any]] = []
        for sym, qty in positions.items():
            close = close_by_symbol.get(sym, 0.0)
            screen = by_symbol.get(sym, {})
            light = light_rows.get(sym)
            meta = latest.get(sym) or {}
            age = meta.get("report_age_days") or 0.0
            conv = compute_conviction(_conviction_input_from_light(
                light or {}, screen, report_age_days=age, verdict=meta.get("verdict"),
            ))
            result.append({
                "symbol": sym, "qty": qty, "market_value": qty * close,
                "conviction": conv["score"], "vetoed": conv["vetoed"],
                "tags": screen.get("tags") or {},
                "source_tags": stored_tags.get(sym) or {},
                "sector": screened.get("sector_by_symbol", {}).get(sym),
            })
        return result

    holdings = _build_holdings()

    # ── Thesis memo: the ONLY buy authority (spec §3). Runs BEFORE stage A so
    # its `review` actions and its crowded/priced stage moves can join this
    # week's trigger set. None ⇒ unusable memo ⇒ no-op week: no entries, while
    # exits/trims/already-earned reviews still run.
    book = [{"symbol": h["symbol"], "qty": h["qty"],
             # avg_price is not on the weekly path (EnginePosition rows load
             # inside stage A); the memo reasons from thesis + market context.
             "avg_price": None,
             "themes": (h.get("source_tags") or {}).get("themes", []),
             "market_value": h["market_value"]} for h in holdings]
    candidates_packet = {
        sym: {
            "dist_200wma": screen.get("dist_200wma"),
            "rsi14": (light_rows.get(sym) or {}).get("rsi14"),
            "fair_value_gap_pct": (light_rows.get(sym) or {}).get("fair_value_gap_pct"),
            "valuation_score": (light_rows.get(sym) or {}).get("valuation_score"),
            "insider_score": (light_rows.get(sym) or {}).get("insider_score"),
            "dark_pool_score": (light_rows.get(sym) or {}).get("dark_pool_score"),
            "short_pct_float": (light_rows.get(sym) or {}).get("short_pct_float"),
            "atr_pct": screen.get("atr_pct"), "price": screen.get("price"),
            "themes": (screen.get("tags") or {}).get("themes", []),
        } for sym, screen in by_symbol.items()
    }
    memo_plan = await _memo_pipeline(db, outlook or {}, book, candidates_packet,
                                     run_date, step)
    memo_ok = memo_plan is not None
    memo_summary = {
        "status": "ok" if memo_ok else "noop",
        "entries_planned": (len(memo_plan["entries"]) + len(memo_plan["adds"]))
                           if memo_ok else 0,
        "rejected": len(memo_plan["rejected"]) if memo_ok else 0,
    }

    # Holdings the memo put up for review: an explicit `review` action, plus
    # every holding whose sourcing theme just MOVED to crowded/priced. They
    # join stage A's trigger map under the name "memo_stage" — earning a
    # review, never a trade.
    #
    # Transition, not state (spec §2). stage_updates records EVERY thesis's
    # stage (it is the persistence contract, correctly), so filtering on "is
    # currently crowded/priced" would re-flag every holding of a sticky crowded
    # theme EVERY week and eat FULL_RUNS_PER_WEEK forever. Only a stage that
    # CHANGED INTO crowded/priced this pass fires; a theme already there last
    # week is silent. prior_stages comes from the pre-memo theme state captured
    # inside the memoized "thesis-memo" step, so the set is replay-stable.
    memo_review_symbols: set = set()
    if memo_ok:
        memo_review_symbols |= set(memo_plan["reviews"])
        prior_stages = memo_plan.get("prior_stages") or {}
        flagged_slugs = {slug for slug, stage in memo_plan["stage_updates"].items()
                         if stage in _MEMO_REVIEW_STAGES
                         and prior_stages.get(slug) != stage}
        if flagged_slugs:
            for h in holdings:
                themes = (h.get("source_tags") or {}).get("themes") or []
                if flagged_slugs & set(themes):
                    memo_review_symbols.add(h["symbol"])

    # ── Stage A: review triggers (pure — a trigger NEVER trades, it earns a
    # review). For each holding compute dd/weight/earnings-recency and collect
    # the fired triggers; journal one review_trigger row per triggered name.
    #
    # The WHOLE stage runs inside ONE memoized step (C2). Inngest re-executes
    # the function body on every step boundary, so an unmemoized trigger scan
    # would recompute — and DRIFT — on each replay: a rung consumed on the first
    # execution vanishes before the post-review replay (killing the ADD), the
    # earnings-cache DataFrame changes shape on the same-day second call
    # (flipping earnings_divergence off), and a staleness/run-up trigger
    # self-negates once its own review persists a fresh row. Memoizing the map
    # pins trigger membership identical across every replay; the review_trigger
    # journals live INSIDE the step so they fire exactly once. Rungs are NOT
    # durably consumed here (C2b) — a budget-deferred review must leave the rung
    # for next week — so dcaState is persisted in stage B only when a review
    # outcome is actually reached. Any failure journals engine_failure and the
    # pass continues with no triggers (never a phantom trade).
    reviewed_this_pass: set = set()

    async def _collect_triggers_stage() -> Dict[str, Dict[str, Any]]:
        import asyncio  # noqa: PLC0415
        from research_swarm.data.market_data_client import (  # noqa: PLC0415
            MarketDataClient,
        )
        from execution.sleeve_service import get_engine_positions  # noqa: PLC0415

        market_client = MarketDataClient()
        pos_rows = {p.symbol: p for p in await get_engine_positions(db, SLEEVE_A)}

        async def _days_since_earnings(sym: str) -> Optional[float]:
            # ANY failure → None: the trigger degrades (no earnings signal), it
            # never blocks. Only fetched when dd ≥ EARNINGS_DIVERGENCE_DD.
            # Robust to BOTH shapes get_earnings_dates returns: a fresh fetch
            # (DatetimeIndex named "Earnings Date") and a same-day cache hit
            # (reset-index RangeIndex + stringified "Earnings Date" column). The
            # old index-only read raised on the cache shape → trigger silently
            # off; running inside the memoized step also pins the answer across
            # replays regardless of who warmed the cache (C2b).
            try:
                edf = await asyncio.to_thread(market_client.get_earnings_dates, sym)
                if edf is None or getattr(edf, "empty", False):
                    return None
                import pandas as pd  # noqa: PLC0415
                idx = edf.index
                if pd.api.types.is_datetime64_any_dtype(idx):
                    raw = list(idx)
                elif "Earnings Date" in getattr(edf, "columns", []):
                    raw = list(pd.to_datetime(edf["Earnings Date"], errors="coerce",
                                              utc=True))
                else:
                    return None
                now_ts = pd.Timestamp(now)
                past = []
                for d in raw:
                    if d is None or pd.isna(d):
                        continue
                    ts = pd.Timestamp(d)
                    ts = (ts.tz_localize("UTC") if ts.tzinfo is None
                          else ts.tz_convert("UTC"))
                    if ts <= now_ts:
                        past.append(ts)
                return float((now_ts - max(past)).days) if past else None
            except Exception:  # noqa: BLE001
                return None

        collected: Dict[str, Dict[str, Any]] = {}
        for h in holdings:
            sym = h["symbol"]
            pos = pos_rows.get(sym)
            close = close_by_symbol.get(sym, 0.0)
            hw = (getattr(pos, "highWaterClose", None) if pos else None) or close
            dd = drawdown(close, hw)
            weight = (h["market_value"] / sleeve_equity) if sleeve_equity > 0 else 0.0
            dse = await _days_since_earnings(sym) if dd >= EARNINGS_DIVERGENCE_DD else None
            names, new_state = collect_triggers(
                dd=dd, days_since_earnings=dse,
                report_age_days=(latest.get(sym) or {}).get("report_age_days"),
                weight=weight,
                dca_state=(getattr(pos, "dcaState", None) if pos else None),
                high_water=hw,
                price=close,
                last_review_price=(latest.get(sym) or {}).get("last_review_price"),
            )
            if sym in memo_review_symbols and "memo_stage" not in names:
                names = list(names) + ["memo_stage"]
            if not names:
                continue
            # JSON-round-trippable (no sets/dates): the step's return value is
            # serialized into the durable log and re-read on every replay.
            collected[sym] = {"triggers": names, "dd": dd, "weight": weight,
                              "dca_state": new_state, "has_position": pos is not None}
            await _journal(
                db, "review_trigger", "info",
                f"{sym}: review triggered — {', '.join(names)}",
                {"symbol": sym, "triggers": names, "dd": round(dd, 4),
                 "weight": round(weight, 4),
                 "report_age_days": (latest.get(sym) or {}).get("report_age_days"),
                 "dist_200wma": by_symbol.get(sym, {}).get("dist_200wma")},
            )
        return collected

    try:
        triggered: Dict[str, Dict[str, Any]] = await _run_step(
            step, "thesis-triggers", _collect_triggers_stage,
        )
    except Exception:  # noqa: BLE001 — never block the pass on trigger failure
        logger.exception("funnel: trigger computation failed")
        await _journal(db, "engine_failure", "warning",
                       "Review-trigger computation failed", {"stage": "triggers"})
        triggered = {}

    # ── Stage B: budget-prioritized reviews. Triggered holdings claim the SAME
    # weekly full-run budget as new entries and run BEFORE them (stalest first).
    # Each paid review is its OWN top-level step.run (nested step.run is a
    # non-retriable SDK error). A deferred (budget-exhausted) review produces no
    # outcome this week. After the loop, refresh verdicts and REBUILD holdings
    # so a fresh SELL/AVOID exits via the plan's sell_verdict path.
    if triggered:
        from prisma import Json  # noqa: PLC0415
        try:
            for sym in sorted(
                triggered,
                key=lambda s: -((latest.get(s) or {}).get("report_age_days") or 999),
            ):
                screen = by_symbol.get(sym, {})
                # R1: Inngest replays the whole body on every step boundary. On
                # the exec AFTER this pass's own persist_full created the full
                # row, re-consulting reuse_or_budget counts that just-created row
                # against FULL_RUNS_PER_WEEK and flips a completed review to
                # "skip" → deferred (zeroing its ADD, dropping its trims, and
                # stranding a rung already consumed). Short-circuit: if the
                # symbol's own (ticker, run_date) row is already full-tier with
                # the funnel marker, it was analyzed THIS pass (the memoized
                # step.run returns the cached analysis; persist_full is
                # idempotent) → treat as reviewed and skip the gate.
                own_row = await db.weeklysignal.find_unique(
                    where={"ticker_runDate": {"ticker": sym, "runDate": run_date}}
                )
                if (own_row is not None and own_row.tier == "full"
                        and _FUNNEL_MARKER in (own_row.escalationReasons or [])):
                    reviewed_this_pass.add(sym)
                    continue
                gate = await reuse_or_budget(db, sym, run_date)
                if gate.get("action") == "skip":
                    await _journal(db, "theme_review", "info",
                                   f"{sym}: review deferred — {gate.get('reason')}",
                                   {"symbol": sym, "stage": "thesis_review",
                                    "reason": gate.get("reason")})
                    triggered[sym]["deferred"] = True
                    continue
                # A review outcome WILL be reached (reuse verdict or paid run) →
                # durably consume any ladder rung NOW (C2b). The skip branch
                # above leaves the rung untouched so it re-fires next week. The
                # overwrite is idempotent (same memoized new_state every replay),
                # so re-running stage B on a replay is safe.
                tinfo = triggered[sym]
                if ("ladder_rung" in tinfo.get("triggers", [])
                        and tinfo.get("has_position") and tinfo.get("dca_state")):
                    try:
                        await db.engineposition.update(
                            where={"sleeve_symbol": {"sleeve": SLEEVE_A, "symbol": sym}},
                            data={"dcaState": Json(tinfo["dca_state"])},
                        )
                    except Exception:  # noqa: BLE001
                        logger.exception("funnel: dcaState persist failed for %s", sym)
                if gate.get("action") == "analyze":
                    if step is not None:
                        result = await step.run(
                            f"thesis-review-{sym.lower()}",
                            lambda s=sym: run_paid_analysis(s),
                        )
                    else:
                        result = await run_paid_analysis(sym)
                    await persist_full(
                        db, sym, run_date, result,
                        float(screen.get("price") or close_by_symbol.get(sym, 0.0) or 0.0),
                        float(screen.get("screen_score") or 0.0),
                    )
                    reviewed_this_pass.add(sym)
            latest = await _load_latest_signals(
                db, list(by_symbol) + list(positions), now,
            )
            holdings = _build_holdings()
        except Exception:  # noqa: BLE001
            logger.exception("funnel: triggered reviews failed")
            await _journal(db, "engine_failure", "warning",
                           "Triggered reviews failed", {"stage": "thesis_reviews"})

    # Theme review: holdings whose EVERY sourcing theme (from persisted tags)
    # is retired. A deferred/failed review NEVER exits — only a completed run.
    # Outage guard (same class as C1): if load_theme_members failed or came
    # back EMPTY, every theme-sourced holding would look "all retired" and a
    # completed review scored with hunting_bonus=0 for themes that are not
    # actually retired could exit a holding on a DATA OUTAGE. Skip the entire
    # stage; theme membership re-resolves next Monday.
    if not active_themes:
        await _journal(db, "theme_review", "warning",
                       "Theme review skipped — theme membership unavailable",
                       {"status": "skipped",
                        "reason": "theme membership unavailable"})
    else:
        await _theme_review(db, run_date, holdings, by_symbol, active_themes, step)

    # Standing (unfilled) shadow buys are pending positions: exclude them from
    # this week's challengers so a patient 14-day limit can't spawn a SECOND
    # order, and reserve their slots against the max-positions cap (I3a).
    try:
        open_buys = await _open_shadow_buys(client)
    except Exception:  # noqa: BLE001 — degrade + journal
        logger.exception("funnel: open shadow buy query failed")
        await _journal(db, "engine_failure", "warning",
                       "Open shadow buy query failed — treating committed capital as 0",
                       {"stage": "decide-and-execute"})
        open_buys = {"notional": 0.0, "symbols": set(), "count": 0}
    open_symbols = open_buys["symbols"]
    committed = open_buys["notional"]
    candidates = [c for c in candidates if c["symbol"] not in open_symbols]
    candidates_by_symbol = {
        s: c for s, c in candidates_by_symbol.items() if s not in open_symbols
    }
    max_positions = max(0, SLEEVE_A_MAX_POSITIONS - open_buys["count"])

    # Entries no longer come from here — the memo is the only buy authority, so
    # plan_decisions is called with NO candidates and its entry_queue comes back
    # empty. Its exits/trims survive untouched (Task 11 strips the signature).
    decisions = plan_decisions(holdings, [], sleeve_equity, max_positions,
                               evictions=False, trim_ceiling=None)

    # Spend envelopes, computed BEFORE stage C so a same-pass ADD draws from
    # them and shrinks what new entries may spend. Deployable = regime fraction
    # × equity − position MV − standing orders, and has NO dependence on this
    # pass's sell proceeds. cash_available starts from the PRE-sells ledger (an
    # ADD is funded from cash on hand); sell proceeds are folded back in below,
    # after the trims/exits execute. Buys move the ledger only at daily fill, so
    # committed standing-order notional comes off BOTH envelopes.
    invested_fraction = SLEEVE_A_INVESTED_FRACTION.get(regime, 0.9)
    position_mv = sum(qty * close_by_symbol.get(sym, 0.0) for sym, qty in positions.items())
    deployable = max(0.0, invested_fraction * sleeve_equity - position_mv - committed)
    cash_available = max(0.0, sleeve_ctx["cash"] - committed)

    # ── Stage C/D: review OUTCOMES (ADD / TRIM / REDUCE). A trigger only ever
    # earns a review; every outcome here is gated on the REVIEW's verdict, never
    # on a price/weight level directly. A symbol already exiting this pass, or
    # whose review was deferred on budget, gets no outcome. Wrapped so a failure
    # journals engine_failure and the pass continues.
    add_spend = 0.0
    try:
        exiting = {e["symbol"] for e in decisions.get("exits", [])}
        for sym, t in triggered.items():
            if t.get("deferred") or sym in exiting:
                continue
            meta = latest.get(sym) or {}
            row = by_symbol.get(sym) or {}
            trigs = set(t["triggers"])
            close = close_by_symbol.get(sym, 0.0)
            # ADD: a dip rung or the earnings-divergence signal, but ONLY while
            # the fresh verdict still says buy — half a fresh entry's notional.
            if ({"ladder_rung", "earnings_divergence"} & trigs
                    and meta.get("verdict") == "buy"):
                conv = next((h["conviction"] for h in holdings
                             if h["symbol"] == sym), 0.0)
                notional = DCA_TRANCHE_FRACTION * size_entry(
                    conv, sleeve_equity,
                    float(row.get("liquidity_adv_usd") or 0.0),
                    float(row.get("atr_pct") or 0.0), deployable, cash_available,
                )
                qty = int(notional // close) if close > 0 else 0
                if qty >= 1 and qty * close >= MIN_TRADE_NOTIONAL:
                    # Submit + journal live in ONE memoized step (I4): stage C
                    # replays outside step.run, so an unmemoized journal would
                    # re-write on every boundary (the coid dedup stops the
                    # ORDER, not the journal row). The step returns the ACTUAL
                    # fill so the ledger debits what really executed (I1): a
                    # rejected market buy debits nothing, a partial debits only
                    # the filled portion, a live fill debits filled_qty *
                    # filled_avg_price (never the Friday-close hint).
                    async def _do_dca_add(sym=sym, qty=qty, close=close,
                                          conv=conv, trigs=t["triggers"]):
                        res = await client.submit_market_buy(
                            symbol=sym, qty=qty, price_hint=close,
                            journal={"reason": "dca_add", "triggers": trigs},
                            client_order_id=f"paper-A-{sym}-{run_date:%Y%m%d}-dca",
                        )
                        fq = float(res.filled_qty or 0.0)
                        fp = res.filled_avg_price
                        if fq > 0 and fp is not None:
                            await _journal(db, "dca_add", "info",
                                           f"{sym}: ladder add {fq:g} @ ~{float(fp):.2f}",
                                           {"symbol": sym, "qty": fq,
                                            "fill_price": float(fp),
                                            "notional": round(fq * float(fp), 2),
                                            "conviction": conv, "triggers": trigs})
                        else:
                            await _journal(db, "engine_failure", "warning",
                                           f"{sym}: DCA add did not fill "
                                           f"(status={res.status})",
                                           {"symbol": sym, "qty": qty,
                                            "status": res.status})
                        return {"filled_qty": fq,
                                "filled_avg_price": float(fp) if fp is not None else None}
                    try:
                        fill = await _run_step(
                            step, f"dca-add-{sym.lower()}", _do_dca_add)
                    except Exception:  # noqa: BLE001
                        logger.exception("funnel: DCA add failed for %s", sym)
                        await _journal(db, "engine_failure", "warning",
                                       f"{sym}: DCA add submit failed", {"symbol": sym})
                        continue
                    spent = (float(fill.get("filled_qty") or 0.0)
                             * float(fill.get("filled_avg_price") or 0.0))
                    deployable = max(0.0, deployable - spent)
                    cash_available = max(0.0, cash_available - spent)
                    add_spend += spent
            # TRIM: concentration above the review weight while the verdict is
            # still buy/hold → shave the excess to the review's stated target
            # (or TRIM_FALLBACK_TARGET). Routed through decisions["trims"].
            elif "concentration" in trigs and meta.get("verdict") in ("buy", "hold"):
                target = _parse_trim_target(meta) or TRIM_FALLBACK_TARGET
                excess = t["weight"] - target
                if excess > 0 and close > 0:
                    qty = round(excess * sleeve_equity / close, 4)
                    decisions.setdefault("trims", []).append(
                        {"symbol": sym, "reason": "risk_trim",
                         "sell_notional": round(qty * close, 2), "origin": "llm_trim",
                         "triggers": t["triggers"]})
            # REDUCE: a fresh review this pass downgraded buy→hold — release one
            # tranche (the DCA ladder's mirror). avoid already fully exits via
            # the plan's sell_verdict path.
            elif (sym in reviewed_this_pass
                  and meta.get("verdict") == "hold"
                  and meta.get("prior_verdict") == "buy"):
                qty = round(REDUCE_TRANCHE_FRACTION * positions.get(sym, 0.0), 4)
                if qty > 0 and close > 0 and qty * close >= MIN_TRADE_NOTIONAL:
                    # Mirror of the TRIM branch: append to decisions["trims"] and
                    # let _execute_sells journal the single thesis_reduce row at
                    # execution time (its reason→report map owns the type).
                    decisions.setdefault("trims", []).append(
                        {"symbol": sym, "reason": "thesis_reduce",
                         "sell_notional": round(qty * close, 2),
                         "origin": "thesis_reduce", "triggers": t["triggers"]})
    except Exception:  # noqa: BLE001
        logger.exception("funnel: review-outcome stage failed")
        await _journal(db, "engine_failure", "warning",
                       "Review-outcome (ADD/TRIM/REDUCE) stage failed",
                       {"stage": "review_outcomes"})

    # Sells (exits + trims — now including any concentration trim / REDUCE
    # tranche) first: their proceeds fund entries. The starting ledger is
    # debited by any ADD that already filled this pass (a market buy fills
    # immediately, unlike a standing limit buy). Wrapped in its own step (no
    # internal step.run) so the shadow sells + cash update are memoized.
    sell_out = await _run_step(
        step, "execute-sells",
        lambda: _execute_sells(
            db, client, decisions, close_by_symbol, positions, run_date,
            max(0.0, sleeve_ctx["cash"] - add_spend),
        ),
    )

    # Fold sell proceeds into the entry cash envelope. Deployable already
    # reflects the ADD draw above; committed standing orders already netted.
    cash_available = max(0.0, sell_out["cash"] - committed)

    other_sleeve_sector_notional = await _sleeve_b_sector_notional(db)

    # Task 10 rewires this to pass planned entries (the full dicts, carrying
    # role/conviction/entry_style) instead of a bare symbol list.
    entry_queue = ([e["ticker"] for e in memo_plan["entries"] + memo_plan["adds"]]
                   if memo_ok else [])

    placed = await _handshake_and_enter(
        db, client, entry_queue, candidates_by_symbol, run_date,
        sleeve_equity, deployable, cash_available, holdings,
        screened.get("sector_by_symbol", {}), other_sleeve_sector_notional,
        sleeve_ctx.get("allow_buys", True), step,
    )

    # NOTE: no cash write for buys here. A shadow buy is a limit order that
    # may never fill; the daily cron's sleeve-a-fills step is the SOLE cash
    # mover for buys (deducts at fill, nothing to refund on expiry). Sells
    # fill immediately at submit, so their cash already moved inside
    # _execute_sells above. Deducting placed buy notionals at submit would
    # double-count against the fill-time deduction and strand cash on expiry.

    # Report ACTUAL spend, not the caps: full runs commissioned this pass (the
    # handshake + theme review may have billed) and the real light count.
    try:
        full_used = await full_runs_used(db, run_date)
    except Exception:  # noqa: BLE001
        full_used = None

    return {
        "decisions": decisions, "guardrail_notes": decisions.get("notes", []),
        "placed": placed, "sells": sell_out, "memo": memo_summary,
        "budget_used": {"full_runs_used": full_used,
                        "full_runs_cap": FULL_RUNS_PER_WEEK,
                        "light_runs": lights.get("spent", 0)},
        "reviews": {
            "triggered": {s: t["triggers"] for s, t in triggered.items()},
            "reviewed": sorted(reviewed_this_pass),
            "deferred": sorted(s for s, t in triggered.items() if t.get("deferred")),
            "add_notional": round(add_spend, 2),
        },
        "sleeve_equity": round(sleeve_equity, 2),
    }


async def _theme_review(
    db, run_date: datetime, holdings: List[Dict[str, Any]],
    by_symbol: Dict[str, Any], active_themes: set, step,
) -> None:
    """Per holding whose EVERY sourcing theme (from PERSISTED sourceTags) is
    retired: re-run research and re-score with hunting_bonus=0; flag
    theme_review_failed only when a COMPLETED review lands below the floor.

    Degradation must never generate a trade (C1b): when the handshake returns
    no signals (budget exhausted or a failed persist), journal `deferred` and
    leave the holding untouched — the name stays and re-competes next week."""
    flagged = [h for h in holdings if _sourcing_themes_retired(h, active_themes)]
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
            elif gate.get("action") == "skip":
                signals = None  # budget exhausted — defer, do NOT fail
            else:
                signals = gate.get("signals")
        except Exception:  # noqa: BLE001
            logger.exception("funnel theme review failed for %s", sym)
            await _journal(db, "engine_failure", "warning",
                           f"{sym}: theme review failed", {"symbol": sym})
            continue

        if signals is None:
            # No completed review this pass. Never exit on degradation.
            reason = gate.get("reason") if gate.get("action") == "skip" else "no_signals"
            await _journal(db, "theme_review", "info",
                           f"{sym}: theme review deferred — {reason}",
                           {"symbol": sym, "status": "deferred", "reason": reason})
            continue

        conv_input = _conviction_input_from_signals(signals, screen)
        conv_input["hunting_bonus"] = 0.0  # retired ground: no hunting credit
        conv = compute_conviction(conv_input)
        failed = conv["vetoed"] or conv["score"] < RETIRED_THEME_EXIT_CONVICTION
        h["theme_review_failed"] = failed
        await _journal(db, "theme_review", "info",
                       f"{sym}: theme review — {'exit' if failed else 'keep'}",
                       {"symbol": sym, "conviction": conv["score"], "status": "completed",
                        "floor": RETIRED_THEME_EXIT_CONVICTION, "failed": failed})


def _sourcing_themes_retired(holding: Dict[str, Any], active_themes: set) -> bool:
    """Flag a holding for theme review only when its PERSISTED sourceTags show
    ≥1 theme, ALL of those themes are now retired (absent from the active
    theme set), and it carries no watchlist tag. Holdings with no stored tags
    (pre-fix rows) or industry-only tags are NEVER flagged — industries rotate
    out of the top-5 weekly by design and must not trigger a paid review."""
    tags = holding.get("source_tags") or {}
    themes = tags.get("themes") or []
    if not themes or tags.get("watchlist"):
        return False
    return all(t not in active_themes for t in themes)


def _all_themes_retired(holding: Dict[str, Any], by_symbol: Dict[str, Any]) -> bool:
    """Deprecated (pre-provenance). Retained only so nothing imports it and
    breaks; the live path uses _sourcing_themes_retired against stored tags."""
    screen = by_symbol.get(holding["symbol"], {})
    tags = (screen.get("tags") or {})
    themes = tags.get("themes", [])
    return bool(tags.get("holding")) and not themes and not tags.get("watchlist")


async def _open_shadow_buys(client) -> Dict[str, Any]:
    """ONE query → {notional, symbols, count} for standing (unfilled) Sleeve A
    buys. Buys move cash only when the daily cron fills them, so an open order
    is committed capital the cash ledger doesn't yet reflect AND a pending
    position that must reserve a slot and block a duplicate challenger (I3).

    Goes through the broker's OWN get_open_orders() rather than hand-rolling a
    DB query: ShadowBrokerClient's rows are status="shadow_open" but
    AlpacaFunnelBroker's (the live paper broker, owner ruling 2026-07-10) are
    status="open" — a hardcoded "shadow_open" filter went blind the moment
    Sleeve A traded live, silently un-gating the duplicate-order check this
    function exists to enforce."""
    orders = await client.get_open_orders()
    total = 0.0
    symbols: set = set()
    for o in orders:
        if getattr(o, "side", "buy") != "buy":
            continue
        sym = getattr(o, "symbol", None)
        if sym:
            symbols.add(sym)
        notional = getattr(o, "notional", None)
        if notional is not None:
            total += float(notional)
        else:  # legacy/partial rows: reconstruct from qty × limit
            total += float(getattr(o, "qty", 0.0) or 0.0) * float(
                getattr(o, "limitPrice", 0.0) or 0.0
            )
    return {"notional": round(total, 2), "symbols": symbols, "count": len(symbols)}


async def _open_shadow_buy_notional(client) -> float:
    """Back-compat thin wrapper — total notional only."""
    return (await _open_shadow_buys(client))["notional"]


async def _latest_full_signal_id(db, symbol: str) -> Optional[str]:
    """Best-effort id of the symbol's most recent full WeeklySignal (reportRef
    audit column). None when unavailable — never load-bearing for a decision."""
    try:
        row = await db.weeklysignal.find_first(
            where={"ticker": symbol, "tier": "full"}, order={"runDate": "desc"},
        )
    except Exception:  # noqa: BLE001
        return None
    return getattr(row, "id", None) if row is not None else None


async def _load_position_source_tags(db) -> Dict[str, Dict[str, Any]]:
    """Per-symbol PERSISTED sourceTags for Sleeve A positions (C1a). These are
    copied onto the EnginePosition at fill time; the theme review reads them so
    it flags only theme-sourced holdings, never industry-only ones."""
    out: Dict[str, Dict[str, Any]] = {}
    try:
        rows = await db.engineposition.find_many(where={"sleeve": SLEEVE_A})
    except Exception:  # noqa: BLE001 — degrade; no tags ⇒ nothing flagged
        logger.exception("funnel: position source-tags query failed")
        return out
    for r in rows:
        sym = getattr(r, "symbol", None)
        tags = getattr(r, "sourceTags", None)
        if sym and isinstance(tags, dict):
            out[sym] = tags
    return out


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
        logger.exception("funnel: Sleeve B sector notional lookup failed")
        try:
            await _journal(db, "engine_failure", "warning",
                           "Sleeve B sector-notional lookup failed — cross-sleeve "
                           "sector cap may be under-enforced this pass",
                           {"stage": "sleeve-b-sector-notional"})
        except Exception:  # noqa: BLE001
            pass
    return out


try:
    sleeve_a_funnel = _register_inngest_function()
except Exception:
    # inngest pip SDK not available (e.g. unit tests) — no-op export.
    sleeve_a_funnel = None  # type: ignore[assignment]
