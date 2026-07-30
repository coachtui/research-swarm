"""
Admin-only endpoints for the autopilot market outlook.

Email delivery is dormant (Resend never configured); the weekly MarketOutlook
row is surfaced in-app instead, admin-only for now, with tier gating to
follow later.
"""

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.dependencies import require_admin
from api.lib.db import get_db
from api.models.auth import User
from execution.outlook_service import get_latest_outlook
from execution.batch_run_service import (
    get_batch_run, get_latest_batch_run, list_batch_runs,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# --- Response Models ---

class MarketOutlookResponse(BaseModel):
    """Latest MarketOutlook row, serialized for the admin dashboard."""
    id: str
    run_date: datetime
    regime: str
    regime_mechanical: str
    strategist_override: bool
    strategist_status: str
    conviction: Optional[float]
    sector_rankings: List[dict]
    rotation_flags: List[dict]
    breadth: dict
    reasoning: Optional[str]
    # Phase 3A extended signals — None until the first post-3A outlook runs
    industry_rankings: Optional[List[dict]] = None
    industry_rotations: Optional[List[dict]] = None
    industry_missing: Optional[List[str]] = None
    size_style: Optional[dict] = None
    # Phase 3B theme baskets — None until the first post-3B outlook runs
    theme_rankings: Optional[List[dict]] = None
    theme_rotations: Optional[List[dict]] = None
    theme_missing: Optional[List[dict]] = None
    theme_history: Optional[dict] = None


# --- Pure helpers (tested directly) ────────────────────────────────────────

def outlook_row_to_response(row) -> MarketOutlookResponse:
    """Map a Prisma MarketOutlook row (camelCase) to MarketOutlookResponse (snake_case)."""
    industry = getattr(row, "industryRankings", None) or None
    themes = getattr(row, "themeRankings", None) or None
    return MarketOutlookResponse(
        id=row.id,
        run_date=row.runDate,
        regime=row.regime,
        regime_mechanical=row.regimeMechanical,
        strategist_override=row.strategistOverride,
        strategist_status=row.strategistStatus,
        conviction=row.conviction,
        sector_rankings=row.sectorRankings,
        rotation_flags=row.rotationFlags,
        breadth=row.breadth,
        reasoning=row.reasoning,
        industry_rankings=industry.get("rankings") if industry else None,
        industry_rotations=industry.get("rotations") if industry else None,
        industry_missing=industry.get("missing") if industry else None,
        size_style=getattr(row, "sizeStyle", None),
        theme_rankings=themes.get("rankings") if themes else None,
        theme_rotations=themes.get("rotations") if themes else None,
        theme_missing=themes.get("missing") if themes else None,
        theme_history=themes.get("history") if themes else None,
    )


# --- Endpoints ──────────────────────────────────────────────────────────────

@router.get("/autopilot/outlook", response_model=MarketOutlookResponse)
async def get_outlook(admin: User = Depends(require_admin)):
    """
    Return the most recent MarketOutlook row.

    Admin-only endpoint. Tier gating (flag flip) to follow later.
    """
    db = await get_db()
    row = await get_latest_outlook(db)
    if row is None:
        raise HTTPException(status_code=404, detail="No outlook available yet")

    return outlook_row_to_response(row)


class EngineReportResponse(BaseModel):
    """One EngineReport journal row."""
    id: str
    created_at: datetime
    type: str
    severity: str
    source: str
    title: str
    body: dict


def engine_report_row_to_response(row) -> EngineReportResponse:
    return EngineReportResponse(
        id=row.id, created_at=row.createdAt, type=row.type,
        severity=row.severity, source=row.source, title=row.title,
        body=row.body or {},
    )


@router.get("/autopilot/reports", response_model=List[EngineReportResponse])
async def get_engine_reports(
    limit: int = 50,
    type: Optional[str] = None,
    severity: Optional[str] = None,
    admin: User = Depends(require_admin),
):
    """Engine journal feed, newest first. The owner's veto surface."""
    db = await get_db()
    where: dict = {}
    if type:
        where["type"] = type
    if severity:
        where["severity"] = severity
    rows = await db.enginereport.find_many(
        where=where or None,
        take=max(1, min(limit, 200)),
        order={"createdAt": "desc"},
    )
    return [engine_report_row_to_response(r) for r in rows]


# ── Monday batch audit trail ────────────────────────────────────────────────

class WeeklyBatchRunSummary(BaseModel):
    """One WeeklyBatchRun row, counts only — powers the history picker."""
    id: str
    run_date: datetime
    status: str
    abort_reason: Optional[str]
    universe_size: Optional[int]
    advanced_count: Optional[int]
    watchlist_extras: Optional[int]
    quant_stored: Optional[int]
    quant_failed: Optional[int]
    escalation_swarm: Optional[int]
    escalation_reuse: Optional[int]
    escalation_hold: Optional[int]
    swarm_cap: Optional[int]


class WeeklySignalRow(BaseModel):
    """One WeeklySignal row for a batch-run week, admin audit shape."""
    ticker: str
    tier: str
    verdict: Optional[str]
    screener_score: Optional[float]
    escalation_score: Optional[float]
    escalation_reasons: Optional[List[str]]
    quant_signals: Optional[dict]


class WeeklyBatchRunDetail(WeeklyBatchRunSummary):
    """One WeeklyBatchRun row plus its WeeklySignal rows for that week."""
    outcomes: Optional[Dict[str, str]]
    signals: List[WeeklySignalRow]


def batch_run_row_to_summary(row) -> WeeklyBatchRunSummary:
    """Map a Prisma WeeklyBatchRun row (camelCase) to WeeklyBatchRunSummary (snake_case)."""
    return WeeklyBatchRunSummary(
        id=row.id,
        run_date=row.runDate,
        status=row.status,
        abort_reason=row.abortReason,
        universe_size=row.universeSize,
        advanced_count=row.advancedCount,
        watchlist_extras=row.watchlistExtras,
        quant_stored=row.quantStored,
        quant_failed=row.quantFailed,
        escalation_swarm=row.escalationSwarm,
        escalation_reuse=row.escalationReuse,
        escalation_hold=row.escalationHold,
        swarm_cap=row.swarmCap,
    )


def weekly_signal_row_to_response(row) -> WeeklySignalRow:
    """Map a Prisma WeeklySignal row (camelCase) to WeeklySignalRow (snake_case)."""
    return WeeklySignalRow(
        ticker=row.ticker,
        tier=row.tier,
        verdict=row.verdict,
        screener_score=row.screenerScore,
        escalation_score=row.escalationScore,
        escalation_reasons=row.escalationReasons,
        quant_signals=row.quantSignals,
    )


def batch_run_row_to_detail(row, signal_rows) -> WeeklyBatchRunDetail:
    """Combine a WeeklyBatchRun row with its week's WeeklySignal rows."""
    summary = batch_run_row_to_summary(row)
    return WeeklyBatchRunDetail(
        **summary.model_dump(),
        outcomes=row.outcomes,
        signals=[weekly_signal_row_to_response(r) for r in signal_rows],
    )


@router.get("/autopilot/batch-runs", response_model=List[WeeklyBatchRunSummary])
async def get_batch_runs(limit: int = 12, admin: User = Depends(require_admin)):
    """History list of past weekly-batch runs, newest first."""
    db = await get_db()
    rows = await list_batch_runs(db, limit=limit)
    return [batch_run_row_to_summary(r) for r in rows]


@router.get("/autopilot/batch-runs/detail", response_model=WeeklyBatchRunDetail)
async def get_batch_run_detail(
    run_date: Optional[datetime] = None, admin: User = Depends(require_admin)
):
    """One weekly-batch run with its WeeklySignal rows joined in.

    Omit run_date for the most recent run.
    """
    db = await get_db()
    row = await get_batch_run(db, run_date) if run_date else await get_latest_batch_run(db)
    if row is None:
        raise HTTPException(status_code=404, detail="No batch run available yet")
    signal_rows = await db.weeklysignal.find_many(where={"runDate": row.runDate})
    return batch_run_row_to_detail(row, signal_rows)


# ── Phase 2: broker linking + sleeve control ────────────────────────────────

import asyncio

from execution.broker.credentials import get_active_alpaca_account, upsert_alpaca_account
from execution.sleeve_service import get_sleeve_state, set_sleeve_status


def _alpaca_client_factory(api_key: str, api_secret: str):
    """Indirection so tests can patch client construction (alpaca-py is a
    runtime-only dep, not installed in the unit-test env)."""
    from execution.broker.alpaca_client import AlpacaPaperClient

    return AlpacaPaperClient(api_key, api_secret)


class BrokerLinkRequest(BaseModel):
    api_key: str
    api_secret: str


class BrokerLinkResponse(BaseModel):
    status: str
    account_equity: float


@router.post("/autopilot/broker/link", response_model=BrokerLinkResponse)
async def link_broker(body: BrokerLinkRequest, admin: User = Depends(require_admin)):
    """Validate Alpaca paper keys against the live API, then store them
    encrypted (Fernet). Bad keys are rejected before anything is stored."""
    try:
        client = _alpaca_client_factory(body.api_key, body.api_secret)
        summary = await asyncio.to_thread(client.get_account_summary)
    except Exception:
        raise HTTPException(status_code=400, detail="Alpaca rejected these keys")

    db = await get_db()
    await upsert_alpaca_account(db, admin.id, body.api_key, body.api_secret)
    return BrokerLinkResponse(status="linked", account_equity=summary["equity"])


@router.get("/autopilot/broker/status")
async def broker_status(admin: User = Depends(require_admin)):
    """Linked-account + sleeve health overview (admin dashboard / curl)."""
    db = await get_db()
    account = await get_active_alpaca_account(db)
    if account is None:
        return {"linked": False, "sleeves": [], "latest_snapshot": None}

    sleeves = []
    for sleeve in ("A", "B"):
        state = await get_sleeve_state(db, sleeve)
        if state is not None:
            sleeves.append({
                "sleeve": sleeve,
                "status": state.status,
                "status_reason": state.statusReason,
                "cash_balance": state.cashBalance,
            })
    latest = await db.sleevesnapshot.find_first(order={"snapshotDate": "desc"})
    snapshot = None
    if latest is not None:
        snapshot = {
            "date": latest.snapshotDate.isoformat(),
            "sleeve": latest.sleeve,
            "equity": latest.equity,
            "spy_close": latest.spyClose,
        }
    return {
        "linked": True,
        "provider": account.provider,
        "mode": account.mode,
        "sleeves": sleeves,
        "latest_snapshot": snapshot,
    }


@router.post("/autopilot/sleeve/{sleeve}/resume")
async def resume_sleeve(sleeve: str, admin: User = Depends(require_admin)):
    """Manual reset after a circuit-breaker halt or reconciliation freeze —
    the engine never un-halts itself (spec requirement)."""
    if sleeve not in ("A", "B"):
        raise HTTPException(status_code=404, detail="Unknown sleeve")
    db = await get_db()
    state = await get_sleeve_state(db, sleeve)
    if state is None:
        raise HTTPException(status_code=404, detail="Sleeve not initialized")
    await set_sleeve_status(db, sleeve, "active", reason=None)
    return {"sleeve": sleeve, "status": "active"}


# ── This week: one page joining the broker to the memo's reasoning ──────────
# The "what" (positions, orders, fills) lived in EngineReport/Alpaca and the
# "why" (memo prose) in ThesisEvidence, and nothing ever joined them — so the
# only readable surface was a flat journal you had to click through row by row.
# Positions come from the BROKER, not EnginePosition: the engine's book is a
# mirror that syncs once a day, and the page should show what is actually held.

class WeekPosition(BaseModel):
    symbol: str
    qty: float
    avg_price: float
    market_value: float
    unrealized_pl: float
    unrealized_plpc: float
    sleeve: Optional[str] = None
    themes: List[str] = []
    conviction: Optional[float] = None
    why_now: Optional[str] = None
    why_this_expression: Optional[str] = None
    plan: Optional[dict] = None              # positionPlan verbatim, or None
    entry_forensics: Optional[dict] = None   # latest entry_order journal slice


class WeekAction(BaseModel):
    """Something the memo decided that did NOT become a held position."""
    ticker: str
    slug: Optional[str] = None
    outcome: str            # placed | vetoed | rejected | blocked | passed_on
    reason: Optional[str] = None
    role: Optional[str] = None
    conviction: Optional[float] = None
    reconsider_if: Optional[str] = None


class WeekThesis(BaseModel):
    slug: str
    stage: Optional[str] = None
    stage_rationale: Optional[str] = None


class WeekResponse(BaseModel):
    week: str
    regime: Optional[str] = None
    macro_reasoning: Optional[str] = None
    market_view: Optional[str] = None        # the memo's own words, verbatim
    equity: Optional[float] = None
    cash: Optional[float] = None
    broker_ok: bool
    theses: List[WeekThesis] = []
    positions: List[WeekPosition] = []
    open_orders: List[dict] = []
    actions: List[WeekAction] = []


async def _week_memo_rows(db, week: str) -> List[Any]:
    """Latest weekly_memo ledger row per theme for `week` (a memo can run more
    than once — manual invokes — and only the last one is the decision)."""
    rows = await db.thesisevidence.find_many(
        where={"kind": "weekly_memo", "week": week}, order={"createdAt": "asc"})
    return list({r.themeSlug: r for r in rows if r.themeSlug}.values())


def _broker_snapshot() -> Dict[str, Any]:
    """Live positions/orders/account. Degrades to broker_ok=False — the page
    must still render the memo's reasoning when the broker is unreachable."""
    import os

    try:
        from execution.broker.alpaca_client import AlpacaPaperClient

        key = os.getenv("ALPACA_PAPER_API_KEY", "")
        secret = os.getenv("ALPACA_PAPER_API_SECRET", "")
        if not key or not secret:
            return {"ok": False}
        c = AlpacaPaperClient(key, secret)._client
        acct = c.get_account()
        from alpaca.trading.enums import QueryOrderStatus
        from alpaca.trading.requests import GetOrdersRequest

        return {
            "ok": True,
            "equity": float(acct.equity),
            "cash": float(acct.cash),
            "positions": [
                {"symbol": p.symbol, "qty": float(p.qty),
                 "avg_price": float(p.avg_entry_price),
                 "market_value": float(p.market_value),
                 "unrealized_pl": float(p.unrealized_pl),
                 "unrealized_plpc": float(p.unrealized_plpc)}
                for p in c.get_all_positions()
            ],
            "orders": [
                {"symbol": o.symbol, "side": str(o.side).split(".")[-1],
                 "qty": float(o.qty), "limit_price": float(o.limit_price or 0.0),
                 "status": str(o.status).split(".")[-1],
                 "submitted": str(o.submitted_at)[:10]}
                for o in c.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN,
                                                       limit=100))
            ],
        }
    except Exception:
        logger.exception("week view: broker snapshot failed")
        return {"ok": False}


_FORENSIC_KEYS = ("limit_price", "entry_style", "price", "sma20", "atr",
                  "dist_200wma", "add_tranche_fraction")


def _entry_forensics_map(rows) -> Dict[str, dict]:
    """symbol -> the latest entry_order journal's price story. Rows arrive
    newest-first; first occurrence per symbol wins. Pre-Phase-C rows lack the
    math inputs — keys are always present, values None (a labeled absence,
    per the spec's degrade posture)."""
    out: Dict[str, dict] = {}
    for r in rows:
        body = r.body or {}
        symbol = body.get("symbol")
        if not symbol or symbol in out:
            continue
        out[symbol] = {k: body.get(k) for k in _FORENSIC_KEYS}
    return out


def _market_view(row) -> Optional[str]:
    """The memo's 3-6-sentence read, verbatim from the latest thesis_memo
    journal row. Never recomputed, never summarized."""
    body = getattr(row, "body", None) or {}
    view = body.get("market_view")
    return view if isinstance(view, str) and view.strip() else None


@router.get("/autopilot/week", response_model=WeekResponse)
async def get_week(week: Optional[str] = None, admin: User = Depends(require_admin)):
    """Everything decided this week, joined to what the broker actually holds."""
    import asyncio

    db = await get_db()

    outlook = await db.marketoutlook.find_first(order={"runDate": "desc"})
    if week is None:
        week = (outlook.runDate.date().isoformat() if outlook
                else date.today().isoformat())

    memo_rows = await _week_memo_rows(db, week)
    if not memo_rows:                      # fall back to the latest memo week
        latest = await db.thesisevidence.find_first(
            where={"kind": "weekly_memo"}, order={"createdAt": "desc"})
        if latest:
            week = latest.week
            memo_rows = await _week_memo_rows(db, week)

    # ticker -> the memo's own words, and the theses list
    by_ticker: Dict[str, Dict[str, Any]] = {}
    theses: List[WeekThesis] = []
    actions: List[WeekAction] = []
    for r in memo_rows:
        body = r.body or {}
        theses.append(WeekThesis(slug=r.themeSlug, stage=r.stage,
                                 stage_rationale=body.get("stage_rationale")))
        for a in body.get("actions") or []:
            if a.get("ticker"):
                by_ticker[a["ticker"]] = {**a, "slug": r.themeSlug}
        for p in body.get("passed_on") or []:
            actions.append(WeekAction(ticker=p.get("ticker", "?"), slug=r.themeSlug,
                                      outcome="passed_on", reason=p.get("reason"),
                                      reconsider_if=p.get("reconsider_if")))

    snap = await asyncio.to_thread(_broker_snapshot)
    held = {p["symbol"] for p in snap.get("positions", [])}

    pos_rows = {p.symbol: p for p in await db.engineposition.find_many()}

    forensic_rows = await db.enginereport.find_many(
        where={"type": "entry_order"}, order={"createdAt": "desc"}, take=200)
    forensics = _entry_forensics_map(forensic_rows)

    memo_report = await db.enginereport.find_first(
        where={"type": "thesis_memo"}, order={"createdAt": "desc"})

    positions: List[WeekPosition] = []
    for p in snap.get("positions", []):
        meta = pos_rows.get(p["symbol"])
        memo = by_ticker.get(p["symbol"]) or {}
        positions.append(WeekPosition(
            **p,
            sleeve=getattr(meta, "sleeve", None),
            themes=((getattr(meta, "sourceTags", None) or {}).get("themes") or []),
            conviction=getattr(meta, "convictionScore", None),
            why_now=memo.get("why_now"),
            why_this_expression=memo.get("why_this_expression"),
            plan=(getattr(meta, "positionPlan", None) or None),
            entry_forensics=forensics.get(p["symbol"]),
        ))

    # Decided but not held: the column that never existed anywhere.
    for ticker, a in by_ticker.items():
        if ticker in held or a.get("action") in ("hold", "review"):
            continue
        actions.append(WeekAction(
            ticker=ticker, slug=a.get("slug"),
            outcome="exited" if a.get("action") == "exit" else "not_placed",
            reason=a.get("why_now"), role=a.get("role"),
            conviction=a.get("conviction")))

    return WeekResponse(
        week=week,
        regime=getattr(outlook, "regime", None),
        macro_reasoning=getattr(outlook, "reasoning", None),
        market_view=_market_view(memo_report),
        equity=snap.get("equity"), cash=snap.get("cash"),
        broker_ok=bool(snap.get("ok")),
        theses=theses, positions=positions,
        open_orders=snap.get("orders", []), actions=actions,
    )
