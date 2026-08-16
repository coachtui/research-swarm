"""Deterministic signal calculators for the News Hound agent.

These four signals (short interest, analyst consensus, institutional activity,
dark pool) were previously computed by Haiku calls whose prompts asked the
model to copy pre-formatted numbers into JSON and apply hardcoded threshold
tables — pure arithmetic dressed up as analysis, at LLM cost and latency, with
hallucination risk on fields the inputs couldn't support.

Each function returns the same dict shape the LLM produced, so the Pydantic
models (ShortInterest, AnalystConsensus, InstitutionalActivity,
DarkPoolActivity) and every downstream consumer are unchanged.
"""

import math
from typing import Any, Dict, List, Optional

import pandas as pd

from research_swarm.logger import logger


# ── Short interest ──────────────────────────────────────────────────────────


def calculate_short_interest(short_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Short metrics, trend, and squeeze risk from yfinance short data.

    Thresholds are the ones the old prompt instructed the LLM to apply:
    High = >20% short AND >5 days to cover; Medium = 10-20% OR 3-5 dtc.
    """
    if not short_data:
        return {
            "short_interest_pct": None,
            "short_interest_shares": None,
            "days_to_cover": None,
            "short_interest_trend": "stable",
            "mom_change_pct": None,
            "squeeze_risk": "low",
            "squeeze_triggers": [],
            "notable_short_activity": [],
            "short_sentiment": "neutral",
        }

    raw_pct = short_data.get("short_percent_float")
    short_pct = round(raw_pct * 100, 2) if raw_pct is not None else None
    shares_short = short_data.get("shares_short")
    prior_shares = short_data.get("shares_short_prior_month")
    days_to_cover = short_data.get("short_ratio")

    # Month-over-month trend
    mom_change_pct = None
    trend = "stable"
    sentiment = "neutral"
    if shares_short and prior_shares:
        mom_change_pct = round((shares_short - prior_shares) / prior_shares * 100, 2)
        if mom_change_pct > 5.0:
            trend, sentiment = "increasing", "bearish"
        elif mom_change_pct < -5.0:
            trend, sentiment = "decreasing", "bullish"

    # Squeeze risk
    squeeze_risk = "low"
    triggers: List[str] = []
    if short_pct is not None and days_to_cover is not None:
        if short_pct > 20 and days_to_cover > 5:
            squeeze_risk = "high"
        elif 10 <= short_pct <= 20 or 3 <= days_to_cover <= 5:
            squeeze_risk = "medium"
    elif short_pct is not None and short_pct > 20:
        squeeze_risk = "medium"

    if short_pct is not None and short_pct > 15:
        triggers.append(f"Elevated short interest ({short_pct:.1f}% of float)")
    if days_to_cover is not None and days_to_cover > 5:
        triggers.append(f"High days-to-cover ({days_to_cover:.1f} days)")
    if trend == "increasing":
        triggers.append(f"Short interest rising ({mom_change_pct:+.1f}% MoM)")

    return {
        "short_interest_pct": short_pct,
        "short_interest_shares": int(shares_short) if shares_short else None,
        "days_to_cover": days_to_cover,
        "short_interest_trend": trend,
        "mom_change_pct": mom_change_pct,
        "squeeze_risk": squeeze_risk,
        "squeeze_triggers": triggers,
        "notable_short_activity": [],
        "short_sentiment": sentiment,
    }


# ── Analyst consensus ───────────────────────────────────────────────────────

_RECOMMENDATION_KEY_LABELS = {
    "strong_buy": "Strong Buy",
    "buy": "Buy",
    "hold": "Hold",
    "underperform": "Sell",
    "sell": "Sell",
    "strong_sell": "Strong Sell",
}


def _rating_counts_from_row(row: Dict[str, Any]) -> Dict[str, int]:
    def _int(key_variants):
        for key in key_variants:
            val = row.get(key)
            if val is not None and not (isinstance(val, float) and math.isnan(val)):
                try:
                    return int(val)
                except (TypeError, ValueError):
                    continue
        return 0

    return {
        "strong_buy": _int(["strongBuy", "strong_buy"]),
        "buy": _int(["buy"]),
        "hold": _int(["hold"]),
        "sell": _int(["sell"]),
        "strong_sell": _int(["strongSell", "strong_sell"]),
    }


def _weighted_rating_score(counts: Dict[str, int]) -> Optional[float]:
    """1 (strong sell) .. 5 (strong buy), analyst-count-weighted."""
    weights = {"strong_buy": 5, "buy": 4, "hold": 3, "sell": 2, "strong_sell": 1}
    total = sum(counts.values())
    if total == 0:
        return None
    return sum(counts[k] * w for k, w in weights.items()) / total


def calculate_analyst_consensus(
    recommendations_data: Optional[pd.DataFrame],
    price_targets: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Consensus rating distribution, price targets, and rating momentum.

    Rating momentum is derived by comparing the current month's weighted
    rating score against the oldest month in the recommendations history —
    something the old prompt asked for but the LLM had no basis to compute.
    Upgrades/downgrades/new-coverage counts are not derivable from these
    inputs, so they are reported as 0 rather than hallucinated.
    """
    counts = {"strong_buy": 0, "buy": 0, "hold": 0, "sell": 0, "strong_sell": 0}
    rating_momentum = "stable"

    rows: List[Dict[str, Any]] = []
    if recommendations_data is not None:
        try:
            if isinstance(recommendations_data, pd.DataFrame) and not recommendations_data.empty:
                rows = recommendations_data.to_dict(orient="records")
            elif isinstance(recommendations_data, list):
                rows = recommendations_data
        except Exception as e:
            logger.warning(f"Could not read recommendations data: {e}")

    if rows:
        # yfinance orders periods 0m (current) → -3m (oldest)
        counts = _rating_counts_from_row(rows[0])
        current_score = _weighted_rating_score(counts)
        oldest_score = _weighted_rating_score(_rating_counts_from_row(rows[-1])) if len(rows) > 1 else None
        if current_score is not None and oldest_score is not None:
            delta = current_score - oldest_score
            if delta > 0.15:
                rating_momentum = "improving"
            elif delta < -0.15:
                rating_momentum = "deteriorating"

    # Consensus label: prefer yfinance's own recommendationKey, else the
    # weighted score over the ratings distribution.
    consensus_rating = "Hold"
    rec_key = (price_targets or {}).get("recommendation")
    if rec_key and rec_key in _RECOMMENDATION_KEY_LABELS:
        consensus_rating = _RECOMMENDATION_KEY_LABELS[rec_key]
    else:
        score = _weighted_rating_score(counts)
        if score is not None:
            if score >= 4.5:
                consensus_rating = "Strong Buy"
            elif score >= 3.5:
                consensus_rating = "Buy"
            elif score >= 2.5:
                consensus_rating = "Hold"
            elif score >= 1.5:
                consensus_rating = "Sell"
            else:
                consensus_rating = "Strong Sell"

    pt = price_targets or {}
    avg_target = pt.get("target_mean")
    current_price = pt.get("current_price")
    target_upside_pct = None
    if avg_target and current_price:
        target_upside_pct = round((avg_target - current_price) / current_price * 100, 2)

    num_analysts = pt.get("num_analysts") or sum(counts.values())
    if num_analysts >= 20:
        confidence = "high"
    elif num_analysts >= 8:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        **counts,
        "consensus_rating": consensus_rating,
        "avg_price_target": avg_target,
        "high_price_target": pt.get("target_high"),
        "low_price_target": pt.get("target_low"),
        "target_upside_pct": target_upside_pct,
        "upgrades": 0,
        "downgrades": 0,
        "new_coverage": 0,
        "rating_momentum": rating_momentum,
        "target_trend": "stable",
        "consensus_confidence": confidence,
    }


# ── Institutional activity ──────────────────────────────────────────────────


def calculate_institutional_activity(
    institutional_data: Optional[pd.DataFrame],
) -> Dict[str, Any]:
    """Top-holder summary and accumulation/distribution trend from 13F data.

    yfinance provides only the top holders, so ownership figures reflect that
    subset; unknown values are reported as None rather than guessed.
    """
    rows: List[Dict[str, Any]] = []
    if institutional_data is not None:
        try:
            if isinstance(institutional_data, pd.DataFrame) and not institutional_data.empty:
                rows = institutional_data.to_dict(orient="records")
            elif isinstance(institutional_data, list):
                rows = institutional_data
        except Exception as e:
            logger.warning(f"Could not read institutional data: {e}")

    top_holders: List[Dict[str, Any]] = []
    changes: List[float] = []
    notable: List[str] = []

    for row in rows[:10]:
        name = row.get("Holder") or row.get("holder")
        if not name:
            continue
        pct_held = row.get("pctHeld") or row.get("pct_held")
        pct_change = row.get("pctChange") or row.get("pct_change")

        change_str = "Held"
        if pct_change is not None and not (isinstance(pct_change, float) and math.isnan(pct_change)):
            change_pct = pct_change * 100
            changes.append(change_pct)
            if change_pct > 0.5:
                change_str = f"Added {change_pct:.1f}%"
            elif change_pct < -0.5:
                change_str = f"Reduced {abs(change_pct):.1f}%"
            if abs(change_pct) >= 10:
                verb = "increased" if change_pct > 0 else "reduced"
                notable.append(f"{name} {verb} position by {abs(change_pct):.0f}%")

        top_holders.append({
            "name": name,
            "ownership_pct": round(pct_held * 100, 2) if pct_held is not None else None,
            "change": change_str,
        })

    trend = "stable"
    sentiment = "neutral"
    if changes:
        avg_change = sum(changes) / len(changes)
        if avg_change > 2.0:
            trend, sentiment = "accumulation", "bullish"
        elif avg_change < -2.0:
            trend, sentiment = "distribution", "bearish"

    return {
        "institutional_ownership_pct": None,  # not derivable from top-holders list
        "qoq_change_pct": None,
        "num_holders": len(top_holders),
        "trend": trend,
        "top_holders": top_holders[:5],
        "notable_activity": notable,
        "institutional_sentiment": sentiment,
    }


# ── Dark pool activity ──────────────────────────────────────────────────────


def calculate_dark_pool_activity(
    dark_pool_data: Optional[List[Dict[str, Any]]],
) -> Dict[str, Any]:
    """ATS volume trend, baseline z-score, and venue concentration from FINRA
    weekly records. The stock-specific baseline math was already deterministic
    pre-LLM; this just completes the job and drops the model call.
    """
    result: Dict[str, Any] = {
        "avg_ats_pct": None,
        "trend": "stable",
        "trend_pct_change": None,
        "peak_week": None,
        "peak_ats_pct": None,
        "major_venues": [],
        "venue_concentration": "medium",
        "notable_patterns": [],
        "dark_pool_sentiment": "neutral",
        "confidence": "low",
        "baseline_avg_ats_pct": None,
        "baseline_std_ats_pct": None,
        "z_score": None,
    }
    if not dark_pool_data:
        return result

    weeks = [w for w in dark_pool_data if w.get("ats_pct") is not None]
    if not weeks:
        return result

    ats_pcts = [w["ats_pct"] for w in weeks]
    recent_window = ats_pcts[-4:]
    recent_avg = sum(recent_window) / len(recent_window)
    result["avg_ats_pct"] = round(recent_avg, 2)

    peak = max(weeks, key=lambda w: w["ats_pct"])
    result["peak_week"] = peak.get("week_ending")
    result["peak_ats_pct"] = round(peak["ats_pct"], 2)

    # Baseline stats (>= 5 weeks: recent = last 4, baseline = the rest)
    if len(ats_pcts) >= 5:
        baseline_window = ats_pcts[:-4]
        b_avg = sum(baseline_window) / len(baseline_window)
        variance = sum((x - b_avg) ** 2 for x in baseline_window) / len(baseline_window)
        b_std = math.sqrt(variance) if variance > 0 else 1.0
        z_score = round((recent_avg - b_avg) / b_std, 2) if b_std > 0 else 0.0
        result["baseline_avg_ats_pct"] = round(b_avg, 2)
        result["baseline_std_ats_pct"] = round(b_std, 2)
        result["z_score"] = z_score

        if b_avg > 0:
            result["trend_pct_change"] = round((recent_avg - b_avg) / b_avg * 100, 2)
        if z_score >= 1.0:
            result["trend"] = "increasing"
        elif z_score <= -1.0:
            result["trend"] = "decreasing"
        if abs(z_score) >= 2.0:
            direction = "above" if z_score > 0 else "below"
            result["notable_patterns"].append(
                f"4-week avg ATS ({recent_avg:.1f}%) is {abs(recent_avg - b_avg):.1f}pp "
                f"{direction} this stock's baseline ({b_avg:.1f}%), z={z_score:+.2f}"
            )

    # Venue aggregation across weeks
    venue_counts: Dict[str, int] = {}
    for w in weeks:
        for venue in (w.get("venues") or [])[:3]:
            venue_counts[venue] = venue_counts.get(venue, 0) + 1
    ranked = sorted(venue_counts, key=venue_counts.get, reverse=True)
    result["major_venues"] = ranked[:3]
    if len(ranked) <= 3:
        result["venue_concentration"] = "high"
    elif len(ranked) <= 6:
        result["venue_concentration"] = "medium"
    else:
        result["venue_concentration"] = "low"

    # ATS % alone carries no directional signal — report neutral rather than
    # guessing, and let signal_divergence combine it with 13F direction.
    if len(weeks) >= 10:
        result["confidence"] = "high"
    elif len(weeks) >= 5:
        result["confidence"] = "medium"

    return result
