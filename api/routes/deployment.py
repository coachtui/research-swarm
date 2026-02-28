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


class EligibilityFailureItem(BaseModel):
    """One eligibility rule and how many structurally confirmed tickers fail it."""
    rule: str
    label: str
    count: int
    threshold_desc: str


class NearMissTicker(BaseModel):
    """A structurally confirmed ticker that just misses allocation eligibility."""
    ticker: str
    failing_rules: List[str]
    metric_values: Dict[str, float]
    threshold_values: Dict[str, float]
    suggested_action: str


class EligibilityDiagnostics(BaseModel):
    """Pipeline funnel + failure breakdown for the diagnostics panel."""
    evaluated_count: int
    confirmed_count: int
    eligible_count: int
    failure_reasons: List[EligibilityFailureItem]   # ranked by count desc
    near_misses: List[NearMissTicker]               # up to 10, closest first


class DeploymentUpdateResponse(BaseModel):
    snapshot_id: str
    generated_at: str
    ttl_expires_at: str
    cache_age_hours: float
    model_version: str
    ruleset_version: str
    universe_size: int
    confirmed_count: int
    eligible_count: int
    snapshot: MarketDeployabilitySnapshot
    deployable_tickers: List[DeployableTickerItem]
    sector_breadth: List[SectorBreadthRow]
    no_deployable_message: Optional[str]
    eligibility_diagnostics: EligibilityDiagnostics


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


# ── Eligibility diagnostics helpers ───────────────────────────────────────────

# Human-readable metadata for each allocation eligibility rule.
# Keys match the `failing_rules` strings used in NearMissTicker / failure_reasons.
_RULE_META: Dict[str, Tuple[str, str]] = {
    "allocation_delta_positive": (
        "Positive Conviction Delta (30d)",
        "> 0% vs prior run",
    ),
    "vol_adj_ev_percentile": (
        "Vol-Adj EV Percentile",
        "≥ 60th percentile across universe",
    ),
    "stop_probability": (
        "Stop Probability",
        "≤ 25.0%",
    ),
    "regime_stable": (
        "Regime Stability",
        "Not Noise-Dominated or High-Noise",
    ),
}


def _suggest_action(failing: List[str]) -> str:
    """Map top failure reason to an explanatory suggested-focus label."""
    if "stop_probability" in failing:
        return "Stop risk elevated"
    if "vol_adj_ev_percentile" in failing:
        return "Needs cheaper entry"
    if "regime_stable" in failing:
        return "Needs higher stability"
    if "allocation_delta_positive" in failing:
        return "Conviction declining"
    return "Monitor"


def _build_eligibility_diagnostics(
    cached_rows: List[Any],
    all_vol_adj_scores: List[float],
    confirmed_count: int,
    eligible_count: int,
) -> EligibilityDiagnostics:
    """
    For each structurally confirmed ticker (score >= 4), evaluate all
    allocation eligibility predicates and record failures.

    Returns:
        EligibilityDiagnostics with pipeline funnel counts, ranked failure
        reasons, and the top-10 near-miss tickers sorted by fewest failing
        rules then smallest gap to the threshold.

    Notes:
        - Tickers with confirmation_score < 4 are excluded (not structurally
          confirmed) — they never enter the eligibility pipeline.
        - Tickers that pass all rules are already counted in eligible_count;
          they are not included in near_misses.
        - gap_score is a normalised float used for sorting only; not exposed
          in the API response.
    """
    failure_counts: Dict[str, int] = {rule: 0 for rule in _RULE_META}
    near_miss_candidates: List[Dict[str, Any]] = []

    for r in cached_rows:
        if r.confirmationScore < 4:
            continue  # Not structurally confirmed — skip

        vol_adj_pct = (
            _percentile(r.volAdjEvScore, all_vol_adj_scores)
            if r.volAdjEvScore is not None and all_vol_adj_scores
            else 0.0
        )

        failing: List[str] = []
        metric_vals: Dict[str, float] = {}
        threshold_vals: Dict[str, float] = {}
        gap_score = 0.0  # normalised distance from eligibility (for sorting)

        # Rule 1: allocation_delta_positive
        if r.allocationDelta30d is None or r.allocationDelta30d <= 0:
            failing.append("allocation_delta_positive")
            failure_counts["allocation_delta_positive"] += 1
            val = float(r.allocationDelta30d or 0.0)
            metric_vals["allocation_delta_30d"] = round(val, 2)
            threshold_vals["allocation_delta_30d"] = 0.0
            gap_score += min(1.0, max(0.0, (-val) / 10.0 + 0.5))

        # Rule 2: vol_adj_ev_percentile
        if vol_adj_pct < 60.0:
            failing.append("vol_adj_ev_percentile")
            failure_counts["vol_adj_ev_percentile"] += 1
            metric_vals["vol_adj_ev_percentile"] = round(vol_adj_pct, 1)
            threshold_vals["vol_adj_ev_percentile"] = 60.0
            gap_score += (60.0 - vol_adj_pct) / 60.0

        # Rule 3: stop_probability
        if r.stopProbability > 25.0:
            failing.append("stop_probability")
            failure_counts["stop_probability"] += 1
            metric_vals["stop_probability"] = round(r.stopProbability, 1)
            threshold_vals["stop_probability"] = 25.0
            gap_score += min(1.0, (r.stopProbability - 25.0) / 75.0)

        # Rule 4: regime_stable
        if not r.regimeStable:
            failing.append("regime_stable")
            failure_counts["regime_stable"] += 1
            metric_vals["regime_stable"] = 0.0
            threshold_vals["regime_stable"] = 1.0
            gap_score += 1.0  # binary: fully failing

        if failing:
            near_miss_candidates.append({
                "ticker": r.ticker,
                "failing": failing,
                "metric_vals": metric_vals,
                "threshold_vals": threshold_vals,
                "suggested_action": _suggest_action(failing),
                "sort_key": (len(failing), gap_score),
            })

    # Sort: fewest failures first, then smallest gap to threshold
    near_miss_candidates.sort(key=lambda x: x["sort_key"])

    failure_reasons = [
        EligibilityFailureItem(
            rule=rule,
            label=_RULE_META[rule][0],
            count=cnt,
            threshold_desc=_RULE_META[rule][1],
        )
        for rule, cnt in sorted(failure_counts.items(), key=lambda kv: -kv[1])
        if cnt > 0
    ]

    near_misses = [
        NearMissTicker(
            ticker=c["ticker"],
            failing_rules=c["failing"],
            metric_values=c["metric_vals"],
            threshold_values=c["threshold_vals"],
            suggested_action=c["suggested_action"],
        )
        for c in near_miss_candidates[:10]
    ]

    return EligibilityDiagnostics(
        evaluated_count=len(cached_rows),
        confirmed_count=confirmed_count,
        eligible_count=eligible_count,
        failure_reasons=failure_reasons,
        near_misses=near_misses,
    )


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

    # Build eligibility diagnostics (funnel counts + failure reasons + near misses)
    eligibility_diagnostics = _build_eligibility_diagnostics(
        cached_rows,
        all_vol_adj_scores,
        confirmed_count,
        eligible_count,
    )

    # Diagnostic logging — always useful for verifying filter isn't too strict
    logger.info(
        "Deployment diagnostics — scope=%s, evaluated=%d, confirmed=%d, eligible=%d, "
        "top_failures=%s",
        user_id,
        universe_size,
        confirmed_count,
        eligible_count,
        [(f.label, f.count) for f in eligibility_diagnostics.failure_reasons[:3]],
    )

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
        confirmed_count=confirmed_count,
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
        eligibility_diagnostics=eligibility_diagnostics,
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
        confirmed_count=0,
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
        eligibility_diagnostics=EligibilityDiagnostics(
            evaluated_count=0,
            confirmed_count=0,
            eligible_count=0,
            failure_reasons=[],
            near_misses=[],
        ),
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


# ── Stress test models ────────────────────────────────────────────────────────


class StressBaselineResult(BaseModel):
    eligible: int
    pass_rate_structural: float  # % of confirmed tickers that pass all rules


class StressScenarioResult(BaseModel):
    name: str
    eligible: int
    pass_rate_structural: float
    change_vs_baseline: int


class AvgDistanceToThreshold(BaseModel):
    """
    Average shortfall from each threshold, measured only across *failing* confirmed tickers.

    delta:         avg (allocationDelta30d) for tickers failing the delta rule.
                   Negative means below zero (conviction declining).
    ev_percentile: avg (vol_adj_ev_percentile - 60) for tickers below 60th pct.
                   Negative means below threshold.
    stop:          avg (stopProbability - 25) for tickers above 25% stop.
                   Positive means above threshold (elevated risk).
    """
    delta: Optional[float]
    ev_percentile: Optional[float]
    stop: Optional[float]


class EligibilityStressTestResponse(BaseModel):
    evaluated_universe: int
    structural_confirmed: int
    baseline: StressBaselineResult
    scenarios: List[StressScenarioResult]
    dominant_binding_constraint: str
    avg_distance_to_threshold: AvgDistanceToThreshold
    generated_at: str


# ── Stress test session cache (process-lifetime; keyed by user_id) ─────────────
# Value: (snapshot_bucket_str, result) — replaced when bucket changes.
_stress_test_cache: Dict[str, Tuple[str, EligibilityStressTestResponse]] = {}


# ── Stress test helpers ────────────────────────────────────────────────────────

def _compute_deployability_index(rows: List[Any]) -> float:
    """
    Replicates the frontend getDeployabilityIndex formula:
      DI = pct_confirmed*0.35 + regime_stable_pct*0.30
           + (100 - avg_stop)*0.20 + avg_breadth_pct*0.15
    Returns 0–100.
    """
    n = len(rows)
    if n == 0:
        return 0.0
    pct_confirmed = sum(1 for r in rows if r.confirmationScore >= 4) / n * 100.0
    regime_stable_pct = sum(1 for r in rows if r.regimeStable) / n * 100.0
    avg_stop = sum(r.stopProbability for r in rows) / n

    sector_stats: Dict[str, Dict[str, int]] = {}
    for r in rows:
        sec = r.sector or "Unknown"
        if sec not in sector_stats:
            sector_stats[sec] = {"confirmed": 0, "total": 0}
        sector_stats[sec]["total"] += 1
        if r.confirmationScore >= 4:
            sector_stats[sec]["confirmed"] += 1

    breadth_pcts = [
        s["confirmed"] / s["total"] * 100.0
        for s in sector_stats.values() if s["total"] > 0
    ]
    avg_breadth = sum(breadth_pcts) / len(breadth_pcts) if breadth_pcts else 0.0

    return round(
        pct_confirmed * 0.35
        + regime_stable_pct * 0.30
        + (100.0 - avg_stop) * 0.20
        + avg_breadth * 0.15,
        1,
    )


def _count_eligible_with_params(
    confirmed_rows: List[Any],
    all_vol_adj_scores: List[float],
    *,
    delta_mode: str = "positive",   # "positive" (>0) | "nonneg" (>=0) | "any"
    ev_min: float = 60.0,
    stop_max: float = 25.0,
) -> int:
    """
    Count confirmed tickers that pass all eligibility gates under the given params.
    Regime stability is never relaxed — it stays as a hard gate.
    """
    total = 0
    for r in confirmed_rows:
        # Delta check
        if delta_mode == "positive":
            if r.allocationDelta30d is None or r.allocationDelta30d <= 0:
                continue
        elif delta_mode == "nonneg":
            if r.allocationDelta30d is None or r.allocationDelta30d < 0:
                continue
        # else "any" → skip delta check

        # EV percentile
        vol_pct = (
            _percentile(r.volAdjEvScore, all_vol_adj_scores)
            if r.volAdjEvScore is not None and all_vol_adj_scores
            else 0.0
        )
        if vol_pct < ev_min:
            continue

        # Stop probability
        if r.stopProbability > stop_max:
            continue

        # Regime stability — always required
        if not r.regimeStable:
            continue

        total += 1
    return total


def _run_stress_simulation(
    cached_rows: List[Any],
    all_vol_adj_scores: List[float],
) -> EligibilityStressTestResponse:
    """
    Pure simulation — reads existing cached metrics, no DB writes.

    Only structurally confirmed tickers (confirmationScore >= 4) enter
    the eligibility pipeline; others are excluded from scenario counts.
    """
    now_utc = datetime.now(timezone.utc)
    universe_size = len(cached_rows)
    confirmed_rows = [r for r in cached_rows if r.confirmationScore >= 4]
    confirmed_count = len(confirmed_rows)

    def pct(n: int) -> float:
        return round(n / confirmed_count * 100.0, 1) if confirmed_count > 0 else 0.0

    # ── Baseline ──────────────────────────────────────────────────────────────
    baseline_n = _count_eligible_with_params(
        confirmed_rows, all_vol_adj_scores,
        delta_mode="positive", ev_min=60.0, stop_max=25.0,
    )
    baseline = StressBaselineResult(
        eligible=baseline_n,
        pass_rate_structural=pct(baseline_n),
    )

    # ── Scenarios ─────────────────────────────────────────────────────────────
    scenarios: List[StressScenarioResult] = []

    def scenario(name: str, n: int) -> StressScenarioResult:
        return StressScenarioResult(
            name=name,
            eligible=n,
            pass_rate_structural=pct(n),
            change_vs_baseline=n - baseline_n,
        )

    # A — Relax Conviction Acceleration
    sc_a1 = _count_eligible_with_params(confirmed_rows, all_vol_adj_scores, delta_mode="nonneg")
    scenarios.append(scenario("Delta ≥ 0 (non-negative)", sc_a1))

    sc_a2 = _count_eligible_with_params(confirmed_rows, all_vol_adj_scores, delta_mode="any")
    scenarios.append(scenario("Remove Delta Filter", sc_a2))

    # B — Relax EV threshold
    for ev_min in [55.0, 50.0, 45.0]:
        n = _count_eligible_with_params(confirmed_rows, all_vol_adj_scores, ev_min=ev_min)
        scenarios.append(scenario(f"EV ≥ {int(ev_min)}th percentile", n))

    # C — Relax Stop probability
    for stop_max in [30.0, 35.0]:
        n = _count_eligible_with_params(confirmed_rows, all_vol_adj_scores, stop_max=stop_max)
        scenarios.append(scenario(f"Stop ≤ {int(stop_max)}%", n))

    # D — Combined moderate relaxation
    sc_d = _count_eligible_with_params(
        confirmed_rows, all_vol_adj_scores,
        delta_mode="nonneg", ev_min=55.0, stop_max=30.0,
    )
    scenarios.append(scenario("Combined: Delta ≥ 0, EV ≥ 55, Stop ≤ 30%", sc_d))

    # E — Regime-conditional thresholds
    di = _compute_deployability_index(cached_rows)
    if di >= 60.0:
        sc_e = _count_eligible_with_params(
            confirmed_rows, all_vol_adj_scores, ev_min=55.0, stop_max=30.0,
        )
        sc_e_name = f"Regime-Conditional (DI={di:.0f}, Risk-On: EV ≥ 55, Stop ≤ 30%)"
    else:
        sc_e = baseline_n
        sc_e_name = f"Regime-Conditional (DI={di:.0f}, Risk-Off: strict baseline)"
    scenarios.append(scenario(sc_e_name, sc_e))

    # ── Dominant binding constraint ────────────────────────────────────────────
    # Count each rule's failures independently (not mutually exclusive)
    delta_fail = 0
    ev_fail = 0
    stop_fail = 0
    regime_fail = 0

    delta_shortfalls: List[float] = []
    ev_gaps: List[float] = []
    stop_excesses: List[float] = []

    for r in confirmed_rows:
        vol_pct = (
            _percentile(r.volAdjEvScore, all_vol_adj_scores)
            if r.volAdjEvScore is not None and all_vol_adj_scores
            else 0.0
        )
        if r.allocationDelta30d is None or r.allocationDelta30d <= 0:
            delta_fail += 1
            delta_shortfalls.append(float(r.allocationDelta30d or 0.0))
        if vol_pct < 60.0:
            ev_fail += 1
            ev_gaps.append(vol_pct - 60.0)
        if r.stopProbability > 25.0:
            stop_fail += 1
            stop_excesses.append(r.stopProbability - 25.0)
        if not r.regimeStable:
            regime_fail += 1

    rule_failures: Dict[str, int] = {
        "Delta": delta_fail,
        "EV Percentile": ev_fail,
        "Stop Probability": stop_fail,
        "Regime Stability": regime_fail,
    }
    dominant = max(rule_failures, key=lambda k: rule_failures[k])

    avg_dist = AvgDistanceToThreshold(
        delta=round(sum(delta_shortfalls) / len(delta_shortfalls), 2) if delta_shortfalls else None,
        ev_percentile=round(sum(ev_gaps) / len(ev_gaps), 1) if ev_gaps else None,
        stop=round(sum(stop_excesses) / len(stop_excesses), 1) if stop_excesses else None,
    )

    return EligibilityStressTestResponse(
        evaluated_universe=universe_size,
        structural_confirmed=confirmed_count,
        baseline=baseline,
        scenarios=scenarios,
        dominant_binding_constraint=dominant,
        avg_distance_to_threshold=avg_dist,
        generated_at=now_utc.isoformat(),
    )


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


# ── Eligibility stress-test route (admin-only) ────────────────────────────────

@router.get("/deployment/eligibility-stress-test/admin", response_model=EligibilityStressTestResponse)
async def get_admin_eligibility_stress_test(
    admin: User = Depends(require_admin),
):
    """
    Allocation Eligibility Stress-Test Simulation — Admin Only.

    Reads from the current admin snapshot cache (no DB writes, no new analyses).
    Simulates how eligible count changes under independently-relaxed threshold
    variants.  Results are cached in-process per snapshot bucket (24h TTL
    matching the underlying deployment cache).

    Scenarios:
      A — Relax Conviction Delta (>0 → ≥0; then remove entirely)
      B — Relax EV Percentile  (60 → 55 / 50 / 45)
      C — Relax Stop Probability (25 → 30 / 35%)
      D — Combined moderate relaxation (delta≥0, EV≥55, stop≤30%)
      E — Regime-conditional (DI≥60 → relaxed; else strict baseline)

    Returns:
      Baseline + 9 scenario results, dominant binding constraint,
      avg shortfall per rule for failing confirmed tickers.
    """
    db = await get_db()
    try:
        now_utc = datetime.now(timezone.utc)
        current_bucket = _snapshot_bucket(now_utc)
        bucket_str = current_bucket.isoformat()

        # ── In-process cache ──────────────────────────────────────────────────
        cached_entry = _stress_test_cache.get(_ADMIN_SENTINEL)
        if cached_entry and cached_entry[0] == bucket_str:
            logger.debug("Stress test cache hit for admin bucket %s", bucket_str)
            return cached_entry[1]

        # ── Load current admin snapshot rows ──────────────────────────────────
        rows = await db.deploymentmetricscache.find_many(
            where={
                "userId": _ADMIN_SENTINEL,
                "snapshotBucket": current_bucket,
                "modelVersion": MODEL_VERSION,
            },
            order={"ticker": "asc"},
        )
        if not rows:
            # No cache yet — trigger a full build first, then retry once
            logger.info(
                "Stress test: admin snapshot empty for bucket %s — triggering build.",
                bucket_str,
            )
            await _build_deployment_update(_ADMIN_SENTINEL, db, admin_mode=True)
            rows = await db.deploymentmetricscache.find_many(
                where={
                    "userId": _ADMIN_SENTINEL,
                    "snapshotBucket": current_bucket,
                    "modelVersion": MODEL_VERSION,
                },
                order={"ticker": "asc"},
            )

        if not rows:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "no_universe_data",
                    "message": "No universe data available. Run at least one analysis first.",
                },
            )

        all_vol_adj = [r.volAdjEvScore for r in rows if r.volAdjEvScore is not None]
        result = _run_stress_simulation(rows, all_vol_adj)

        _stress_test_cache[_ADMIN_SENTINEL] = (bucket_str, result)
        logger.info(
            "Stress test complete — universe=%d, confirmed=%d, baseline=%d, dominant=%s",
            result.evaluated_universe,
            result.structural_confirmed,
            result.baseline.eligible,
            result.dominant_binding_constraint,
        )
        return result

    except HTTPException:
        raise
    except _TableNotFoundError as exc:
        logger.error("deployment_metrics_cache missing for stress test: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={
                "error": "deployment_cache_not_migrated",
                "message": "Run: prisma migrate deploy --schema=db/schema.prisma",
            },
        )
    except Exception as exc:
        logger.exception("Stress test failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to run eligibility stress test.")
