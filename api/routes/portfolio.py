"""
Portfolio management endpoints — Compounder Ownership OS v3.1.

Supports:
  - Portfolio CRUD (max per tier enforced)
  - Position management (add, update, remove)
  - Action feed (paginated, filterable)
  - Action lifecycle (mark executed/ignored)
  - Manual engine trigger (Investor+)
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import get_current_user
from api.lib.db import get_db
from api.lib.entitlements import (
    has_feature,
    FEAT_PORTFOLIO_CORE,
    FEAT_PORTFOLIO_ACTIONS,
    FEAT_PORTFOLIO_INTELLIGENCE_BASIC,
    FEAT_PORTFOLIO_INTELLIGENCE_FULL,
    FEAT_PORTFOLIO_INTELLIGENCE_STRESS,
)
from api.lib.plan_limits import get_tier_limits
from api.models.auth import User
from api.models.portfolio import (
    ActionFeedResponse,
    ActionResponse,
    AddPositionRequest,
    CreatePortfolioRequest,
    MarkActionRequest,
    PortfolioListResponse,
    PortfolioResponse,
    PositionResponse,
    UpdatePositionRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Helpers ──────────────────────────────────────────────────────────────────


def _position_response(pos) -> PositionResponse:
    """Convert a Prisma Position record to PositionResponse."""
    return PositionResponse(
        ticker=pos.ticker,
        current_weight=pos.currentWeight,
        cost_basis=pos.costBasis,
        shares=pos.shares,
        tier_state=pos.tierState,
        thesis_state=pos.thesisState,
        eligibility_state=pos.eligibilityState,
        ownership_status=pos.ownershipStatus,
        entry_date=pos.entryDate,
        quarters_held=pos.quartersHeld,
        compounder_score=pos.compounderScore,
        last_drawdown=pos.lastDrawdown,
        latest_run_id=pos.latestRunId,
    )


def _portfolio_response(portfolio) -> PortfolioResponse:
    """Convert a Prisma Portfolio record (with positions) to PortfolioResponse."""
    positions = [_position_response(p) for p in (portfolio.positions or [])]
    total_weight = sum(p.current_weight for p in positions)
    return PortfolioResponse(
        id=portfolio.id,
        name=portfolio.name,
        mandate=portfolio.mandate,
        positions=positions,
        total_weight=total_weight,
        position_count=len(positions),
        created_at=portfolio.createdAt,
    )


def _action_response(action) -> ActionResponse:
    """Convert a Prisma PortfolioAction record to ActionResponse."""
    return ActionResponse(
        id=action.id,
        ticker=action.ticker,
        action_type=action.actionType,
        weight_delta=action.weightDelta,
        reason_codes=action.reasonCodes or [],
        reason_text=action.reasonText,
        status=action.status,
        signal_snapshot=action.signalSnapshot,
        trigger_cycle=action.triggerCycle,
        engine_version=action.engineVersion,
        created_at=action.createdAt,
        executed_at=action.executedAt,
        expires_at=action.expiresAt,
    )


async def _verify_portfolio_ownership(db, portfolio_id: str, user_id: str):
    """Fetch portfolio and verify it belongs to the user. Raises 404 if not found."""
    portfolio = await db.portfolio.find_unique(
        where={"id": portfolio_id},
        include={"positions": True},
    )
    if not portfolio or portfolio.userId != user_id:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return portfolio


# ── Portfolio CRUD ───────────────────────────────────────────────────────────


@router.post("/portfolio", response_model=PortfolioResponse)
async def create_portfolio(
    request: CreatePortfolioRequest,
    user: User = Depends(get_current_user),
):
    """Create a new portfolio. Enforces max_portfolios per tier."""
    if not has_feature(user, FEAT_PORTFOLIO_CORE):
        raise HTTPException(status_code=403, detail={
            "code": "NOT_ENTITLED",
            "message": "Portfolio access requires a paid subscription",
        })

    db = await get_db()
    tier = str(user.tier.value).lower() if hasattr(user.tier, "value") else str(user.tier).lower()
    limits = get_tier_limits(tier)

    existing_count = await db.portfolio.count(where={"userId": user.id})
    if existing_count >= limits.max_portfolios:
        raise HTTPException(status_code=400, detail={
            "code": "PORTFOLIO_LIMIT",
            "message": f"Your plan allows {limits.max_portfolios} portfolio(s)",
        })

    portfolio = await db.portfolio.create(
        data={
            "userId": user.id,
            "name": request.name,
            "mandate": request.mandate,
        },
        include={"positions": True},
    )
    return _portfolio_response(portfolio)


@router.get("/portfolio", response_model=PortfolioListResponse)
async def list_portfolios(user: User = Depends(get_current_user)):
    """List all portfolios for the current user."""
    db = await get_db()
    portfolios = await db.portfolio.find_many(
        where={"userId": user.id},
        include={"positions": True},
        order={"createdAt": "asc"},
    )
    return PortfolioListResponse(
        portfolios=[_portfolio_response(p) for p in portfolios]
    )


@router.get("/portfolio/{portfolio_id}", response_model=PortfolioResponse)
async def get_portfolio(portfolio_id: str, user: User = Depends(get_current_user)):
    """Get a single portfolio with all positions."""
    db = await get_db()
    portfolio = await _verify_portfolio_ownership(db, portfolio_id, user.id)
    return _portfolio_response(portfolio)


# ── Position Management ─────────────────────────────────────────────────────


@router.post("/portfolio/{portfolio_id}/positions", response_model=PositionResponse)
async def add_position(
    portfolio_id: str,
    request: AddPositionRequest,
    user: User = Depends(get_current_user),
):
    """Add a position to a portfolio."""
    db = await get_db()
    portfolio = await _verify_portfolio_ownership(db, portfolio_id, user.id)

    ticker = request.ticker.upper()

    # Check if position already exists
    existing = await db.position.find_first(
        where={"portfolioId": portfolio_id, "ticker": ticker}
    )
    if existing:
        raise HTTPException(status_code=400, detail=f"{ticker} already in portfolio")

    # Find most recent completed analysis for this ticker
    latest_result = await db.stockresult.find_first(
        where={"userId": user.id, "ticker": ticker, "status": "completed"},
        order={"createdAt": "desc"},
    )

    position = await db.position.create(
        data={
            "portfolioId": portfolio_id,
            "ticker": ticker,
            "currentWeight": request.weight,
            "costBasis": request.cost_basis,
            "shares": request.shares,
            "entryDate": datetime.now(timezone.utc),
            "latestRunId": latest_result.runId if latest_result else None,
        }
    )
    return _position_response(position)


@router.patch("/portfolio/{portfolio_id}/positions/{ticker}", response_model=PositionResponse)
async def update_position(
    portfolio_id: str,
    ticker: str,
    request: UpdatePositionRequest,
    user: User = Depends(get_current_user),
):
    """Update an existing position's weight, cost basis, or shares."""
    db = await get_db()
    await _verify_portfolio_ownership(db, portfolio_id, user.id)

    ticker = ticker.upper()
    position = await db.position.find_first(
        where={"portfolioId": portfolio_id, "ticker": ticker}
    )
    if not position:
        raise HTTPException(status_code=404, detail=f"{ticker} not found in portfolio")

    update_data = {}
    if request.weight is not None:
        update_data["currentWeight"] = request.weight
    if request.cost_basis is not None:
        update_data["costBasis"] = request.cost_basis
    if request.shares is not None:
        update_data["shares"] = request.shares

    if not update_data:
        return _position_response(position)

    updated = await db.position.update(
        where={"id": position.id},
        data=update_data,
    )
    return _position_response(updated)


@router.delete("/portfolio/{portfolio_id}/positions/{ticker}")
async def remove_position(
    portfolio_id: str,
    ticker: str,
    user: User = Depends(get_current_user),
):
    """Remove a position from a portfolio."""
    db = await get_db()
    await _verify_portfolio_ownership(db, portfolio_id, user.id)

    ticker = ticker.upper()
    deleted = await db.position.delete_many(
        where={"portfolioId": portfolio_id, "ticker": ticker}
    )
    if deleted == 0:
        raise HTTPException(status_code=404, detail=f"{ticker} not found in portfolio")

    return {"success": True, "ticker": ticker}


# ── Action Feed ──────────────────────────────────────────────────────────────


@router.get("/portfolio/{portfolio_id}/actions", response_model=ActionFeedResponse)
async def get_actions(
    portfolio_id: str,
    user: User = Depends(get_current_user),
    status: str | None = Query(None, description="Filter by status: pending, executed, ignored, expired"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Get the action feed for a portfolio, ordered by most recent first."""
    db = await get_db()
    await _verify_portfolio_ownership(db, portfolio_id, user.id)

    # Starter tier: limit to 3 most recent
    if not has_feature(user, FEAT_PORTFOLIO_ACTIONS):
        limit = min(limit, 3)

    where: dict = {"portfolioId": portfolio_id}
    if status:
        where["status"] = status

    actions = await db.portfolioaction.find_many(
        where=where,
        order={"createdAt": "desc"},
        take=limit,
        skip=offset,
    )
    total = await db.portfolioaction.count(where=where)
    pending_count = await db.portfolioaction.count(
        where={"portfolioId": portfolio_id, "status": "pending"}
    )

    return ActionFeedResponse(
        actions=[_action_response(a) for a in actions],
        total=total,
        pending_count=pending_count,
    )


@router.patch("/portfolio/{portfolio_id}/actions/{action_id}")
async def mark_action(
    portfolio_id: str,
    action_id: str,
    request: MarkActionRequest,
    user: User = Depends(get_current_user),
):
    """Mark an action as executed or ignored. Executing updates position weight."""
    db = await get_db()
    await _verify_portfolio_ownership(db, portfolio_id, user.id)

    action = await db.portfolioaction.find_unique(where={"id": action_id})
    if not action or action.portfolioId != portfolio_id:
        raise HTTPException(status_code=404, detail="Action not found")

    if action.status != "pending":
        raise HTTPException(status_code=400, detail=f"Action already {action.status}")

    if request.status not in ("executed", "ignored"):
        raise HTTPException(status_code=400, detail="Status must be 'executed' or 'ignored'")

    now = datetime.now(timezone.utc)
    update_data: dict = {"status": request.status}

    if request.status == "executed":
        update_data["executedAt"] = now

        # Apply weight delta to position
        weight_delta = request.override_weight if request.override_weight is not None else action.weightDelta
        position = await db.position.find_first(
            where={"portfolioId": portfolio_id, "ticker": action.ticker}
        )

        if action.actionType == "EXIT_THESIS":
            # Full exit: remove position
            if position:
                await db.position.update(
                    where={"id": position.id},
                    data={
                        "currentWeight": 0.0,
                        "thesisState": "broken",
                        "ownershipStatus": "disqualified",
                    },
                )
        elif action.actionType == "INITIATE":
            # New position: create if doesn't exist
            if not position:
                await db.position.create(
                    data={
                        "portfolioId": portfolio_id,
                        "ticker": action.ticker,
                        "currentWeight": weight_delta,
                        "entryDate": now,
                        "ownershipStatus": "watch",
                    }
                )
            else:
                await db.position.update(
                    where={"id": position.id},
                    data={"currentWeight": position.currentWeight + weight_delta},
                )
        elif position:
            # ADD_TIER_*, TRIM_*, etc: adjust weight
            new_weight = max(0.0, position.currentWeight + weight_delta)
            await db.position.update(
                where={"id": position.id},
                data={"currentWeight": new_weight},
            )

    await db.portfolioaction.update(where={"id": action_id}, data=update_data)

    return {"success": True, "action_id": action_id, "status": request.status}


# ── Engine Trigger ───────────────────────────────────────────────────────────


@router.post("/portfolio/{portfolio_id}/engine/run")
async def trigger_engine_run(
    portfolio_id: str,
    user: User = Depends(get_current_user),
    cycle_type: str = Query("monthly", description="Engine cycle: monthly, quarterly, annual"),
):
    """Manually trigger the portfolio engine. Investor+ only."""
    if not has_feature(user, FEAT_PORTFOLIO_ACTIONS):
        raise HTTPException(status_code=403, detail={
            "code": "NOT_ENTITLED",
            "message": "Engine trigger requires Investor tier or above",
        })

    db = await get_db()
    await _verify_portfolio_ownership(db, portfolio_id, user.id)

    if cycle_type not in ("monthly", "quarterly", "annual"):
        raise HTTPException(status_code=400, detail="cycle_type must be monthly, quarterly, or annual")

    from api.services.portfolio_engine import run_portfolio_engine

    try:
        result = await run_portfolio_engine(portfolio_id, cycle_type)
        return {"success": True, **result}
    except Exception as e:
        logger.error("Engine run failed for portfolio %s: %s", portfolio_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Engine run failed: {str(e)}")


# ── Portfolio Intelligence ────────────────────────────────────────────────────


@router.get("/portfolio/{portfolio_id}/intelligence")
async def get_portfolio_intelligence(
    portfolio_id: str,
    user: User = Depends(get_current_user),
):
    """
    Compute and return the Portfolio Intelligence overlay for a given portfolio.

    Tier levels:
      Starter  → basic  (PM memo + 3-row alignment matrix)
      Investor → full   (+ edge score + concentration + regime vulnerability + misalignment flags)
      Trader   → stress (+ thematic clustering + all 5 misalignment flags)
    """
    if not has_feature(user, FEAT_PORTFOLIO_INTELLIGENCE_BASIC):
        raise HTTPException(status_code=403, detail={
            "code": "NOT_ENTITLED",
            "message": "Portfolio Intelligence requires a paid subscription",
        })

    db = await get_db()
    portfolio = await _verify_portfolio_ownership(db, portfolio_id, user.id)
    positions = portfolio.positions or []

    if not positions:
        from api.lib.portfolio_intelligence import compute_portfolio_intelligence
        return compute_portfolio_intelligence(portfolio_id, [], "basic")

    # Determine tier level for intelligence computation
    if has_feature(user, FEAT_PORTFOLIO_INTELLIGENCE_STRESS):
        tier = "stress"
    elif has_feature(user, FEAT_PORTFOLIO_INTELLIGENCE_FULL):
        tier = "full"
    else:
        tier = "basic"

    # Fetch latest completed StockResult per ticker
    tickers = [p.ticker for p in positions]
    results = await db.stockresult.find_many(
        where={"userId": user.id, "ticker": {"in": tickers}, "status": "completed"},
        order={"createdAt": "desc"},
    )

    # Build ticker → latest result map
    result_map: dict[str, Any] = {}
    for r in results:
        if r.ticker not in result_map:
            result_map[r.ticker] = r

    # Build positions_data list
    positions_data = []
    for pos in positions:
        stock_result = result_map.get(pos.ticker)
        full_output: dict | None = None
        if stock_result and stock_result.fullOutput:
            raw = stock_result.fullOutput
            if isinstance(raw, str):
                try:
                    full_output = json.loads(raw)
                except Exception:
                    full_output = None
            elif isinstance(raw, dict):
                full_output = raw

        positions_data.append({
            "ticker": pos.ticker,
            "weight": float(pos.currentWeight or 0.0),
            "full_output": full_output,
            "sector": stock_result.sector if stock_result else None,
            "moat_score": float(stock_result.moatScore or 5.0) if stock_result else 5.0,
        })

    from api.lib.portfolio_intelligence import compute_portfolio_intelligence

    try:
        result = compute_portfolio_intelligence(portfolio_id, positions_data, tier)
        return result
    except Exception as e:
        logger.error(
            "Portfolio intelligence failed for portfolio %s: %s", portfolio_id, e, exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Intelligence computation failed: {str(e)}")
