"""
Structural Deployment Update — Investor-tier capital deployability report.

Reads from existing StockResult.fullOutput rows. NO new LLM calls.
Metrics are extracted, cached for 24 hours, and returned as a structured report.

Universe: user's watchlist tickers + any ticker analyzed in the last 30 days.

Inclusion criteria (all must pass):
  1. confirmation_score >= 4  (4-of-5 moat components above threshold)
  2. allocation_delta_30d > 0  (positive conviction shift vs prior run)
  3. vol_adj_ev_percentile >= 60  (cross-universe rank)
  4. stop_probability <= 25.0 %
  5. regime_stable == True  (not Noise Dominated or High Noise)

# Future: integrate Allocation Impact Simulation
# Future: integrate Market Deployability Index chart
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.dependencies import get_current_user
from api.lib.db import get_db
from api.lib.entitlements import FEAT_DEPLOYMENT_STRUCTURAL, has_feature
from api.models.auth import User

logger = logging.getLogger(__name__)

router = APIRouter()

_CACHE_TTL_HOURS = 24

# ── Confirmation score thresholds ─────────────────────────────────────────────
_CONF_THRESHOLDS: Dict[str, float] = {
    "earnings_momentum": 6.0,
    "financial_health": 6.0,
    "valuation": 5.0,
    "technical_strength": 5.0,
    "sentiment_catalysts": 5.0,
}

# Noise regimes that indicate deteriorating regime stability
_UNSTABLE_REGIMES = frozenset({"Noise Dominated", "High Noise"})


# ── Response models ────────────────────────────────────────────────────────────

class DeployableTickerItem(BaseModel):
    ticker: str
    sector: str
    allocation_current: float
    allocation_delta_30d: Optional[float]
    confirmation_score: int         # 0–5
    vol_adj_ev_percentile: float    # 0–100 rank within universe
    stop_probability: float         # 0–100
    sector_breadth_pct: float       # % of same-sector tickers that are confirmed


class SectorBreadthRow(BaseModel):
    sector: str
    confirmed: int
    total: int
    pct_confirmed: float
    trend: str  # "rising" | "stable" | "falling"


class MarketDeployabilitySnapshot(BaseModel):
    universe_size: int
    pct_universe_confirmed: float
    avg_allocation_delta: Optional[float]
    avg_stop_probability: float
    regime_stable_pct: float
    capital_posture: str  # "Low" | "Moderate" | "Expanding"


class DeploymentUpdateResponse(BaseModel):
    generated_at: str
    cache_age_hours: float
    snapshot: MarketDeployabilitySnapshot
    deployable_tickers: List[DeployableTickerItem]
    sector_breadth: List[SectorBreadthRow]
    no_deployable_message: Optional[str]


# ── Helper: parse fullOutput JSON ─────────────────────────────────────────────

def _parse_full_output(raw: Any) -> Optional[Dict[str, Any]]:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return None
    return None


# ── Helper: enrich full_output with decision_intelligence ─────────────────────

def _enrich(full_output: Dict[str, Any], moat_score: float) -> Dict[str, Any]:
    """Apply the on-the-fly DI enrichment. Fails silently."""
    try:
        from api.lib.decision_intelligence import enrich_with_decision_intelligence
        return enrich_with_decision_intelligence(full_output, moat_score)
    except Exception as exc:
        logger.warning("DI enrichment failed for deployment metrics: %s", exc)
        return full_output


# ── Helper: extract raw metrics from enriched full_output ─────────────────────

def _extract_metrics(
    ticker: str,
    full_output: Dict[str, Any],
    moat_score: float,
) -> Dict[str, Any]:
    """
    Extract all deployment-relevant metrics from an enriched full_output dict.
    Returns a dict with all fields needed to upsert DeploymentMetricsCache.
    """
    fund = full_output.get("fundamentalist_output") or {}
    valuation_metrics = fund.get("valuation_metrics") or {}
    peer = fund.get("peer_comparison") or {}
    price_targets_raw = fund.get("price_targets") or {}

    signal_bd = full_output.get("signal_breakdown") or {}
    stop_prob_raw = signal_bd.get("stop_probability") or {}
    noise_filter = signal_bd.get("noise_filter") or {}
    moat_bd = full_output.get("moat_breakdown") or {}

    di = full_output.get("decision_intelligence") or {}
    conviction = di.get("conviction_position") or {}

    # ── Sector ────────────────────────────────────────────────────────────────
    sector = (
        peer.get("sector")
        or valuation_metrics.get("sector")
        or "Unknown"
    )

    # ── Allocation current ────────────────────────────────────────────────────
    allocation_current = float(conviction.get("recommended_pct") or 0.0)

    # ── Confirmation score (0–5) ──────────────────────────────────────────────
    confirmation_score = 0
    for field, threshold in _CONF_THRESHOLDS.items():
        value = moat_bd.get(field)
        if value is not None and float(value) >= threshold:
            confirmation_score += 1

    # ── EV ratio ──────────────────────────────────────────────────────────────
    prob_ev = price_targets_raw.get("probability_weighted_ev")
    current_price = valuation_metrics.get("current_price") or di.get("current_price")
    ev_ratio: Optional[float] = None
    if prob_ev and current_price and current_price > 0:
        ev_ratio = round(float(prob_ev) / float(current_price), 4)

    # ── Stop probability ──────────────────────────────────────────────────────
    stop_probability = float(
        stop_prob_raw.get("effective_stop_probability_pct") or 50.0
    )

    # ── Regime stability ──────────────────────────────────────────────────────
    noise_regime = noise_filter.get("noise_regime", "")
    regime_stable = noise_regime not in _UNSTABLE_REGIMES

    # ── Vol-adjusted EV score (used for cross-universe percentile ranking) ────
    vol_adj_ev_score: Optional[float] = None
    if ev_ratio is not None:
        vol_adj_ev_score = round(ev_ratio * (1.0 - stop_probability / 100.0), 4)

    return {
        "sector": sector,
        "allocationCurrent": allocation_current,
        "confirmationScore": confirmation_score,
        "evRatio": ev_ratio,
        "volAdjEvScore": vol_adj_ev_score,
        "stopProbability": stop_probability,
        "regimeStable": regime_stable,
    }


# ── Helper: compute rank-based percentile ─────────────────────────────────────

def _percentile(value: float, all_values: List[float]) -> float:
    """Return 0–100 rank-based percentile of value within all_values."""
    if not all_values:
        return 50.0
    rank = sum(1 for v in all_values if v <= value)
    return round(rank / len(all_values) * 100.0, 1)


# ── Helper: classify capital posture ─────────────────────────────────────────

def _classify_posture(
    pct_confirmed: float,
    avg_delta: Optional[float],
    avg_stop: float,
) -> str:
    if pct_confirmed >= 0.40 and avg_stop < 20.0:
        return "Expanding"
    if pct_confirmed >= 0.20 or (avg_delta is not None and avg_delta > 0):
        return "Moderate"
    return "Low"


# ── Helper: sector breadth trend (comparing current vs prior cached scores) ───

def _sector_trend(sector: str, current_scores: Dict[str, int], prior_scores: Dict[str, int]) -> str:
    """
    Compare avg confirmation scores for a sector between current and prior snapshots.
    Returns "rising", "stable", or "falling".
    """
    current_vals = [v for k, v in current_scores.items() if k == sector]
    prior_vals = [v for k, v in prior_scores.items() if k == sector]
    if not current_vals or not prior_vals:
        return "stable"
    avg_curr = sum(current_vals) / len(current_vals)
    avg_prior = sum(prior_vals) / len(prior_vals)
    if avg_curr > avg_prior + 0.1:
        return "rising"
    if avg_curr < avg_prior - 0.1:
        return "falling"
    return "stable"


# ── Core service function ──────────────────────────────────────────────────────

async def _build_deployment_update(user_id: str, db) -> DeploymentUpdateResponse:
    now_utc = datetime.now(timezone.utc)

    # ── 1. Check cache freshness ───────────────────────────────────────────────
    cached_rows = await db.deploymentmetricscache.find_many(
        where={"userId": user_id},
        order={"computedAt": "desc"},
    )

    cache_age_hours = 0.0
    if cached_rows:
        newest_computed = cached_rows[0].computedAt
        if newest_computed.tzinfo is None:
            newest_computed = newest_computed.replace(tzinfo=timezone.utc)
        cache_age_hours = (now_utc - newest_computed).total_seconds() / 3600.0

    cache_is_fresh = cached_rows and cache_age_hours < _CACHE_TTL_HOURS

    # ── 2. Build prior-score lookup from cached rows (for sector trend) ────────
    prior_sector_scores: Dict[str, int] = {r.ticker: r.confirmationScore for r in cached_rows}

    # ── 3. Refresh cache if stale or empty ────────────────────────────────────
    if not cache_is_fresh:
        logger.info("Deployment cache stale/empty for user %s — recomputing.", user_id)

        # a) Watchlist tickers with latest run ID
        watchlist_rows = await db.watchlist.find_many(where={"userId": user_id})
        watchlist_map: Dict[str, str] = {
            w.ticker: w.latestAnalysisRunId
            for w in watchlist_rows
            if w.latestAnalysisRunId
        }

        # b) Recent 30-day StockResults (completed, may overlap watchlist)
        cutoff = now_utc - timedelta(days=30)
        recent_results = await db.stockresult.find_many(
            where={
                "userId": user_id,
                "status": "completed",
                "createdAt": {"gte": cutoff},
            },
            order={"createdAt": "desc"},
        )

        # Deduplicate: latest per ticker, watchlist takes precedence via run ID
        ticker_to_result: Dict[str, Any] = {}
        for r in recent_results:
            if r.ticker not in ticker_to_result:
                ticker_to_result[r.ticker] = r

        # For watchlist tickers that may not appear in recent 30d, fetch by run ID
        watchlist_run_ids = [
            run_id for ticker, run_id in watchlist_map.items()
            if ticker not in ticker_to_result
        ]
        if watchlist_run_ids:
            extra_results = await db.stockresult.find_many(
                where={"runId": {"in": watchlist_run_ids}, "status": "completed"},
            )
            for r in extra_results:
                if r.ticker not in ticker_to_result:
                    ticker_to_result[r.ticker] = r

        if not ticker_to_result:
            logger.info("No completed results found for user %s universe.", user_id)
            # Return empty report; cache nothing
            return DeploymentUpdateResponse(
                generated_at=now_utc.isoformat(),
                cache_age_hours=0.0,
                snapshot=MarketDeployabilitySnapshot(
                    universe_size=0,
                    pct_universe_confirmed=0.0,
                    avg_allocation_delta=None,
                    avg_stop_probability=0.0,
                    regime_stable_pct=0.0,
                    capital_posture="Low",
                ),
                deployable_tickers=[],
                sector_breadth=[],
                no_deployable_message="No capital structurally deployable this cycle.",
            )

        # c) Batch-fetch prior run data for allocation_delta_30d
        prior_run_id_map: Dict[str, str] = {}  # ticker → prior_run_id
        for ticker, result in ticker_to_result.items():
            fo = _parse_full_output(result.fullOutput)
            if fo:
                delta_raw = fo.get("previous_analysis_delta") or {}
                prior_run_id = delta_raw.get("prior_run_id")
                if prior_run_id:
                    prior_run_id_map[ticker] = prior_run_id

        prior_results_by_run: Dict[str, Any] = {}
        if prior_run_id_map:
            all_prior_run_ids = list(set(prior_run_id_map.values()))
            prior_rows = await db.stockresult.find_many(
                where={"runId": {"in": all_prior_run_ids}, "status": "completed"},
            )
            for pr in prior_rows:
                prior_results_by_run[pr.runId] = pr

        # d) Enrich, extract metrics, compute allocation delta
        raw_metrics: Dict[str, Dict[str, Any]] = {}
        for ticker, result in ticker_to_result.items():
            fo = _parse_full_output(result.fullOutput)
            if not fo:
                continue
            moat_score = float(result.moatScore or 5.0)
            fo = _enrich(fo, moat_score)
            metrics = _extract_metrics(ticker, fo, moat_score)

            # Allocation delta: compare recommended_pct with prior run
            allocation_delta: Optional[float] = None
            prior_run_id = prior_run_id_map.get(ticker)
            if prior_run_id and prior_run_id in prior_results_by_run:
                prior_result = prior_results_by_run[prior_run_id]
                prior_fo = _parse_full_output(prior_result.fullOutput)
                if prior_fo:
                    prior_moat = float(prior_result.moatScore or 5.0)
                    prior_fo = _enrich(prior_fo, prior_moat)
                    prior_di = prior_fo.get("decision_intelligence") or {}
                    prior_conviction = prior_di.get("conviction_position") or {}
                    prior_pct = prior_conviction.get("recommended_pct")
                    if prior_pct is not None:
                        allocation_delta = round(
                            metrics["allocationCurrent"] - float(prior_pct), 2
                        )

            metrics["allocationDelta30d"] = allocation_delta
            metrics["sourceRunId"] = result.runId
            raw_metrics[ticker] = metrics

        # e) Upsert cache rows
        for ticker, m in raw_metrics.items():
            await db.deploymentmetricscache.upsert(
                where={"userId_ticker": {"userId": user_id, "ticker": ticker}},
                data={
                    "create": {
                        "userId": user_id,
                        "ticker": ticker,
                        "sector": m["sector"],
                        "allocationCurrent": m["allocationCurrent"],
                        "allocationDelta30d": m["allocationDelta30d"],
                        "confirmationScore": m["confirmationScore"],
                        "evRatio": m["evRatio"],
                        "volAdjEvScore": m["volAdjEvScore"],
                        "stopProbability": m["stopProbability"],
                        "regimeStable": m["regimeStable"],
                        "sourceRunId": m["sourceRunId"],
                        "computedAt": now_utc,
                    },
                    "update": {
                        "sector": m["sector"],
                        "allocationCurrent": m["allocationCurrent"],
                        "allocationDelta30d": m["allocationDelta30d"],
                        "confirmationScore": m["confirmationScore"],
                        "evRatio": m["evRatio"],
                        "volAdjEvScore": m["volAdjEvScore"],
                        "stopProbability": m["stopProbability"],
                        "regimeStable": m["regimeStable"],
                        "sourceRunId": m["sourceRunId"],
                        "computedAt": now_utc,
                    },
                },
            )

        # Reload fresh cached rows
        cached_rows = await db.deploymentmetricscache.find_many(
            where={"userId": user_id},
        )
        cache_age_hours = 0.0

    # ── 4. Build response from cached rows ────────────────────────────────────
    if not cached_rows:
        return DeploymentUpdateResponse(
            generated_at=now_utc.isoformat(),
            cache_age_hours=cache_age_hours,
            snapshot=MarketDeployabilitySnapshot(
                universe_size=0,
                pct_universe_confirmed=0.0,
                avg_allocation_delta=None,
                avg_stop_probability=0.0,
                regime_stable_pct=0.0,
                capital_posture="Low",
            ),
            deployable_tickers=[],
            sector_breadth=[],
            no_deployable_message="No capital structurally deployable this cycle.",
        )

    universe_size = len(cached_rows)

    # ── 5. Compute cross-universe percentiles ─────────────────────────────────
    all_vol_adj_scores = [
        r.volAdjEvScore for r in cached_rows if r.volAdjEvScore is not None
    ]

    # ── 6. Compute sector breadth ─────────────────────────────────────────────
    sector_stats: Dict[str, Dict[str, int]] = {}
    current_sector_scores: Dict[str, int] = {}  # ticker → confirmation_score (for trend)

    for r in cached_rows:
        sec = r.sector or "Unknown"
        current_sector_scores[r.ticker] = r.confirmationScore
        if sec not in sector_stats:
            sector_stats[sec] = {"confirmed": 0, "total": 0}
        sector_stats[sec]["total"] += 1
        if r.confirmationScore >= 4:
            sector_stats[sec]["confirmed"] += 1

    sector_breadth: List[SectorBreadthRow] = []
    for sec, counts in sorted(sector_stats.items()):
        total = counts["total"]
        confirmed = counts["confirmed"]
        pct = round(confirmed / total * 100.0, 1) if total > 0 else 0.0
        trend = _sector_trend(
            sec,
            {t: s for t, s in current_sector_scores.items()},
            {t: s for t, s in prior_sector_scores.items()},
        )
        sector_breadth.append(SectorBreadthRow(
            sector=sec,
            confirmed=confirmed,
            total=total,
            pct_confirmed=pct,
            trend=trend,
        ))

    # ── 7. Apply inclusion criteria ───────────────────────────────────────────
    deployable_tickers: List[DeployableTickerItem] = []

    for r in sorted(cached_rows, key=lambda x: x.ticker):
        # Skip if allocation delta is missing (no prior run to compare)
        if r.allocationDelta30d is None:
            continue

        # Compute vol-adjusted EV percentile
        if r.volAdjEvScore is not None and all_vol_adj_scores:
            vol_adj_pct = _percentile(r.volAdjEvScore, all_vol_adj_scores)
        else:
            vol_adj_pct = 0.0

        # Gate: all 5 criteria must pass
        passes = (
            r.confirmationScore >= 4
            and r.allocationDelta30d > 0
            and vol_adj_pct >= 60.0
            and r.stopProbability <= 25.0
            and r.regimeStable
        )
        if not passes:
            continue

        sec = r.sector or "Unknown"
        sec_stats = sector_stats.get(sec, {"confirmed": 0, "total": 0})
        sector_breadth_pct = (
            round(sec_stats["confirmed"] / sec_stats["total"] * 100.0, 1)
            if sec_stats["total"] > 0
            else 0.0
        )

        deployable_tickers.append(DeployableTickerItem(
            ticker=r.ticker,
            sector=sec,
            allocation_current=round(r.allocationCurrent, 2),
            allocation_delta_30d=round(r.allocationDelta30d, 2),
            confirmation_score=r.confirmationScore,
            vol_adj_ev_percentile=vol_adj_pct,
            stop_probability=round(r.stopProbability, 1),
            sector_breadth_pct=sector_breadth_pct,
        ))

    # ── 8. Compute snapshot metrics ───────────────────────────────────────────
    confirmed_count = sum(1 for r in cached_rows if r.confirmationScore >= 4)
    pct_confirmed = round(confirmed_count / universe_size, 4) if universe_size > 0 else 0.0

    deltas = [
        r.allocationDelta30d for r in cached_rows if r.allocationDelta30d is not None
    ]
    avg_delta = round(sum(deltas) / len(deltas), 2) if deltas else None

    avg_stop = (
        round(sum(r.stopProbability for r in cached_rows) / universe_size, 1)
        if universe_size > 0
        else 0.0
    )

    stable_count = sum(1 for r in cached_rows if r.regimeStable)
    regime_stable_pct = round(stable_count / universe_size * 100.0, 1) if universe_size > 0 else 0.0

    capital_posture = _classify_posture(pct_confirmed, avg_delta, avg_stop)

    snapshot = MarketDeployabilitySnapshot(
        universe_size=universe_size,
        pct_universe_confirmed=round(pct_confirmed * 100.0, 1),
        avg_allocation_delta=avg_delta,
        avg_stop_probability=avg_stop,
        regime_stable_pct=regime_stable_pct,
        capital_posture=capital_posture,
    )

    no_deployable_message: Optional[str] = None
    if not deployable_tickers:
        no_deployable_message = "No capital structurally deployable this cycle."

    return DeploymentUpdateResponse(
        generated_at=now_utc.isoformat(),
        cache_age_hours=round(cache_age_hours, 2),
        snapshot=snapshot,
        deployable_tickers=deployable_tickers,
        sector_breadth=sector_breadth,
        no_deployable_message=no_deployable_message,
    )


# ── Route ─────────────────────────────────────────────────────────────────────

@router.get("/deployment/structural-update", response_model=DeploymentUpdateResponse)
async def get_structural_deployment_update(
    user: User = Depends(get_current_user),
):
    """
    Monthly structural capital deployability report.

    Returns a portfolio-level deployment update based on precomputed metrics
    from the user's tracked universe. Data is extracted from existing analysis
    results — no new analyses are triggered.

    Available to Investor tier and above.
    """
    if not (user.is_admin or has_feature(user, FEAT_DEPLOYMENT_STRUCTURAL)):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "NOT_ENTITLED",
                "message": "Structural Deployment Update requires Investor tier or above.",
                "required_tier": "investor",
            },
        )

    db = await get_db()
    try:
        return await _build_deployment_update(user.id, db)
    except Exception as exc:
        logger.exception("Deployment update failed for user %s: %s", user.id, exc)
        raise HTTPException(status_code=500, detail="Failed to build deployment update.")
