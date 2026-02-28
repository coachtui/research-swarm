"""
Structural Deployment Update — Investor-tier capital deployability report.

Reads from existing StockResult.fullOutput rows. NO new LLM calls.
Metrics are extracted, cached per snapshot bucket (UTC midnight), and returned
as a structured report.

Universe: user's watchlist tickers + any ticker analyzed in the last 30 days.

Inclusion criteria (all must pass):
  1. confirmation_score >= 4  (4-of-5 moat components above threshold)
  2. allocation_delta_30d > 0  (positive conviction shift vs prior run)
  3. vol_adj_ev_percentile >= 60  (cross-universe rank)
  4. stop_probability <= 25.0 %
  5. regime_stable == True  (not Noise Dominated or High Noise)

Cache design:
  - Snapshot bucket = UTC midnight of the generation day
  - Unique key per row: (userId, snapshotBucket, ticker)
  - Cache hit = rows with matching snapshotBucket + MODEL_VERSION exist
  - Model version bump automatically invalidates same-day cache on next request

# Future: integrate Allocation Impact Simulation
# Future: integrate Market Deployability Index chart
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.dependencies import get_current_user, require_admin
from api.lib.db import get_db
from api.lib.entitlements import FEAT_DEPLOYMENT_STRUCTURAL, has_feature
from api.models.auth import User

logger = logging.getLogger(__name__)

# Guard import: TableNotFoundError signals an unapplied migration.
# Fall back to a never-matching stub if the prisma version doesn't export it.
try:
    from prisma.errors import TableNotFoundError as _TableNotFoundError
except ImportError:  # pragma: no cover
    class _TableNotFoundError(Exception):  # type: ignore[no-redef]
        pass

router = APIRouter()

MODEL_VERSION = "1.1.0"
RULESET_VERSION = "1.0.0"
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
    avg_stop_probability_trend: str  # "rising" | "stable" | "falling"
    regime_stable_pct: float
    capital_posture: str     # "Low" | "Moderate" | "Expanding"
    exposure_ceiling: float  # suggested max portfolio exposure %


class DeploymentUpdateResponse(BaseModel):
    snapshot_id: str
    generated_at: str
    ttl_expires_at: str
    cache_age_hours: float
    model_version: str
    ruleset_version: str
    universe_size: int
    eligible_count: int
    snapshot: MarketDeployabilitySnapshot
    deployable_tickers: List[DeployableTickerItem]
    sector_breadth: List[SectorBreadthRow]
    no_deployable_message: Optional[str]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _compute_universe_hash(tickers: List[str]) -> str:
    """SHA-256[:16] fingerprint of the sorted ticker set."""
    return hashlib.sha256(",".join(sorted(tickers)).encode()).hexdigest()[:16]


def _snapshot_bucket(dt: datetime) -> datetime:
    """Truncate to UTC midnight (the 24h snapshot day bucket)."""
    return dt.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)


def _stop_trend(current_avg: float, prior_avg: Optional[float]) -> str:
    """
    Compare current vs prior avg stop probability.
    'rising'  = stop probability worsening (higher risk).
    'falling' = stop probability improving (lower risk).
    """
    if prior_avg is None:
        return "stable"
    delta = current_avg - prior_avg
    if delta > 2.0:
        return "rising"
    if delta < -2.0:
        return "falling"
    return "stable"


def _classify_posture(confirmed_count: int, universe_size: int) -> Tuple[str, float]:
    """
    Returns (capital_posture, exposure_ceiling_pct).

    Thresholds:
      confirmed/universe < 0.10 → Low,      exposure_ceiling = 50%
      confirmed/universe < 0.25 → Moderate,  exposure_ceiling = 65%
      confirmed/universe >= 0.25 → Expanding, exposure_ceiling = 85%
    """
    if universe_size == 0:
        return "Low", 50.0
    ratio = confirmed_count / universe_size
    if ratio >= 0.25:
        return "Expanding", 85.0
    if ratio >= 0.10:
        return "Moderate", 65.0
    return "Low", 50.0


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


def _enrich(full_output: Dict[str, Any], moat_score: float) -> Dict[str, Any]:
    """Apply on-the-fly DI enrichment to populate decision_intelligence. Fails silently."""
    try:
        from api.lib.decision_intelligence import enrich_with_decision_intelligence
        return enrich_with_decision_intelligence(full_output, moat_score)
    except Exception as exc:
        logger.warning("DI enrichment failed for deployment metrics: %s", exc)
        return full_output


def _extract_metrics(
    ticker: str,
    full_output: Dict[str, Any],
    moat_score: float,
) -> Dict[str, Any]:
    """
    Extract all deployment-relevant per-ticker metrics from an enriched full_output.
    Returns a dict with Prisma camelCase field names.
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

    # Sector
    sector = (
        peer.get("sector")
        or valuation_metrics.get("sector")
        or "Unknown"
    )

    # Allocation current
    allocation_current = float(conviction.get("recommended_pct") or 0.0)

    # Confirmation score (0–5)
    confirmation_score = 0
    for field, threshold in _CONF_THRESHOLDS.items():
        value = moat_bd.get(field)
        if value is not None and float(value) >= threshold:
            confirmation_score += 1

    # EV ratio
    prob_ev = price_targets_raw.get("probability_weighted_ev")
    current_price = valuation_metrics.get("current_price") or di.get("current_price")
    ev_ratio: Optional[float] = None
    if prob_ev and current_price and float(current_price) > 0:
        ev_ratio = round(float(prob_ev) / float(current_price), 4)

    # Stop probability
    stop_probability = float(
        stop_prob_raw.get("effective_stop_probability_pct") or 50.0
    )

    # Regime stability
    noise_regime = noise_filter.get("noise_regime", "")
    regime_stable = noise_regime not in _UNSTABLE_REGIMES

    # Vol-adjusted EV score (used for cross-universe percentile ranking)
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


def _percentile(value: float, all_values: List[float]) -> float:
    """Return 0–100 rank-based percentile of value within all_values."""
    if not all_values:
        return 50.0
    rank = sum(1 for v in all_values if v <= value)
    return round(rank / len(all_values) * 100.0, 1)


def _sector_trend(
    sector_name: str,
    ticker_to_sector: Dict[str, str],
    curr_scores: Dict[str, int],
    prior_scores: Dict[str, int],
) -> str:
    """
    Compare avg confirmation score for a sector between current and prior snapshot.
    Only compares tickers present in both snapshots.
    """
    sector_tickers = {t for t, s in ticker_to_sector.items() if s == sector_name}
    common = sector_tickers & set(prior_scores.keys())
    if not common:
        return "stable"
    avg_curr = sum(curr_scores[t] for t in common if t in curr_scores) / len(common)
    avg_prior = sum(prior_scores[t] for t in common) / len(common)
    if avg_curr > avg_prior + 0.1:
        return "rising"
    if avg_curr < avg_prior - 0.1:
        return "falling"
    return "stable"


# ── Core service function ──────────────────────────────────────────────────────

async def _build_deployment_update(
    user_id: str,
    db,
    *,
    admin_mode: bool = False,
) -> DeploymentUpdateResponse:
    """
    Build (or serve from cache) the structural deployment update.

    user_id   — the cache key; pass "__admin_global__" for platform-wide admin view.
    admin_mode — when True, universe queries span ALL users (no userId filter).
    """
    now_utc = datetime.now(timezone.utc)
    current_bucket = _snapshot_bucket(now_utc)
    ttl_expires = current_bucket + timedelta(hours=_CACHE_TTL_HOURS)

    # ── 1. Check cache: look for rows matching today's bucket + MODEL_VERSION ──
    cached_rows = await db.deploymentmetricscache.find_many(
        where={
            "userId": user_id,
            "snapshotBucket": current_bucket,
            "modelVersion": MODEL_VERSION,
        },
        order={"ticker": "asc"},
    )

    cache_age_hours = 0.0
    cache_is_fresh = bool(cached_rows)
    if cached_rows:
        generated_at = cached_rows[0].generatedAt
        if generated_at.tzinfo is None:
            generated_at = generated_at.replace(tzinfo=timezone.utc)
        cache_age_hours = round((now_utc - generated_at).total_seconds() / 3600.0, 2)

    # ── 2. Load prior snapshot rows (for trend computation) ───────────────────
    prior_all = await db.deploymentmetricscache.find_many(
        where={
            "userId": user_id,
            "snapshotBucket": {"lt": current_bucket},
        },
        order={"snapshotBucket": "desc"},
        take=200,
    )
    prior_rows: List[Any] = []
    if prior_all:
        prior_bucket = prior_all[0].snapshotBucket
        prior_rows = [r for r in prior_all if r.snapshotBucket == prior_bucket]

    prior_scores: Dict[str, int] = {r.ticker: r.confirmationScore for r in prior_rows}
    prior_stops: Dict[str, float] = {r.ticker: r.stopProbability for r in prior_rows}

    # ── 3. Refresh cache if stale / empty ────────────────────────────────────
    snapshot_id: str
    if not cache_is_fresh:
        scope_label = "all users" if admin_mode else f"user {user_id}"
        logger.info("Deployment cache miss for %s bucket %s — recomputing.", scope_label, current_bucket.date())
        snapshot_id = str(uuid.uuid4())

        # a) Watchlist tickers with latest run ID
        if admin_mode:
            watchlist_rows = await db.watchlist.find_many()
        else:
            watchlist_rows = await db.watchlist.find_many(where={"userId": user_id})
        watchlist_map: Dict[str, str] = {
            w.ticker: w.latestAnalysisRunId
            for w in watchlist_rows
            if w.latestAnalysisRunId
        }

        # b) Recent 30-day completed StockResults
        cutoff = now_utc - timedelta(days=30)
        if admin_mode:
            recent_results = await db.stockresult.find_many(
                where={"status": "completed", "createdAt": {"gte": cutoff}},
                order={"createdAt": "desc"},
            )
        else:
            recent_results = await db.stockresult.find_many(
                where={
                    "userId": user_id,
                    "status": "completed",
                    "createdAt": {"gte": cutoff},
                },
                order={"createdAt": "desc"},
            )

        # Deduplicate: latest per ticker, watchlist takes precedence
        ticker_to_result: Dict[str, Any] = {}
        for r in recent_results:
            if r.ticker not in ticker_to_result:
                ticker_to_result[r.ticker] = r

        # Fetch watchlist tickers that may not appear in recent 30d
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
            logger.info("No completed results for %s universe.", scope_label)
            return _empty_response(snapshot_id, now_utc, ttl_expires, cache_age_hours)

        # c) Batch-fetch prior run data for allocation_delta_30d
        prior_run_id_map: Dict[str, str] = {}
        for ticker, result in ticker_to_result.items():
            fo = _parse_full_output(result.fullOutput)
            if fo:
                delta_raw = fo.get("previous_analysis_delta") or {}
                prior_run_id = delta_raw.get("prior_run_id")
                if prior_run_id:
                    prior_run_id_map[ticker] = prior_run_id

        prior_results_by_run: Dict[str, Any] = {}
        if prior_run_id_map:
            all_prior_ids = list(set(prior_run_id_map.values()))
            prior_result_rows = await db.stockresult.find_many(
                where={"runId": {"in": all_prior_ids}, "status": "completed"},
            )
            for pr in prior_result_rows:
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

            allocation_delta: Optional[float] = None
            prior_run_id = prior_run_id_map.get(ticker)
            if prior_run_id and prior_run_id in prior_results_by_run:
                pr = prior_results_by_run[prior_run_id]
                pfo = _parse_full_output(pr.fullOutput)
                if pfo:
                    pfo = _enrich(pfo, float(pr.moatScore or 5.0))
                    prior_pct = (pfo.get("decision_intelligence") or {}) \
                        .get("conviction_position", {}) \
                        .get("recommended_pct")
                    if prior_pct is not None:
                        allocation_delta = round(
                            metrics["allocationCurrent"] - float(prior_pct), 2
                        )

            metrics["allocationDelta30d"] = allocation_delta
            metrics["sourceRunId"] = result.runId
            raw_metrics[ticker] = metrics

        # e) Compute snapshot-level aggregates before upsert
        universe_tickers = list(raw_metrics.keys())
        universe_hash = _compute_universe_hash(universe_tickers)
        universe_size = len(universe_tickers)

        # Confirmed = confirmation_score >= 4 (preliminary, for posture)
        confirmed_count_prelim = sum(
            1 for m in raw_metrics.values() if m["confirmationScore"] >= 4
        )
        capital_posture, exposure_ceiling = _classify_posture(confirmed_count_prelim, universe_size)

        # Eligible count = tickers passing all inclusion criteria (need percentile first)
        # Compute vol-adj percentile across universe
        all_vol_scores = [
            m["volAdjEvScore"] for m in raw_metrics.values() if m["volAdjEvScore"] is not None
        ]
        eligible_count = 0
        for m in raw_metrics.values():
            if m["allocationDelta30d"] is None:
                continue
            vol_pct = _percentile(m["volAdjEvScore"], all_vol_scores) if m["volAdjEvScore"] is not None else 0.0
            if (
                m["confirmationScore"] >= 4
                and m["allocationDelta30d"] > 0
                and vol_pct >= 60.0
                and m["stopProbability"] <= 25.0
                and m["regimeStable"]
            ):
                eligible_count += 1

        # f) Upsert all ticker rows
        for ticker, m in raw_metrics.items():
            await db.deploymentmetricscache.upsert(
                where={"userId_snapshotBucket_ticker": {
                    "userId": user_id,
                    "snapshotBucket": current_bucket,
                    "ticker": ticker,
                }},
                data={
                    "create": {
                        "userId": user_id,
                        "snapshotId": snapshot_id,
                        "snapshotBucket": current_bucket,
                        "universeHash": universe_hash,
                        "modelVersion": MODEL_VERSION,
                        "rulesetVersion": RULESET_VERSION,
                        "universeSize": universe_size,
                        "eligibleCount": eligible_count,
                        "capitalPosture": capital_posture,
                        "exposureCeiling": exposure_ceiling,
                        "generatedAt": now_utc,
                        "ttlExpiresAt": ttl_expires,
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
                    },
                    "update": {
                        "snapshotId": snapshot_id,
                        "universeHash": universe_hash,
                        "modelVersion": MODEL_VERSION,
                        "rulesetVersion": RULESET_VERSION,
                        "universeSize": universe_size,
                        "eligibleCount": eligible_count,
                        "capitalPosture": capital_posture,
                        "exposureCeiling": exposure_ceiling,
                        "generatedAt": now_utc,
                        "ttlExpiresAt": ttl_expires,
                        "sector": m["sector"],
                        "allocationCurrent": m["allocationCurrent"],
                        "allocationDelta30d": m["allocationDelta30d"],
                        "confirmationScore": m["confirmationScore"],
                        "evRatio": m["evRatio"],
                        "volAdjEvScore": m["volAdjEvScore"],
                        "stopProbability": m["stopProbability"],
                        "regimeStable": m["regimeStable"],
                        "sourceRunId": m["sourceRunId"],
                    },
                },
            )

        # Reload fresh cached rows
        cached_rows = await db.deploymentmetricscache.find_many(
            where={
                "userId": user_id,
                "snapshotBucket": current_bucket,
                "modelVersion": MODEL_VERSION,
            },
            order={"ticker": "asc"},
        )
        cache_age_hours = 0.0
    else:
        snapshot_id = cached_rows[0].snapshotId

    # ── 4. Guard: empty universe after refresh ───────────────────────────────
    if not cached_rows:
        return _empty_response(snapshot_id, now_utc, ttl_expires, cache_age_hours)

    # ── 5. Build response from cached rows ────────────────────────────────────
    universe_size = len(cached_rows)

    # Cross-universe vol-adj percentile
    all_vol_adj_scores = [
        r.volAdjEvScore for r in cached_rows if r.volAdjEvScore is not None
    ]

    # Sector stats + ticker→sector mapping
    sector_stats: Dict[str, Dict[str, int]] = {}
    ticker_to_sector: Dict[str, str] = {}
    curr_scores: Dict[str, int] = {}

    for r in cached_rows:
        sec = r.sector or "Unknown"
        ticker_to_sector[r.ticker] = sec
        curr_scores[r.ticker] = r.confirmationScore
        if sec not in sector_stats:
            sector_stats[sec] = {"confirmed": 0, "total": 0}
        sector_stats[sec]["total"] += 1
        if r.confirmationScore >= 4:
            sector_stats[sec]["confirmed"] += 1

    # Sector breadth rows
    sector_breadth: List[SectorBreadthRow] = []
    for sec, counts in sorted(sector_stats.items()):
        total = counts["total"]
        confirmed = counts["confirmed"]
        pct = round(confirmed / total * 100.0, 1) if total > 0 else 0.0
        trend = _sector_trend(sec, ticker_to_sector, curr_scores, prior_scores)
        sector_breadth.append(SectorBreadthRow(
            sector=sec,
            confirmed=confirmed,
            total=total,
            pct_confirmed=pct,
            trend=trend,
        ))

    # Apply inclusion criteria
    deployable_tickers: List[DeployableTickerItem] = []
    for r in cached_rows:  # already sorted alphabetically
        if r.allocationDelta30d is None:
            continue

        vol_adj_pct = (
            _percentile(r.volAdjEvScore, all_vol_adj_scores)
            if r.volAdjEvScore is not None and all_vol_adj_scores
            else 0.0
        )

        if not (
            r.confirmationScore >= 4
            and r.allocationDelta30d > 0
            and vol_adj_pct >= 60.0
            and r.stopProbability <= 25.0
            and r.regimeStable
        ):
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

    # Snapshot aggregates
    confirmed_count = sum(1 for r in cached_rows if r.confirmationScore >= 4)
    pct_confirmed = confirmed_count / universe_size if universe_size > 0 else 0.0

    deltas = [r.allocationDelta30d for r in cached_rows if r.allocationDelta30d is not None]
    avg_delta = round(sum(deltas) / len(deltas), 2) if deltas else None

    avg_stop = (
        round(sum(r.stopProbability for r in cached_rows) / universe_size, 1)
        if universe_size > 0 else 0.0
    )

    # Stop probability trend vs prior snapshot
    prior_avg_stop: Optional[float] = None
    if prior_stops:
        common_tickers = [t for t in prior_stops if t in {r.ticker for r in cached_rows}]
        if common_tickers:
            prior_avg_stop = sum(prior_stops[t] for t in common_tickers) / len(common_tickers)
    stop_prob_trend = _stop_trend(avg_stop, prior_avg_stop)

    stable_count = sum(1 for r in cached_rows if r.regimeStable)
    regime_stable_pct = round(stable_count / universe_size * 100.0, 1) if universe_size > 0 else 0.0

    capital_posture, exposure_ceiling = _classify_posture(confirmed_count, universe_size)

    # Use denormalized snapshot metadata from cached rows when available
    eligible_count = len(deployable_tickers)

    # Determine ttl_expires_at: prefer stored value, fall back to computed
    ttl_stored = getattr(cached_rows[0], "ttlExpiresAt", None)
    if ttl_stored is not None:
        if ttl_stored.tzinfo is None:
            ttl_stored = ttl_stored.replace(tzinfo=timezone.utc)
        ttl_expires = ttl_stored

    no_deployable_message: Optional[str] = None
    if not deployable_tickers:
        no_deployable_message = "No capital structurally deployable this cycle."

    return DeploymentUpdateResponse(
        snapshot_id=snapshot_id,
        generated_at=now_utc.isoformat(),
        ttl_expires_at=ttl_expires.isoformat(),
        cache_age_hours=cache_age_hours,
        model_version=MODEL_VERSION,
        ruleset_version=RULESET_VERSION,
        universe_size=universe_size,
        eligible_count=eligible_count,
        snapshot=MarketDeployabilitySnapshot(
            universe_size=universe_size,
            pct_universe_confirmed=round(pct_confirmed * 100.0, 1),
            avg_allocation_delta=avg_delta,
            avg_stop_probability=avg_stop,
            avg_stop_probability_trend=stop_prob_trend,
            regime_stable_pct=regime_stable_pct,
            capital_posture=capital_posture,
            exposure_ceiling=exposure_ceiling,
        ),
        deployable_tickers=deployable_tickers,
        sector_breadth=sector_breadth,
        no_deployable_message=no_deployable_message,
    )


def _empty_response(
    snapshot_id: str,
    now_utc: datetime,
    ttl_expires: datetime,
    cache_age_hours: float,
) -> DeploymentUpdateResponse:
    """Return a well-formed empty response when the user has no universe data."""
    return DeploymentUpdateResponse(
        snapshot_id=snapshot_id,
        generated_at=now_utc.isoformat(),
        ttl_expires_at=ttl_expires.isoformat(),
        cache_age_hours=cache_age_hours,
        model_version=MODEL_VERSION,
        ruleset_version=RULESET_VERSION,
        universe_size=0,
        eligible_count=0,
        snapshot=MarketDeployabilitySnapshot(
            universe_size=0,
            pct_universe_confirmed=0.0,
            avg_allocation_delta=None,
            avg_stop_probability=0.0,
            avg_stop_probability_trend="stable",
            regime_stable_pct=0.0,
            capital_posture="Low",
            exposure_ceiling=50.0,
        ),
        deployable_tickers=[],
        sector_breadth=[],
        no_deployable_message="No capital structurally deployable this cycle.",
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
    except _TableNotFoundError as exc:
        # The deployment_metrics_cache table has not been migrated yet.
        # Return 503 (not 500) so the client and monitoring can distinguish
        # a schema gap from a genuine application error.
        logger.error(
            "deployment_metrics_cache table missing — run: "
            "prisma migrate deploy --schema=db/schema.prisma  (%s)",
            exc,
        )
        raise HTTPException(
            status_code=503,
            detail={
                "error": "deployment_cache_not_migrated",
                "message": (
                    "Deployment cache table not migrated yet. "
                    "Run: prisma migrate deploy --schema=db/schema.prisma"
                ),
                "model_version": MODEL_VERSION,
                "ruleset_version": RULESET_VERSION,
            },
        )
    except Exception as exc:
        logger.exception("Deployment update failed for user %s: %s", user.id, exc)
        raise HTTPException(status_code=500, detail="Failed to build deployment update.")


# ── Admin route (platform-wide, all users) ────────────────────────────────────

_ADMIN_SENTINEL = "__admin_global__"


@router.get("/deployment/structural-update/admin", response_model=DeploymentUpdateResponse)
async def get_admin_structural_deployment_update(
    admin: User = Depends(require_admin),
):
    """
    Platform-wide structural capital deployability snapshot.

    Admin-only. Aggregates across ALL users' watchlists and analyses —
    no per-user filter. Results are cached under the sentinel userId
    "__admin_global__" with the same 24-hour snapshot bucket TTL.
    """
    db = await get_db()
    try:
        return await _build_deployment_update(_ADMIN_SENTINEL, db, admin_mode=True)
    except _TableNotFoundError as exc:
        logger.error(
            "deployment_metrics_cache table missing — run: "
            "prisma migrate deploy --schema=db/schema.prisma  (%s)",
            exc,
        )
        raise HTTPException(
            status_code=503,
            detail={
                "error": "deployment_cache_not_migrated",
                "message": (
                    "Deployment cache table not migrated yet. "
                    "Run: prisma migrate deploy --schema=db/schema.prisma"
                ),
                "model_version": MODEL_VERSION,
                "ruleset_version": RULESET_VERSION,
            },
        )
    except Exception as exc:
        logger.exception("Admin deployment update failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to build admin deployment update.")
