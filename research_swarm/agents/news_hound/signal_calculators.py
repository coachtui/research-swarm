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


# ── Earnings estimates (Phase B3) ───────────────────────────────────────────


def _rows_by_period(estimates_data: Any) -> Dict[str, Dict[str, Any]]:
    """yfinance earnings_estimate rows keyed by period (0q/+1q/0y/+1y).
    Handles both the live shape (period as index) and the cache round-trip
    shape (period as a column after reset_index)."""
    rows: Dict[str, Dict[str, Any]] = {}
    if estimates_data is None:
        return rows
    try:
        if isinstance(estimates_data, pd.DataFrame):
            if estimates_data.empty:
                return rows
            df = estimates_data
            if "period" in df.columns:
                for rec in df.to_dict(orient="records"):
                    rows[str(rec.get("period"))] = rec
            elif "index" in df.columns:
                for rec in df.to_dict(orient="records"):
                    rows[str(rec.get("index"))] = rec
            else:
                for idx, rec in zip(df.index, df.to_dict(orient="records")):
                    rows[str(idx)] = rec
    except Exception as e:
        logger.warning(f"Could not read earnings estimates: {e}")
    return rows


def _clean_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        f = float(value)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def calculate_earnings_estimates(
    estimates_data: Any,
    earnings_history: Any,
) -> Dict[str, Any]:
    """EPS estimates, growth, dispersion, and surprise history — all direct
    reads/arithmetic over yfinance data. The old Sonnet call was handed the
    same DataFrames as text and asked to copy numbers into JSON; it was never
    given the earnings history at all, so the surprise fields it reported had
    no basis. Revision counts/direction/momentum are filled by the caller
    from calculate_revision_metrics (unchanged).
    """
    rows = _rows_by_period(estimates_data)
    q0 = rows.get("0q") or {}
    y0 = rows.get("0y") or {}
    y1 = rows.get("+1y") or {}

    current_quarter_eps = _clean_float(q0.get("avg"))
    current_fy_eps = _clean_float(y0.get("avg"))
    next_fy_eps = _clean_float(y1.get("avg"))

    def _growth_pct(row: Dict[str, Any]) -> Optional[float]:
        g = _clean_float(row.get("growth"))
        return round(g * 100, 2) if g is not None else None

    current_year_growth = _growth_pct(y0)
    next_year_growth = _growth_pct(y1)

    # Two-year CAGR: year-ago FY EPS → next-FY estimate
    two_year_cagr = None
    year_ago_fy = _clean_float(y0.get("yearAgoEps"))
    if year_ago_fy and next_fy_eps and year_ago_fy > 0 and next_fy_eps > 0:
        two_year_cagr = round(((next_fy_eps / year_ago_fy) ** 0.5 - 1) * 100, 2)

    analyst_coverage = None
    coverage_raw = _clean_float(q0.get("numberOfAnalysts") or y0.get("numberOfAnalysts"))
    if coverage_raw is not None:
        analyst_coverage = int(coverage_raw)

    # Dispersion: (high - low) relative to the mean estimate
    dispersion = "medium"
    agreement = 0.5
    low, high = _clean_float(q0.get("low")), _clean_float(q0.get("high"))
    if low is not None and high is not None and current_quarter_eps:
        spread = abs(high - low) / abs(current_quarter_eps)
        if spread < 0.10:
            dispersion, agreement = "low", 0.85
        elif spread < 0.25:
            dispersion, agreement = "medium", 0.6
        else:
            dispersion, agreement = "high", 0.35

    # Surprise history from actual earnings results (most recent first)
    surprises: List[Optional[float]] = []
    hist_rows: List[Dict[str, Any]] = []
    try:
        if isinstance(earnings_history, pd.DataFrame) and not earnings_history.empty:
            hist_rows = earnings_history.to_dict(orient="records")
    except Exception as e:
        logger.warning(f"Could not read earnings history: {e}")
    for rec in reversed(hist_rows[-4:]):  # newest first
        actual = _clean_float(rec.get("epsActual"))
        estimate = _clean_float(rec.get("epsEstimate"))
        if actual is not None and estimate not in (None, 0):
            surprises.append(round((actual - estimate) / abs(estimate) * 100, 2))
        else:
            surprises.append(None)

    known_surprises = [s for s in surprises if s is not None]
    beats = sum(1 for s in known_surprises if s > 0)
    beat_pattern = f"Beat {beats}/{len(known_surprises)}" if known_surprises else ""
    avg_surprise = round(sum(known_surprises) / len(known_surprises), 2) if known_surprises else None

    padded = (surprises + [None] * 4)[:4]

    return {
        "current_quarter_eps": current_quarter_eps,
        "current_fy_eps": current_fy_eps,
        "next_fy_eps": next_fy_eps,
        # Filled by the caller from calculate_revision_metrics:
        "upward_revisions": 0,
        "downward_revisions": 0,
        "net_revision_direction": "neutral",
        "momentum": "stable",
        "consensus_change_pct": None,  # needs historical consensus — not in the data
        "analyst_coverage": analyst_coverage or 0,
        "estimate_dispersion": dispersion,
        "estimate_agreement": agreement,
        "q1_surprise_pct": padded[0],
        "q2_surprise_pct": padded[1],
        "q3_surprise_pct": padded[2],
        "q4_surprise_pct": padded[3],
        "avg_surprise_pct": avg_surprise,
        "beat_pattern": beat_pattern,
        "current_year_growth_pct": current_year_growth,
        "next_year_growth_pct": next_year_growth,
        "two_year_cagr": two_year_cagr,
    }


# ── Upcoming catalysts (Phase B3) ───────────────────────────────────────────


def calculate_upcoming_catalysts(
    earnings_dates: Any,
    catalyst_events: List[Dict[str, Any]],
    analysis_date: str,
) -> Dict[str, Any]:
    """Forward catalyst calendar assembled from the earnings-dates calendar
    plus future-dated news catalysts — deterministic date filtering and
    counting that a Haiku call previously performed."""
    from datetime import date, datetime

    try:
        today = datetime.strptime(analysis_date, "%Y-%m-%d").date() if analysis_date else date.today()
    except ValueError:
        today = date.today()

    # ── Next earnings date: earliest future date in the calendar ───────────
    next_earnings: Optional[date] = None
    candidate_values: List[Any] = []
    if earnings_dates is not None:
        try:
            if isinstance(earnings_dates, pd.DataFrame) and not earnings_dates.empty:
                candidate_values.extend(list(earnings_dates.index))
                for col in earnings_dates.columns:
                    if "date" in str(col).lower():
                        candidate_values.extend(list(earnings_dates[col]))
        except Exception as e:
            logger.warning(f"Could not read earnings dates: {e}")
    for value in candidate_values:
        try:
            parsed = pd.to_datetime(value, errors="coerce")
            if parsed is None or pd.isna(parsed):
                continue
            parsed_date = parsed.date()
            if parsed_date >= today and (next_earnings is None or parsed_date < next_earnings):
                next_earnings = parsed_date
        except Exception:
            continue

    catalysts: List[Dict[str, Any]] = []
    if next_earnings is not None:
        catalysts.append({
            "event_type": "earnings",
            "event_date": next_earnings.isoformat(),
            "description": f"Next earnings announcement scheduled for {next_earnings.isoformat()}",
            "potential_impact": "high",
            "impact_direction": "neutral",
            "confidence": 0.9,
        })

    # ── Future-dated news catalysts ────────────────────────────────────────
    directions: List[str] = []
    for event in catalyst_events or []:
        event_date = event.get("date")
        if not event_date:
            continue
        try:
            parsed_date = datetime.strptime(str(event_date)[:10], "%Y-%m-%d").date()
        except ValueError:
            continue
        if parsed_date < today:
            continue
        impact = str(event.get("impact", "neutral")).lower()
        directions.append(impact)
        confidence = event.get("confidence")
        catalysts.append({
            "event_type": str(event.get("event_type", "other")),
            "event_date": parsed_date.isoformat(),
            "description": event.get("description", "Upcoming catalyst"),
            "potential_impact": "high" if (confidence or 0) >= 0.8 else "medium",
            "impact_direction": impact,
            "confidence": confidence if confidence is not None else 0.5,
        })

    density = "high" if len(catalysts) >= 4 else ("medium" if len(catalysts) >= 2 else "low")
    positives = sum(1 for d in directions if d == "positive")
    negatives = sum(1 for d in directions if d == "negative")
    if positives > negatives:
        outlook = "positive"
    elif negatives > positives:
        outlook = "negative"
    else:
        outlook = "neutral"

    return {
        "next_earnings_date": next_earnings.isoformat() if next_earnings else None,
        "earnings_confirmed": next_earnings is not None,
        "catalysts": catalysts,
        "catalyst_density": density,
        "outlook": outlook,
    }
