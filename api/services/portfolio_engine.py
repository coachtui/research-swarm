"""
Portfolio Engine Service — translates report decision intelligence into portfolio actions.

Reads positions from DB → fetches latest StockResult per ticker → reads the report's
decision_intelligence (tranche_plan, initiation_decision, conviction_position) →
generates contextual action recommendations → writes PortfolioAction records to DB.

Called by:
  - Manual trigger (POST /api/portfolio/{id}/engine/run)
  - Rebalance endpoint

Usage:
    from api.services.portfolio_engine import run_portfolio_engine

    result = await run_portfolio_engine(portfolio_id, "monthly")
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

SIGNAL_MAX_AGE_DAYS = 90  # StockResults older than this are treated as "no signal"

from api.lib.db import get_db

logger = logging.getLogger(__name__)


def _parse_full_output(raw: Any, moat_score: float | None = None) -> dict:
    """
    Parse fullOutput from DB (stored as JSON string) and apply DI enrichment if needed.

    decision_intelligence is computed on-the-fly in the runs endpoint but never
    persisted. We re-apply the enrichment here so the engine can read conviction
    weights, tranche plans, and thesis break conditions.
    """
    if isinstance(raw, dict):
        fo = raw
    elif isinstance(raw, str):
        try:
            fo = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return {}
    else:
        return {}

    if not fo.get("decision_intelligence") and moat_score is not None:
        try:
            from api.lib.decision_intelligence import enrich_with_decision_intelligence
            fo = enrich_with_decision_intelligence(fo, moat_score)
        except Exception as exc:
            logger.warning("DI enrichment failed in engine: %s", exc)

    return fo


def _moat_fallback_weight(moat_score: float | None) -> float | None:
    """
    Deterministic weight derivation from moat score alone.

    Used when the DI enrichment pipeline fails to produce a conviction_position
    with recommended_pct. Returns None for unknown / low-moat positions so the
    engine does not override a user's deliberate 0% target.
    """
    if moat_score is None:
        return None
    if moat_score >= 8.5:
        return 0.08
    if moat_score >= 7.0:
        return 0.06
    if moat_score >= 5.0:
        return 0.04
    if moat_score >= 3.5:
        return 0.02
    return None


ENGINE_VERSION = "4.0.0"


# ── Cycle Helpers ───────────────────────────────────────────────────────────


def _compute_trigger_cycle(cycle_type: str) -> str:
    now = datetime.now(timezone.utc)
    if cycle_type == "monthly":
        return f"monthly_{now.year}_{now.month:02d}"
    elif cycle_type == "quarterly":
        quarter = (now.month - 1) // 3 + 1
        return f"quarterly_{now.year}_Q{quarter}"
    elif cycle_type == "annual":
        return f"annual_{now.year}"
    return f"{cycle_type}_{now.year}_{now.month:02d}"


def _next_cycle_expiry(trigger_cycle: str) -> datetime:
    now = datetime.now(timezone.utc)
    if "monthly" in trigger_cycle:
        if now.month == 12:
            return datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
        return datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)
    elif "quarterly" in trigger_cycle:
        quarter = (now.month - 1) // 3 + 1
        next_q_month = quarter * 3 + 1
        if next_q_month > 12:
            return datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
        return datetime(now.year, next_q_month, 1, tzinfo=timezone.utc)
    return datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)


# ── Report Data Extraction ──────────────────────────────────────────────────


def _extract_di_data(full_output: dict) -> dict:
    """
    Pull the decision_intelligence block and its sub-components out of fullOutput.

    Returns a flat dict with all the fields we need for action generation.
    Returns None-safe values for all optional fields.
    """
    di = full_output.get("decision_intelligence") or {}
    tranche = di.get("tranche_plan") or {}
    init_dec = di.get("initiation_decision") or {}
    conviction = di.get("conviction_position") or {}
    dvrg = di.get("divergence_overlay") or {}
    verdict = (full_output.get("verdict") or "hold").lower()

    fund = full_output.get("fundamentalist_output") or {}
    valuation = fund.get("valuation") or {}
    fair_value_raw = (
        valuation.get("fair_value")
        or valuation.get("intrinsic_value")
        or full_output.get("fair_value")
    )
    fair_value = float(fair_value_raw) if fair_value_raw else None

    quant = full_output.get("quant_output") or {}
    ti = quant.get("technical_indicators") or {}
    ma = ti.get("moving_averages") or {}
    report_price_raw = (
        ma.get("current_price") or ti.get("current_price") or quant.get("current_price")
    )
    report_price = float(report_price_raw) if report_price_raw else None

    return {
        "tranche": tranche,
        "init_dec": init_dec,
        "conviction": conviction,
        "dvrg": dvrg,
        "verdict": verdict,
        "fair_value": fair_value,
        "report_price": report_price,
        # Convenience extracts
        "initiation_status": init_dec.get("status") or "WAIT",
        "starter_pct": init_dec.get("starter_allocation_percent"),
        "initiation_score": init_dec.get("initiation_score"),
        "initiation_rationale": init_dec.get("rationale_summary"),
        "required_entry_zone": init_dec.get("required_entry_zone") or [],
        "max_pct": conviction.get("max_pct"),
        "recommended_pct": conviction.get("recommended_pct"),
        "stage": tranche.get("stage"),
        "current_position_pct": tranche.get("current_position_pct"),
        "thesis_break_active": tranche.get("thesis_break_active", False),
        "thesis_break_conditions": tranche.get("thesis_break_conditions") or [],
        "stage2_add_pct": tranche.get("stage2_add_pct"),
        "stage3_add_pct": tranche.get("stage3_add_pct"),
        "next_add_size_pct": tranche.get("next_add_size_pct"),
        "next_add_trigger_conditions": tranche.get("next_add_trigger_conditions") or [],
        "next_add_note": tranche.get("next_add_note") or "",
        "dvrg_mode": dvrg.get("dvrg_mode"),
        "divergence_score": dvrg.get("divergence_score"),
        "divergence_phase": dvrg.get("divergence_phase"),
    }


def _build_signal_snapshot(di: dict, current_alloc: float) -> dict:
    """Build the JSON snapshot stored on each PortfolioAction for UI display."""
    active_breaks = [
        c for c in di["thesis_break_conditions"] if c.get("active")
    ]
    snapshot: dict[str, Any] = {
        "stage": di["stage"],
        "initiation_status": di["initiation_status"],
        "initiation_score": di["initiation_score"],
        "initiation_rationale": di["initiation_rationale"],
        "starter_allocation_pct": di["starter_pct"],
        "max_position_pct": di["max_pct"],
        "recommended_pct": di["recommended_pct"],
        "current_position_pct": di["current_position_pct"],
        "current_allocation_pct": round(current_alloc * 100, 2),
        "thesis_break_active": di["thesis_break_active"],
        "active_thesis_breaks": active_breaks,
        "next_add_trigger_conditions": di["next_add_trigger_conditions"],
        "next_add_note": di["next_add_note"],
        "dvrg_mode": di["dvrg_mode"],
        "divergence_score": di["divergence_score"],
        "divergence_phase": di["divergence_phase"],
        "report_verdict": di["verdict"],
        "fair_value": di["fair_value"],
    }
    # Strip None values to keep the snapshot clean
    return {k: v for k, v in snapshot.items() if v is not None}


# ── Action Plan Generator ───────────────────────────────────────────────────


def generate_action_plan(
    position,
    stock_result,
    current_alloc: float,
    portfolio_id: str,
) -> list[dict]:
    """
    Generate a conditional action plan for a position by reading the report's
    decision intelligence — tranche_plan, initiation_decision, conviction_position.

    current_alloc: fraction (0.0–1.0) = shares × lastKnownPrice / total_portfolio_value.

    Returns a list of action dicts (not yet persisted). Items with
    parentActionId="__PARENT__" are children; the caller must replace that
    sentinel with the DB-assigned id of the preceding action.

    Returns [] when no action is warranted (hold at correct stage).
    """
    ticker = position.ticker

    def _action(
        action_type: str,
        weight_delta: float,
        trigger_cond: str,
        trigger_price: Optional[float],
        reason_text: str,
        reason_codes: Optional[list[str]] = None,
        parent: Optional[str] = None,
        snapshot: Optional[dict] = None,
    ) -> dict:
        a: dict = {
            "portfolioId": portfolio_id,
            "ticker": ticker,
            "actionType": action_type,
            "weightDelta": round(weight_delta, 4),
            "reasonCodes": reason_codes or [action_type.lower()],
            "reasonText": reason_text,
            "triggerCondition": trigger_cond,
            "triggerPrice": round(trigger_price, 2) if trigger_price is not None else None,
            "parentActionId": parent,
            "status": "pending",
        }
        if snapshot is not None:
            a["signalSnapshot"] = json.dumps(snapshot)
        return a

    # ── No report available ──────────────────────────────────────────────────
    if stock_result is None:
        return [_action(
            "HOLD", 0.0, "immediate", None,
            "No recent analysis available — run a report on this ticker to get recommendations",
            reason_codes=["no_analysis"],
        )]

    full_output = _parse_full_output(stock_result.fullOutput, stock_result.moatScore)

    # If the report has no decision_intelligence (very old format), fall back minimally
    di_block = full_output.get("decision_intelligence")
    if not di_block:
        verdict = (full_output.get("verdict") or "hold").lower()
        if verdict in ("avoid", "sell") and current_alloc > 0.02:
            return [_action(
                "TRIM_CAP", -current_alloc / 2.0, "immediate", None,
                f"Report verdict: {verdict.upper()} — consider reducing exposure. Run a fresh report for full analysis.",
                reason_codes=["verdict_reduce"],
            )]
        return []

    di = _extract_di_data(full_output)
    price = position.lastKnownPrice or di["report_price"] or 0.0
    snapshot = _build_signal_snapshot(di, current_alloc)

    # ── Watch-only position (no shares held) ────────────────────────────────
    is_watch = (position.shares or 0.0) == 0.0

    if is_watch:
        return _watch_only_plan(di, price, snapshot, _action)

    # ── Has an existing position ────────────────────────────────────────────

    # 1. Thesis integrity check — reduce position if break conditions firing
    if di["thesis_break_active"]:
        active_breaks = [c for c in di["thesis_break_conditions"] if c.get("active")]
        break_labels = "; ".join(
            f"{b['label']} ({b['current']} vs threshold {b['threshold']})"
            for b in active_breaks
        )
        trim_amount = current_alloc * 0.5  # tranche framework: reduce by 50%
        return [_action(
            "TRIM_THESIS", -trim_amount, "immediate", None,
            f"Integrity check: {break_labels}. Reducing by 50% until conditions improve.",
            reason_codes=["thesis_break"],
            snapshot=snapshot,
        )]

    max_pct = di["max_pct"]
    max_frac = (max_pct / 100.0) if max_pct else 0.10  # default 10%

    # 2. Above policy cap — trim to max
    if current_alloc > max_frac + 0.02:
        excess = current_alloc - max_frac
        # Trim near fair value if above it, otherwise near current price +5%
        fv = di["fair_value"]
        trim_trigger = (fv * 0.98) if (fv and fv > price) else (price * 1.05 if price else None)
        return [_action(
            "TRIM_CAP", -excess, "price_above", trim_trigger,
            f"Position at {current_alloc:.1%} exceeds policy cap of {max_pct:.0f}% — "
            f"trim {excess:.1%} near fair value",
            reason_codes=["cap_trim"],
            snapshot=snapshot,
        )]

    # 3. Tranche-based add/hold logic
    stage = di["stage"]
    current_pos_pct = di["current_position_pct"]

    # No tranche plan in this report (WATCHLIST/WAIT reports return tranche_plan=None)
    if stage is None or current_pos_pct is None:
        return _fallback_verdict_plan(di, current_alloc, price, snapshot, _action)

    target_frac = current_pos_pct / 100.0

    # Below current stage target — recommend adding to reach it
    if current_alloc < target_frac - 0.01:
        gap = target_frac - current_alloc
        stage_note = f"Stage {stage} target is {target_frac:.1%}"
        conditions = di["next_add_trigger_conditions"] if stage == 1 else []
        unmet = [c for c in conditions if not c.get("met", False)]

        if unmet:
            unmet_text = "; ".join(c["label"] for c in unmet[:2])
            return [_action(
                "ADD_TIER_20", gap, "catalyst_confirmed", None,
                f"{stage_note} — add {gap:.1%} when: {unmet_text}",
                reason_codes=[f"add_stage{stage}"],
                snapshot=snapshot,
            )]
        else:
            # Conditions met — immediate add
            return [_action(
                "ADD_TIER_20", gap, "immediate", None,
                f"{stage_note} — conditions met, add {gap:.1%} to reach stage target",
                reason_codes=[f"add_stage{stage}"],
                snapshot=snapshot,
            )]

    # At or above current stage target — show path to next stage (if not at max)
    if stage < 3:
        next_add_pct = di["next_add_size_pct"]
        next_add_frac = (next_add_pct / 100.0) if next_add_pct else 0.0
        next_conds = di["next_add_trigger_conditions"]
        note = di["next_add_note"]

        if next_add_frac > 0.005 and next_conds:
            unmet = [c for c in next_conds if not c.get("met", False)]
            met = [c for c in next_conds if c.get("met", False)]
            unmet_text = "; ".join(c["label"] for c in unmet[:2]) if unmet else "all conditions met"
            met_count = len(met)
            total_count = len(next_conds)

            # Determine trigger type from conditions
            trigger_cond = "catalyst_confirmed"
            trigger_price = None
            for c in next_conds:
                if "Price in lower valuation band" in c.get("label", "") and not c.get("met"):
                    trigger_cond = "price_below"
                    # Extract price from detail if available
                    detail = c.get("detail", "")
                    if "FV Low $" in detail:
                        try:
                            trigger_price = float(detail.split("FV Low $")[1].split()[0])
                        except (ValueError, IndexError):
                            pass
                    break

            return [_action(
                "ADD_TIER_20", next_add_frac, trigger_cond, trigger_price,
                f"Stage {stage + 1} add ({next_add_frac:.1%}): {note} · "
                f"{met_count}/{total_count} conditions met · Waiting for: {unmet_text}",
                reason_codes=[f"add_stage{stage + 1}"],
                snapshot=snapshot,
            )]

    # Full position at max stage — hold
    return []


def _watch_only_plan(
    di: dict,
    price: float,
    snapshot: dict,
    _action,
) -> list[dict]:
    """Generate action plan for a watch-only (no shares) position."""
    init_status = di["initiation_status"]
    rationale = di["initiation_rationale"] or f"Report verdict: {di['verdict'].upper()}"

    starter_pct = di["starter_pct"] or di["recommended_pct"] or 5.0
    starter_frac = starter_pct / 100.0

    entry_zone = di["required_entry_zone"]
    entry_price = entry_zone[0] if entry_zone else (price * 0.95 if price else None)

    if init_status == "INITIATE":
        stage2_add_pct = di["stage2_add_pct"] or 0.0
        stage2_frac = stage2_add_pct / 100.0
        stage2_conds = di["next_add_trigger_conditions"]
        note = di["next_add_note"]

        actions = [_action(
            "INITIATE", starter_frac, "immediate", None,
            f"Report: INITIATE — {rationale}. Open starter position ({starter_pct:.1f}%).",
            reason_codes=["initiate"],
            snapshot=snapshot,
        )]

        if stage2_frac > 0.005 and stage2_conds:
            cond_summary = "; ".join(c["label"] for c in stage2_conds[:2]) if stage2_conds else note
            actions.append(_action(
                "ADD_TIER_20", stage2_frac, "catalyst_confirmed", entry_price,
                f"Stage 2 add ({stage2_frac:.1%}): {note} · {cond_summary}",
                reason_codes=["add_stage2"],
                parent="__PARENT__",
            ))

        return actions

    if init_status == "WATCHLIST":
        next_conds = di["next_add_trigger_conditions"]
        cond_text = "; ".join(c["label"] for c in next_conds[:2]) if next_conds else "conditions improving"
        return [_action(
            "HOLD", 0.0, "catalyst_confirmed", entry_price,
            f"Monitoring — {rationale}. Entry triggers: {cond_text}",
            reason_codes=["watchlist"],
            snapshot=snapshot,
        )]

    # WAIT
    return [_action(
        "HOLD", 0.0, "catalyst_confirmed", None,
        f"Report says wait — {rationale}",
        reason_codes=["wait"],
        snapshot=snapshot,
    )]


def _fallback_verdict_plan(
    di: dict,
    current_alloc: float,
    price: float,
    snapshot: dict,
    _action,
) -> list[dict]:
    """Fallback when tranche_plan is absent — use verdict + fair value."""
    verdict = di["verdict"]
    fv = di["fair_value"]
    rationale = di["initiation_rationale"] or f"Report verdict: {verdict.upper()}"

    if verdict in ("avoid", "sell") and current_alloc > 0.02:
        trim_target = (fv * 0.98) if (fv and fv > price) else (price * 1.05 if price else None)
        return [_action(
            "TRIM_CAP", -current_alloc / 2.0, "immediate", trim_target,
            f"Report verdict: {verdict.upper()} — {rationale}. Consider reducing exposure.",
            reason_codes=["verdict_reduce"],
            snapshot=snapshot,
        )]

    return []


# ── Main Engine Entry Point ─────────────────────────────────────────────────


async def run_portfolio_engine(
    portfolio_id: str,
    cycle_type: str,
) -> dict:
    """
    Run the portfolio engine for a single portfolio.

    Steps:
      1. Load portfolio + positions
      2. Compute real allocation per position (shares × price / total)
      3. Fetch latest StockResult per ticker
      4. Generate action plan per position from report decision intelligence
      5. Expire previous pending actions
      6. Write new PortfolioAction records (with parent-child chain)
      7. Update position thesis states
      8. Return summary
    """
    db = await get_db()

    portfolio = await db.portfolio.find_unique(
        where={"id": portfolio_id},
        include={"positions": True},
    )
    if not portfolio:
        raise ValueError(f"Portfolio {portfolio_id} not found")

    if not portfolio.positions:
        return {
            "portfolio_id": portfolio_id,
            "cycle_type": cycle_type,
            "actions_created": 0,
            "diagnostics": {"message": "No positions in portfolio"},
        }

    # 2. Compute real allocation fractions
    from api.services.allocation import compute_portfolio_total
    cash = portfolio.cashBalance or 0.0
    total_value = compute_portfolio_total(portfolio.positions, cash)
    alloc_map: dict[str, float] = {}
    if total_value > 0:
        for pos in portfolio.positions:
            if pos.lastKnownPrice and pos.shares:
                alloc_map[pos.ticker] = (pos.shares * pos.lastKnownPrice) / total_value

    # 3. Fetch latest StockResult per ticker
    results_map: dict[str, Any] = {}
    for pos in portfolio.positions:
        result = await db.stockresult.find_first(
            where={"ticker": pos.ticker, "status": "completed"},
            order={"createdAt": "desc"},
        )
        if not result or not result.fullOutput:
            continue
        age_days = (datetime.now(timezone.utc) - result.createdAt).days
        if age_days > SIGNAL_MAX_AGE_DAYS:
            logger.info(
                "StockResult for %s is %d days old (> %d) — skipping",
                pos.ticker, age_days, SIGNAL_MAX_AGE_DAYS,
            )
            continue
        results_map[pos.ticker] = result

    # 4 + 5. Expire old pending actions
    trigger_cycle = _compute_trigger_cycle(cycle_type)
    expires_at = _next_cycle_expiry(trigger_cycle)

    await db.portfolioaction.update_many(
        where={"portfolioId": portfolio_id, "status": "pending"},
        data={"status": "expired"},
    )

    # 6. Generate and persist actions per position
    actions_created = 0
    thesis_breaks: set[str] = set()
    suggested_weights: dict[str, float] = {}  # ticker → engineSuggestedWeight (fraction)

    for pos in portfolio.positions:
        stock_result = results_map.get(pos.ticker)
        current_alloc = alloc_map.get(pos.ticker, 0.0)

        # Extract engineSuggestedWeight from conviction_position.recommended_pct,
        # falling back to moat-derived weight when DI is missing or incomplete.
        if stock_result and stock_result.fullOutput:
            fo = _parse_full_output(stock_result.fullOutput, stock_result.moatScore)
            di_block = fo.get("decision_intelligence") or {}
            conv = di_block.get("conviction_position") or {}
            rec_pct = conv.get("recommended_pct")
            if rec_pct is not None:
                suggested_weights[pos.ticker] = float(rec_pct) / 100.0
                logger.info(
                    "Engine: %s suggested weight = %.1f%% (source=DI)",
                    pos.ticker,
                    float(rec_pct),
                )
            else:
                fallback = _moat_fallback_weight(stock_result.moatScore)
                if fallback is not None:
                    suggested_weights[pos.ticker] = fallback
                    logger.info(
                        "Engine: %s suggested weight = %.1f%% (source=moat_fallback, moat=%s)",
                        pos.ticker,
                        fallback * 100,
                        stock_result.moatScore,
                    )
                else:
                    logger.warning(
                        "Engine: %s no suggested weight — no DI conviction and moat=%s "
                        "(leaving targetWeight unchanged)",
                        pos.ticker,
                        stock_result.moatScore,
                    )

        plan = generate_action_plan(pos, stock_result, current_alloc, portfolio_id)

        parent_id: Optional[str] = None
        for i, action_dict in enumerate(plan):
            if action_dict.get("parentActionId") == "__PARENT__":
                action_dict["parentActionId"] = parent_id

            action_dict["triggerCycle"] = trigger_cycle
            action_dict["engineVersion"] = ENGINE_VERSION
            action_dict["expiresAt"] = expires_at

            created = await db.portfolioaction.create(data=action_dict)
            if i == 0:
                parent_id = created.id
            actions_created += 1

            if action_dict["actionType"] == "TRIM_THESIS":
                thesis_breaks.add(pos.ticker)

    # 7. Update position thesis states + engineSuggestedWeight
    await _update_position_states(
        db, portfolio_id, portfolio.positions, thesis_breaks, suggested_weights
    )

    return {
        "portfolio_id": portfolio_id,
        "cycle_type": cycle_type,
        "trigger_cycle": trigger_cycle,
        "actions_created": actions_created,
        "positions_analyzed": len(portfolio.positions),
        "with_reports": len(results_map),
        "without_reports": len(portfolio.positions) - len(results_map),
    }


# ── Position State Update ───────────────────────────────────────────────────


async def _update_position_states(
    db,
    portfolio_id: str,
    positions,
    thesis_breaks: set[str],
    suggested_weights: dict[str, float] | None = None,
) -> None:
    """
    Update thesisState and engineSuggestedWeight based on engine output.

    - engineSuggestedWeight: set from report's conviction_position.recommended_pct
    - Positions with a TRIM_THESIS action → thesisState = 'at_risk'
    - Positions without a break (but with a report) → thesisState = 'intact'
    - Positions without a report → unchanged (don't auto-break on missing data)
    """
    suggested_weights = suggested_weights or {}

    for pos in positions:
        update_data: dict = {}

        # Write engineSuggestedWeight from report. Also sync targetWeight so the UI
        # shows the PM's conviction target — user can manually override via edit modal.
        if pos.ticker in suggested_weights:
            update_data["engineSuggestedWeight"] = suggested_weights[pos.ticker]
            update_data["targetWeight"] = suggested_weights[pos.ticker]

        if pos.ticker in thesis_breaks:
            update_data["thesisState"] = "at_risk"
        elif pos.thesisState in ("broken", "disqualified", "at_risk"):
            # Auto-heal if no break fired this run
            update_data["thesisState"] = "intact"

        if update_data:
            await db.position.update(
                where={"id": pos.id},
                data=update_data,
            )


# ── Signal-Driven Action Plans (public for rebalance endpoint) ──────────────

# Expose generate_action_plan at module level (already defined above).
# Also expose the classify helper for the rebalance route to use directly.


def classify_posture(position, current_alloc: float, stock_result) -> str:
    """
    Classify a position's posture for display purposes.

    Returns one of: watch_only | thesis_at_risk | over_cap | below_target | at_target | hold
    """
    if (position.shares or 0.0) == 0.0:
        return "watch_only"

    if not stock_result or not stock_result.fullOutput:
        return "hold"

    fo = _parse_full_output(stock_result.fullOutput, stock_result.moatScore)
    di_block = fo.get("decision_intelligence")
    if not di_block:
        return "hold"

    di = _extract_di_data(fo)

    if di["thesis_break_active"]:
        return "thesis_at_risk"

    max_pct = di["max_pct"]
    if max_pct and current_alloc > (max_pct / 100.0) + 0.02:
        return "over_cap"

    current_pos_pct = di["current_position_pct"]
    if current_pos_pct and current_alloc < (current_pos_pct / 100.0) - 0.01:
        return "below_target"

    stage = di["stage"]
    if stage is not None and stage < 3:
        return "at_target"

    return "hold"
