"""
Portfolio Engine Service — runs the CompounderEngine against persisted portfolio state.

Reads positions from DB → converts to engine data contracts → runs engine →
writes PortfolioAction records back to DB → updates position state.

Called by:
  - Cron scheduler (monthly/quarterly/annual)
  - Manual trigger (POST /api/portfolio/{id}/engine/run)

Usage:
    from api.services.portfolio_engine import run_portfolio_engine

    result = await run_portfolio_engine(portfolio_id, "monthly")
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from typing import Optional

from api.lib.compounder_owner_v3 import (
    CompounderEngine,
    OwnerAction,
    OwnerConfig,
    PortfolioPosition as EnginePosition,
    SignalInput,
)
from api.lib.db import get_db
from api.services.signal_extractor import extract_signal_from_full_output

logger = logging.getLogger(__name__)

ENGINE_VERSION = "3.1.0"


# ── Action Type Mapping ─────────────────────────────────────────────────────


def _map_action_type(action: OwnerAction) -> str:
    """
    Map engine OwnerAction to granular PortfolioAction type.

    Engine produces: ADD, TRIM, SELL, BUY, HOLD
    We refine to: INITIATE, ADD_TIER_20..50, TRIM_EUPHORIA, TRIM_CAP,
                  EXIT_THESIS, REPLACE, HOLD
    """
    if action.action == "ADD":
        dd = action.drawdown_pct
        if dd is not None:
            if dd <= -0.50:
                return "ADD_TIER_50"
            if dd <= -0.40:
                return "ADD_TIER_40"
            if dd <= -0.30:
                return "ADD_TIER_30"
            if dd <= -0.20:
                return "ADD_TIER_20"
        return "ADD_TIER_20"  # Default add if drawdown not tracked

    if action.action == "TRIM":
        # Distinguish euphoria trims from cap trims based on reason
        if "200DMA" in (action.reason or ""):
            return "TRIM_EUPHORIA"
        return "TRIM_CAP"

    if action.action == "SELL":
        if "THESIS BREAK" in (action.reason or "").upper():
            return "EXIT_THESIS"
        if "Replaced by" in (action.reason or ""):
            return "REPLACE"
        return "EXIT_THESIS"  # Default sell = thesis break

    if action.action == "BUY":
        if "replaces" in (action.reason or "").lower():
            return "REPLACE"
        return "INITIATE"

    return "HOLD"


def _extract_reason_codes(action: OwnerAction) -> list[str]:
    """Extract structured reason codes from OwnerAction."""
    codes = []
    reason = (action.reason or "").lower()

    if "drawdown" in reason or "dd" in reason:
        codes.append("drawdown")
    if "thesis break" in reason or "thesis_break" in reason:
        codes.append("thesis_break")
    if "growth collapse" in reason:
        codes.append("growth_collapse")
    if "capital destruction" in reason:
        codes.append("capital_destruction")
    if "structural break" in reason:
        codes.append("structural_break")
    if "200dma" in reason or "euphoria" in reason:
        codes.append("euphoria")
    if "replaced" in reason or "replaces" in reason:
        codes.append("replacement")
    if "durable" in reason or "compounder" in reason:
        codes.append("durable")
    if "filling" in reason:
        codes.append("slot_fill")

    if action.drawdown_pct is not None:
        dd = abs(action.drawdown_pct)
        if dd >= 0.50:
            codes.append("drawdown_50pct")
        elif dd >= 0.40:
            codes.append("drawdown_40pct")
        elif dd >= 0.30:
            codes.append("drawdown_30pct")
        elif dd >= 0.20:
            codes.append("drawdown_20pct")

    return codes or ["engine_decision"]


def _compute_trigger_cycle(cycle_type: str) -> str:
    """Generate a trigger cycle identifier like 'monthly_2026_03'."""
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
    """Actions expire at the start of the next cycle."""
    now = datetime.now(timezone.utc)
    if "monthly" in trigger_cycle:
        # Expire at start of next month
        if now.month == 12:
            return datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
        return datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)
    elif "quarterly" in trigger_cycle:
        # Expire at start of next quarter
        quarter = (now.month - 1) // 3 + 1
        next_q_month = quarter * 3 + 1
        if next_q_month > 12:
            return datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
        return datetime(now.year, next_q_month, 1, tzinfo=timezone.utc)
    # Annual: expire next Jan 1
    return datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)


# ── Main Engine Entry Point ─────────────────────────────────────────────────


async def run_portfolio_engine(
    portfolio_id: str,
    cycle_type: str,
) -> dict:
    """
    Run the CompounderEngine for a single portfolio.

    Steps:
      1. Load portfolio + positions from DB
      2. Fetch latest signals for each position ticker from StockResult
      3. Convert to engine data contracts (SignalInput, PortfolioPosition)
      4. Run CompounderEngine.refresh()
      5. Expire previous pending actions
      6. Write new PortfolioAction records
      7. Update Position state fields
      8. Return summary
    """
    db = await get_db()

    # 1. Load portfolio + positions
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

    # 2. Fetch latest signals for each ticker
    signals_map, signals_list = await _build_signals(db, portfolio)

    # 3. Convert DB positions → engine positions
    engine_positions = _to_engine_positions(portfolio.positions)

    # 4. Run engine
    engine = CompounderEngine(config=OwnerConfig())
    is_quarterly = cycle_type in ("quarterly", "annual")
    result = engine.refresh(
        signals=signals_list,
        current_positions=engine_positions,
        is_quarterly=is_quarterly,
    )

    # 5. Expire previous pending actions
    trigger_cycle = _compute_trigger_cycle(cycle_type)
    await db.portfolioaction.update_many(
        where={
            "portfolioId": portfolio_id,
            "status": "pending",
        },
        data={"status": "expired"},
    )

    # 6. Write new PortfolioAction records
    actions_created = 0
    for action in result.actions:
        sig = signals_map.get(action.ticker)
        signal_snapshot = None
        if sig:
            signal_snapshot = {
                "moat_score": sig.moat_score,
                "current_price": sig.current_price,
                "drawdown_pct": action.drawdown_pct,
                "compounder_score": action.compounder_score,
                "revenue_growth_yoy": sig.revenue_growth_yoy,
                "margin_trend": sig.margin_trend,
                "high_252d": sig.high_252d,
                "ma_200d": sig.ma_200d,
            }

        action_data: dict = {
            "portfolioId": portfolio_id,
            "ticker": action.ticker,
            "actionType": _map_action_type(action),
            "weightDelta": action.target_weight - action.current_weight,
            "reasonCodes": _extract_reason_codes(action),
            "reasonText": action.reason,
            "status": "pending",
            "triggerCycle": trigger_cycle,
            "engineVersion": ENGINE_VERSION,
            "expiresAt": _next_cycle_expiry(trigger_cycle),
        }
        # Prisma rejects None for Json? fields — omit key entirely when no snapshot
        if signal_snapshot is not None:
            action_data["signalSnapshot"] = signal_snapshot

        await db.portfolioaction.create(data=action_data)
        actions_created += 1

    # 7. Update position states
    await _update_position_states(db, portfolio_id, result, signals_map, engine_positions)

    return {
        "portfolio_id": portfolio_id,
        "cycle_type": cycle_type,
        "trigger_cycle": trigger_cycle,
        "actions_created": actions_created,
        "diagnostics": result.diagnostics,
    }


# ── Signal Building ─────────────────────────────────────────────────────────


async def _build_signals(
    db, portfolio,
) -> tuple[dict[str, SignalInput], list[SignalInput]]:
    """
    Fetch latest StockResult per position ticker and convert to SignalInput.

    Returns (signals_map: {ticker: SignalInput}, signals_list: [SignalInput]).
    """
    signals_map: dict[str, SignalInput] = {}
    tickers = [p.ticker for p in portfolio.positions]

    for ticker in tickers:
        # Find most recent completed analysis
        result = await db.stockresult.find_first(
            where={
                "userId": portfolio.userId,
                "ticker": ticker,
                "status": "completed",
            },
            order={"createdAt": "desc"},
        )
        if not result or not result.fullOutput:
            logger.warning("No completed analysis for %s, skipping signal", ticker)
            continue

        full_output = result.fullOutput if isinstance(result.fullOutput, dict) else {}
        moat_score = result.moatScore or 0.0
        sector = result.sector or "Unknown"

        # Get current price from quant output
        quant = full_output.get("quant_output") or {}
        ti = quant.get("technical_indicators") or {}
        ma = ti.get("moving_averages") or {}
        current_price = (
            ma.get("current_price")
            or ti.get("current_price")
            or quant.get("current_price")
            or 0.0
        )

        signal = extract_signal_from_full_output(
            ticker=ticker,
            full_output=full_output,
            moat_score=moat_score,
            sector=sector,
            current_price=float(current_price),
        )
        signals_map[ticker] = signal

    return signals_map, list(signals_map.values())


# ── Position Conversion ─────────────────────────────────────────────────────


def _to_engine_positions(db_positions) -> dict[str, EnginePosition]:
    """Convert Prisma Position records to engine PortfolioPosition dataclass."""
    result: dict[str, EnginePosition] = {}
    for pos in db_positions:
        add_tiers = set()
        if pos.addTiersApplied:
            try:
                raw = pos.addTiersApplied if isinstance(pos.addTiersApplied, list) else json.loads(str(pos.addTiersApplied))
                add_tiers = set(float(t) for t in raw)
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

        result[pos.ticker] = EnginePosition(
            ticker=pos.ticker,
            weight=pos.currentWeight,
            entry_date=pos.entryDate.date() if pos.entryDate else date.today(),
            entry_price=pos.costBasis or 0.0,
            quarters_held=pos.quartersHeld,
            compounder_score=pos.compounderScore or 0.0,
            add_tiers_applied=add_tiers,
            last_drawdown=pos.lastDrawdown or 0.0,
        )
    return result


# ── Position State Update ───────────────────────────────────────────────────


async def _update_position_states(
    db,
    portfolio_id: str,
    result,
    signals_map: dict[str, SignalInput],
    engine_positions: dict[str, EnginePosition],
) -> None:
    """
    Update Position records based on engine result.

    Updates: tierState, thesisState, lastDrawdown, addTiersApplied, compounderScore.
    """
    for action in result.actions:
        position = await db.position.find_first(
            where={"portfolioId": portfolio_id, "ticker": action.ticker}
        )
        if not position:
            continue

        update_data: dict = {}

        # Update drawdown state
        ep = engine_positions.get(action.ticker)
        if ep:
            update_data["lastDrawdown"] = ep.last_drawdown
            update_data["addTiersApplied"] = json.dumps(list(ep.add_tiers_applied))

        # Update compounder score if available
        if action.compounder_score is not None:
            update_data["compounderScore"] = action.compounder_score

        # Update tier state based on drawdown
        if action.drawdown_pct is not None:
            dd = action.drawdown_pct
            if dd <= -0.50:
                update_data["tierState"] = "t4_50"
            elif dd <= -0.40:
                update_data["tierState"] = "t3_40"
            elif dd <= -0.30:
                update_data["tierState"] = "t2_30"
            elif dd <= -0.20:
                update_data["tierState"] = "t1_20"
            else:
                update_data["tierState"] = "none"

        # Update thesis state based on action type
        action_type = _map_action_type(action)
        if action_type == "EXIT_THESIS":
            update_data["thesisState"] = "broken"
            update_data["ownershipStatus"] = "disqualified"
        elif action_type in ("ADD_TIER_20", "ADD_TIER_30", "ADD_TIER_40", "ADD_TIER_50", "INITIATE"):
            update_data["thesisState"] = "intact"
            update_data["eligibilityState"] = "eligible"
            if position.quartersHeld >= 4:
                update_data["ownershipStatus"] = "core_compounder"

        if update_data:
            await db.position.update(
                where={"id": position.id},
                data=update_data,
            )
