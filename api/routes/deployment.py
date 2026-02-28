"""
Structural Deployment Update — Investor-tier capital deployability report.

Reads from existing StockResult.fullOutput rows. NO new LLM calls.
Metrics are extracted, cached per snapshot bucket (UTC midnight), and returned
as a structured report.

Universe: user's watchlist tickers + any ticker analyzed in the last 30 days.

Inclusion criteria (all must pass):
  1. confirmation_score >= 4  (4-of-5 moat components above threshold)
  2. allocation_delta_30d > 0  (positive conviction shift vs prior run)
  3. vol_adj_ev_percentile >= 60  (cross-universe mid-rank percentile; skipped when n < 5)
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
import math
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

MODEL_VERSION = "1.2.0"
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
    vol_adj_ev_percentile: Optional[float]  # 0–100; None when universe < 5 (ranking disabled)
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
    # 2 = fails exactly 1 allocation rule, 3 = fails exactly 2, 0 = fails 3+
    tier: int


class EligibilityDiagnostics(BaseModel):
    """Pipeline funnel + failure breakdown for the diagnostics panel."""
    evaluated_count: int
    confirmed_count: int
    eligible_count: int
    failure_reasons: List[EligibilityFailureItem]   # ranked by count desc
    near_misses: List[NearMissTicker]               # up to 10, closest first
    # Tier 1 = passes all rules; 2 = fails 1; 3 = fails 2 (counts across all confirmed)
    tier_counts: Dict[int, int]


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
    sector_coverage_label: str   # e.g. "Sector coverage: 87% (66/76)"
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
    override_sector: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Extract all deployment-relevant per-ticker metrics from an enriched full_output.
    Returns a dict with Prisma camelCase field names.

    override_sector: when non-empty, used verbatim instead of fullOutput extraction.
    Pass StockResult.sector (or TickerMeta.sector) to get accurate sector grouping
    after the backfill job has run.
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

    # Sector: prefer explicit override (StockResult.sector / TickerMeta.sector)
    # over fullOutput derivation, which is often absent or "Unknown".
    sector = override_sector or (
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

    # Risk-adjusted upside score for cross-universe percentile ranking.
    # edge = prob-weighted upside net of price (signed return space, e.g. 0.15 = 15% upside).
    # stop_frac dampens the score proportionally to stop-hit risk — but stop is also gated
    # separately (Rule 3), so this weighting is an additional quality signal, not a gate.
    vol_adj_ev_score: Optional[float] = None
    if ev_ratio is not None:
        edge = ev_ratio - 1.0  # convert price multiplier → return-space edge
        stop_frac = max(0.0, min(1.0, stop_probability / 100.0))
        vol_adj_ev_score = round(edge * (1.0 - stop_frac), 4)

    return {
        "sector": sector,
        "allocationCurrent": allocation_current,
        "confirmationScore": confirmation_score,
        "evRatio": ev_ratio,
        "volAdjEvScore": vol_adj_ev_score,
        "stopProbability": stop_probability,
        "regimeStable": regime_stable,
    }


def _percentile_mid_rank(
    value: float,
    all_values: List[float],
    *,
    min_universe: int = 5,
    admin_debug: bool = False,
) -> Optional[float]:
    """
    Tie-aware mid-rank percentile of value within all_values.

    Formula: percentile = 100 × (n_lt + 0.5 × n_eq) / n
    where n_lt = count(v < value), n_eq = count(v == value).

    Returns None when fewer than min_universe valid (finite, non-None) values
    are present — caller should disable percentile gating and surface a warning.
    """
    valid = [v for v in all_values if v is not None and math.isfinite(v)]
    n = len(valid)

    if admin_debug:
        if valid:
            sv = sorted(valid)
            mid = n // 2
            median = sv[mid] if n % 2 == 1 else (sv[mid - 1] + sv[mid]) / 2.0
            logger.debug(
                "Percentile rank universe: n_evaluated=%d, n_valid=%d, "
                "min=%.4f, median=%.4f, max=%.4f",
                len(all_values), n, sv[0], median, sv[-1],
            )
        else:
            logger.debug(
                "Percentile rank universe: n_evaluated=%d, n_valid=0", len(all_values)
            )

    if n < min_universe:
        logger.info(
            "Universe too small for percentile ranking (n_valid=%d < min=%d); "
            "disabling percentile gate for this snapshot.",
            n, min_universe,
        )
        return None

    n_lt = sum(1 for v in valid if v < value)
    n_eq = sum(1 for v in valid if v == value)
    return round(100.0 * (n_lt + 0.5 * n_eq) / n, 1)


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
        "Risk-Adjusted Upside Rank",
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


def _suggest_action(
    failing: List[str],
    ev_ratio: Optional[float] = None,
    stop_probability: float = 0.0,
) -> str:
    """
    Map failure context to an explanatory suggested-focus label.

    When vol_adj_ev_percentile fails, decompose whether the binding constraint
    is low upside (edge), elevated stop risk, or both — so the message is
    actionable rather than always showing "Needs cheaper entry."

    Priority: regime → vol_adj_ev (nuanced) → stop_probability → conviction delta.
    """
    if "regime_stable" in failing:
        return "Signal noise-dominated"

    if "vol_adj_ev_percentile" in failing:
        edge = (ev_ratio - 1.0) if ev_ratio is not None else 0.0
        # edge_low: less than 5% prob-weighted upside (insufficient price dislocation)
        edge_low = edge < 0.05
        # stop_elevated: stop is dragging down the score (even if passing Rule 3 gate)
        stop_elevated = stop_probability >= 15.0
        if edge_low and stop_elevated:
            return "Entry + risk need improvement"
        if stop_elevated and not edge_low:
            return "Stop risk elevated"
        return "Needs cheaper entry / more upside"

    if "stop_probability" in failing:
        return "Stop risk elevated"
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

        vol_adj_pct: Optional[float] = (
            _percentile_mid_rank(r.volAdjEvScore, all_vol_adj_scores)
            if r.volAdjEvScore is not None and all_vol_adj_scores
            else None
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

        # Rule 2: vol_adj_ev_percentile — skipped when universe < 5 (vol_adj_pct is None)
        if vol_adj_pct is not None and vol_adj_pct < 60.0:
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
            nfail = len(failing)
            tier = 2 if nfail == 1 else 3 if nfail == 2 else 0
            near_miss_candidates.append({
                "ticker": r.ticker,
                "failing": failing,
                "metric_vals": metric_vals,
                "threshold_vals": threshold_vals,
                "suggested_action": _suggest_action(failing, r.evRatio, r.stopProbability),
                "sort_key": (len(failing), gap_score),
                "tier": tier,
            })

    # Sort: fewest failures first (Tier 2 before Tier 3), then smallest gap to threshold
    near_miss_candidates.sort(key=lambda x: x["sort_key"])

    # Tier counts: Tier 1 = eligible (all rules pass); 2 = fails 1; 3 = fails 2
    tier_counts: Dict[int, int] = {1: eligible_count, 2: 0, 3: 0}
    for c in near_miss_candidates:
        if c["tier"] in (2, 3):
            tier_counts[c["tier"]] += 1

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
            tier=c["tier"],
        )
        for c in near_miss_candidates[:10]
    ]

    return EligibilityDiagnostics(
        evaluated_count=len(cached_rows),
        confirmed_count=confirmed_count,
        eligible_count=eligible_count,
        failure_reasons=failure_reasons,
        near_misses=near_misses,
        tier_counts=tier_counts,
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

        # c-extra) Batch-fetch TickerMeta for sector overrides.
        # Priority: StockResult.sector → TickerMeta.sector → fullOutput extraction.
        universe_ticker_list = list(ticker_to_result.keys())
        try:
            meta_rows = await db.tickermeta.find_many(
                where={"ticker": {"in": universe_ticker_list}},
            )
            ticker_to_meta: Dict[str, Any] = {m.ticker: m for m in meta_rows}
        except Exception as meta_exc:
            logger.warning("Deployment: TickerMeta batch fetch failed: %s", meta_exc)
            ticker_to_meta = {}

        # d) Enrich, extract metrics, compute allocation delta
        raw_metrics: Dict[str, Dict[str, Any]] = {}
        for ticker, result in ticker_to_result.items():
            fo = _parse_full_output(result.fullOutput)
            if not fo:
                continue
            moat_score = float(result.moatScore or 5.0)
            fo = _enrich(fo, moat_score)

            # Resolve sector override: StockResult.sector wins, then TickerMeta
            tm = ticker_to_meta.get(ticker)
            override_sector = (
                getattr(result, "sector", None)
                or (tm.sector if tm and tm.sector else None)
            ) or None
            metrics = _extract_metrics(ticker, fo, moat_score, override_sector=override_sector)

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
            vol_pct = (
                _percentile_mid_rank(m["volAdjEvScore"], all_vol_scores)
                if m["volAdjEvScore"] is not None
                else None
            )
            # None percentile means universe too small to rank — skip that gate
            vol_pct_ok = vol_pct is None or vol_pct >= 60.0
            if (
                m["confirmationScore"] >= 4
                and m["allocationDelta30d"] > 0
                and vol_pct_ok
                and m["stopProbability"] <= 25.0
                and m["regimeStable"]
            ):
                eligible_count += 1

        # Admin debug: universe integrity — duplicate tickers should always be 0
        dup_count = len(ticker_to_result) - len(set(ticker_to_result.keys()))
        n_valid_ev = sum(1 for m in raw_metrics.values() if m["volAdjEvScore"] is not None)
        logger.debug(
            "Deployment universe integrity: n_tickers=%d, n_valid_ev_scores=%d, duplicates=%d",
            len(raw_metrics), n_valid_ev, dup_count,
        )

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

        vol_adj_pct: Optional[float] = (
            _percentile_mid_rank(r.volAdjEvScore, all_vol_adj_scores)
            if r.volAdjEvScore is not None and all_vol_adj_scores
            else None
        )
        # None = universe too small to rank; skip that gate
        vol_pct_ok = vol_adj_pct is None or vol_adj_pct >= 60.0

        if not (
            r.confirmationScore >= 4
            and r.allocationDelta30d > 0
            and vol_pct_ok
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

    # Sector coverage — how many tracked tickers have a known sector (not "Unknown")
    tickers_with_sector = sum(
        1 for r in cached_rows
        if r.sector and r.sector.strip().lower() not in ("", "unknown")
    )
    sector_coverage_pct = round(tickers_with_sector / universe_size * 100.0, 1) if universe_size > 0 else 0.0
    sector_coverage_label = f"Sector coverage: {sector_coverage_pct}% ({tickers_with_sector}/{universe_size})"

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
        "sector_coverage=%s, top_failures=%s",
        user_id,
        universe_size,
        confirmed_count,
        eligible_count,
        sector_coverage_label,
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
        sector_coverage_label=sector_coverage_label,
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
        sector_coverage_label="Sector coverage: 0% (0/0)",
        no_deployable_message="No capital structurally deployable this cycle.",
        eligibility_diagnostics=EligibilityDiagnostics(
            evaluated_count=0,
            confirmed_count=0,
            eligible_count=0,
            failure_reasons=[],
            near_misses=[],
            tier_counts={1: 0, 2: 0, 3: 0},
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

        # EV percentile (stress-test: 0.0 default keeps gate strict when unrankable)
        vol_pct = (
            _percentile_mid_rank(r.volAdjEvScore, all_vol_adj_scores) or 0.0
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
            _percentile_mid_rank(r.volAdjEvScore, all_vol_adj_scores) or 0.0
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


# ── Rolling simulation models ──────────────────────────────────────────────────

class WeeklySimPoint(BaseModel):
    week: str                   # ISO date "YYYY-MM-DD" (Monday of the week)
    deployability_index: float  # 0–100
    structural_confirmed: int   # tickers with confirmation_score >= 4
    tier1_count: int            # strict: conf≥4, delta>0, EV≥60th, stop≤25, stable
    tier2_count: int            # moderate: conf≥4, delta≥0, EV≥55th, stop≤30, stable
    universe_size: int          # tickers with any data this week


class RollingSimSummaryStats(BaseModel):
    pct_weeks_tier1_gte1: float    # % of data-weeks where tier1_count >= 1
    pct_weeks_tier1_zero: float    # % of data-weeks where tier1_count == 0
    median_tier1: float
    median_tier2: float
    total_weeks: int               # total weeks in the 12-month window
    weeks_with_data: int           # weeks that have at least 1 ticker


class EligibilityRollingSimResponse(BaseModel):
    weeks: List[WeeklySimPoint]
    summary_stats: RollingSimSummaryStats
    tier1_label: str
    tier2_label: str
    generated_at: str
    data_start: Optional[str]      # earliest week date with universe data
    data_end: Optional[str]        # latest week date with universe data


# ── Rolling simulation constants & cache ──────────────────────────────────────

_ROLLING_SIM_LABEL_T1 = "Strict (conf ≥ 4, delta > 0, EV ≥ 60th, stop ≤ 25%, stable)"
_ROLLING_SIM_LABEL_T2 = "Moderate (conf ≥ 4, delta ≥ 0, EV ≥ 55th, stop ≤ 30%, stable)"

_rolling_sim_cache: Dict[str, Tuple[str, EligibilityRollingSimResponse]] = {}


# ── Rolling simulation helper ──────────────────────────────────────────────────

def _empty_rolling_sim(now_utc: datetime) -> EligibilityRollingSimResponse:
    """Return an empty rolling sim response (no historical data)."""
    today = now_utc.date()
    this_monday = today - timedelta(days=today.weekday())
    weeks = [
        WeeklySimPoint(
            week=(this_monday - timedelta(weeks=w)).isoformat(),
            deployability_index=0.0,
            structural_confirmed=0,
            tier1_count=0,
            tier2_count=0,
            universe_size=0,
        )
        for w in range(51, -1, -1)
    ]
    return EligibilityRollingSimResponse(
        weeks=weeks,
        summary_stats=RollingSimSummaryStats(
            pct_weeks_tier1_gte1=0.0,
            pct_weeks_tier1_zero=100.0,
            median_tier1=0.0,
            median_tier2=0.0,
            total_weeks=52,
            weeks_with_data=0,
        ),
        tier1_label=_ROLLING_SIM_LABEL_T1,
        tier2_label=_ROLLING_SIM_LABEL_T2,
        generated_at=now_utc.isoformat(),
        data_start=None,
        data_end=None,
    )


async def _run_rolling_simulation(db) -> EligibilityRollingSimResponse:
    """
    Rolling 12-month weekly eligibility simulation.

    Uses historical StockResult.fullOutput — no recalculation, no LLM calls.
    Computes Tier 1 (strict) and Tier 2 (moderate) eligibility counts per ISO week.

    Tier 1 = conf≥4, delta>0, EV≥60th pct, stop≤25%, regime stable
    Tier 2 = conf≥4, delta≥0, EV≥55th pct, stop≤30%, regime stable
    """
    import statistics as _statistics

    now_utc = datetime.now(timezone.utc)

    # ── 1. Fetch all completed results from last ~14 months ───────────────────
    # Extra 2-month buffer so prior-run delta lookups can reach back 30 days
    # from the oldest week in our 12-month window.
    cutoff = now_utc - timedelta(days=430)
    all_results = await db.stockresult.find_many(
        where={"status": "completed", "createdAt": {"gte": cutoff}},
        order={"createdAt": "asc"},
    )
    if not all_results:
        return _empty_rolling_sim(now_utc)

    # ── 2. Pre-compute enriched output + base metrics per run_id ─────────────
    # Cache to avoid redundant DI enrichment when the same result appears in
    # multiple weeks (e.g. a ticker analysed once stays the "latest" for many
    # consecutive weeks).
    enriched_cache: Dict[str, Dict[str, Any]] = {}
    base_metrics_cache: Dict[str, Dict[str, Any]] = {}

    for r in all_results:
        fo = _parse_full_output(r.fullOutput)
        if not fo:
            continue
        moat_score = float(r.moatScore or 5.0)
        fo = _enrich(fo, moat_score)
        enriched_cache[r.runId] = fo
        base_metrics_cache[r.runId] = _extract_metrics(r.ticker, fo, moat_score)

    # ── 3. Group by ticker: sorted list of (ts, run_id) ──────────────────────
    ticker_history: Dict[str, List[Tuple[datetime, str]]] = {}
    for r in all_results:
        if r.runId not in enriched_cache:
            continue  # fullOutput was unparseable
        ts = r.createdAt
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        ticker_history.setdefault(r.ticker, []).append((ts, r.runId))
    # Already in ascending order because we queried ORDER BY createdAt ASC

    def _latest_run_id_before(
        history: List[Tuple[datetime, str]], cutoff_dt: datetime
    ) -> Optional[str]:
        """Return run_id of the latest entry with ts ≤ cutoff_dt, or None."""
        result = None
        for ts, run_id in history:
            if ts <= cutoff_dt:
                result = run_id
            else:
                break
        return result

    def _get_conviction_pct(run_id: str) -> Optional[float]:
        fo = enriched_cache.get(run_id)
        if fo is None:
            return None
        return (
            (fo.get("decision_intelligence") or {})
            .get("conviction_position", {})
            .get("recommended_pct")
        )

    # ── 4. Build ISO week windows (52 weeks, Monday to Sunday) ───────────────
    today = now_utc.date()
    this_monday = today - timedelta(days=today.weekday())
    week_mondays = [
        this_monday - timedelta(weeks=w)
        for w in range(51, -1, -1)
    ]  # oldest first → newest last

    result_points: List[WeeklySimPoint] = []

    for week_monday in week_mondays:
        # Inclusive window: [week_monday 00:00Z, week_monday+6 23:59:59Z]
        week_end = datetime(
            week_monday.year, week_monday.month, week_monday.day,
            23, 59, 59, tzinfo=timezone.utc,
        ) + timedelta(days=6)
        prior_cutoff = week_end - timedelta(days=30)

        # Per-ticker: snapshot of latest result as of this week's end
        weekly_metrics: List[Dict[str, Any]] = []
        for ticker, history in ticker_history.items():
            curr_run_id = _latest_run_id_before(history, week_end)
            if curr_run_id is None:
                continue

            m = dict(base_metrics_cache[curr_run_id])  # copy

            # Allocation delta: prior run ≤ (week_end - 30d)
            prior_run_id = _latest_run_id_before(history, prior_cutoff)
            allocation_delta: Optional[float] = None
            if prior_run_id and prior_run_id != curr_run_id:
                prior_pct = _get_conviction_pct(prior_run_id)
                if prior_pct is not None:
                    allocation_delta = round(m["allocationCurrent"] - float(prior_pct), 2)

            m["allocationDelta30d"] = allocation_delta
            weekly_metrics.append(m)

        universe_size = len(weekly_metrics)
        if universe_size == 0:
            result_points.append(WeeklySimPoint(
                week=week_monday.isoformat(),
                deployability_index=0.0,
                structural_confirmed=0,
                tier1_count=0,
                tier2_count=0,
                universe_size=0,
            ))
            continue

        # Cross-universe vol-adj EV scores for percentile ranking this week
        all_vol_scores = [
            m["volAdjEvScore"]
            for m in weekly_metrics
            if m.get("volAdjEvScore") is not None
        ]

        structural_confirmed = sum(
            1 for m in weekly_metrics if m["confirmationScore"] >= 4
        )
        tier1_count = 0
        tier2_count = 0

        for m in weekly_metrics:
            if m["confirmationScore"] < 4:
                continue
            if not m.get("regimeStable", False):
                continue

            vol_pct = (
                _percentile_mid_rank(m["volAdjEvScore"], all_vol_scores) or 0.0
                if m.get("volAdjEvScore") is not None and all_vol_scores
                else 0.0
            )
            delta = m.get("allocationDelta30d")
            stop = m.get("stopProbability", 100.0)

            # Tier 1 — strict baseline
            if (
                delta is not None and delta > 0
                and vol_pct >= 60.0
                and stop <= 25.0
            ):
                tier1_count += 1

            # Tier 2 — moderate (Scenario D equivalent)
            if (
                delta is not None and delta >= 0
                and vol_pct >= 55.0
                and stop <= 30.0
            ):
                tier2_count += 1

        # Deployability index (same formula as _compute_deployability_index)
        pct_confirmed_di = structural_confirmed / universe_size * 100.0
        regime_stable_cnt = sum(1 for m in weekly_metrics if m.get("regimeStable", False))
        regime_stable_pct_di = regime_stable_cnt / universe_size * 100.0
        avg_stop_di = sum(m.get("stopProbability", 50.0) for m in weekly_metrics) / universe_size

        sector_di: Dict[str, Dict[str, int]] = {}
        for m in weekly_metrics:
            sec = m.get("sector") or "Unknown"
            if sec not in sector_di:
                sector_di[sec] = {"confirmed": 0, "total": 0}
            sector_di[sec]["total"] += 1
            if m["confirmationScore"] >= 4:
                sector_di[sec]["confirmed"] += 1
        breadth_pcts = [
            s["confirmed"] / s["total"] * 100.0
            for s in sector_di.values() if s["total"] > 0
        ]
        avg_breadth_di = sum(breadth_pcts) / len(breadth_pcts) if breadth_pcts else 0.0

        di_score = round(
            pct_confirmed_di * 0.35
            + regime_stable_pct_di * 0.30
            + (100.0 - avg_stop_di) * 0.20
            + avg_breadth_di * 0.15,
            1,
        )

        result_points.append(WeeklySimPoint(
            week=week_monday.isoformat(),
            deployability_index=di_score,
            structural_confirmed=structural_confirmed,
            tier1_count=tier1_count,
            tier2_count=tier2_count,
            universe_size=universe_size,
        ))

    # ── 5. Summary statistics ─────────────────────────────────────────────────
    data_weeks = [p for p in result_points if p.universe_size > 0]
    total_weeks = len(result_points)
    weeks_with_data = len(data_weeks)

    if data_weeks:
        t1_vals = [p.tier1_count for p in data_weeks]
        t2_vals = [p.tier2_count for p in data_weeks]
        pct_t1_gte1 = round(sum(1 for v in t1_vals if v >= 1) / weeks_with_data * 100.0, 1)
        pct_t1_zero = round(sum(1 for v in t1_vals if v == 0) / weeks_with_data * 100.0, 1)
        median_t1 = float(_statistics.median(t1_vals))
        median_t2 = float(_statistics.median(t2_vals))
        data_start = data_weeks[0].week
        data_end = data_weeks[-1].week
    else:
        pct_t1_gte1 = 0.0
        pct_t1_zero = 100.0
        median_t1 = 0.0
        median_t2 = 0.0
        data_start = None
        data_end = None

    logger.info(
        "Rolling sim complete — %d weeks, %d with data, "
        "pct_t1_gte1=%.1f%%, median_t1=%.1f, median_t2=%.1f",
        total_weeks, weeks_with_data, pct_t1_gte1, median_t1, median_t2,
    )

    return EligibilityRollingSimResponse(
        weeks=result_points,
        summary_stats=RollingSimSummaryStats(
            pct_weeks_tier1_gte1=pct_t1_gte1,
            pct_weeks_tier1_zero=pct_t1_zero,
            median_tier1=median_t1,
            median_tier2=median_t2,
            total_weeks=total_weeks,
            weeks_with_data=weeks_with_data,
        ),
        tier1_label=_ROLLING_SIM_LABEL_T1,
        tier2_label=_ROLLING_SIM_LABEL_T2,
        generated_at=now_utc.isoformat(),
        data_start=data_start,
        data_end=data_end,
    )


# ── Rolling simulation route (admin-only) ─────────────────────────────────────

@router.get("/deployment/eligibility-rolling-sim/admin", response_model=EligibilityRollingSimResponse)
async def get_admin_eligibility_rolling_sim(
    admin: User = Depends(require_admin),
):
    """
    Rolling 12-month weekly eligibility tier simulation — Admin Only.

    Reads historical StockResult.fullOutput snapshots. No new analyses, no LLM calls.
    Returns a WeeklySimPoint for every ISO week in the trailing 52-week window with:
      - deployability_index  (same 4-component formula as the live dashboard)
      - structural_confirmed (tickers with confirmation_score >= 4)
      - tier1_count          (strict baseline: all 5 eligibility rules)
      - tier2_count          (moderate: Scenario-D equivalent relaxation)

    Results are cached in-process per snapshot bucket (24h) to avoid re-scanning
    the full 14-month StockResult history on every request.
    """
    db = await get_db()
    try:
        now_utc = datetime.now(timezone.utc)
        current_bucket = _snapshot_bucket(now_utc)
        bucket_str = current_bucket.isoformat()

        cached = _rolling_sim_cache.get(_ADMIN_SENTINEL)
        if cached and cached[0] == bucket_str:
            logger.debug("Rolling sim cache hit for bucket %s", bucket_str)
            return cached[1]

        result = await _run_rolling_simulation(db)
        _rolling_sim_cache[_ADMIN_SENTINEL] = (bucket_str, result)
        return result

    except _TableNotFoundError as exc:
        logger.error("deployment/rolling-sim: table missing — %s", exc)
        raise HTTPException(
            status_code=503,
            detail={
                "error": "deployment_cache_not_migrated",
                "message": "Run: prisma migrate deploy --schema=db/schema.prisma",
            },
        )
    except Exception as exc:
        logger.exception("Rolling sim failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to run rolling eligibility simulation.")
