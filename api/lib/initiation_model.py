"""
DVRG Initiation Model — informational risk-framing score only.

CANONICAL DECISION AUTHORITY: CompounderEngine (compounder_owner_v3.py)
This model is used ONLY for the Conservative Valuation Lens section.
It does NOT gate initiations or tier adds — those are governed by
CompounderScore, drawdown state, and portfolio slot.

Score formula:
  EV% × 3.0  +  QualityScore × 4.0  −  DownsideRiskFactor × 3.0  −  VolatilityPenalty × 2.0

Note: valuation discount factor (VDF) removed — price position relative to
intrinsic value must NOT influence the initiation score.
"""

from typing import Any, Dict, Optional


# ── Normalization bounds ────────────────────────────────────────────────────────
#
# Derived from realistic input ranges (VDF removed):
#   EV_percent ∈ [-30, +40]       → EV × 3   : [-90, +120]
#   Quality_score ∈ [0, 10]       → Q  × 4   : [  0,  +40]
#   Downside_risk_factor × 3 (sub):            [  0,  -30]
#   Volatility_penalty × 2 (sub)  :            [  0,  -20]
# ─────────────────────────────────────────────────────────────────────────────
#   RAW_MIN = -90 + 0 - 30 - 20  = -140
#   RAW_MAX = +120 + 40 - 0 - 0  = +160

_RAW_MIN = -140.0
_RAW_MAX = 160.0


# ── Factor helpers ──────────────────────────────────────────────────────────────

def _valuation_discount_factor(
    price: float,
    fair_value_low: float,
    fair_value_high: float,
) -> int:
    """
    +10  price is below the lower intrinsic-value band  (significant discount)
    +5   price is within the intrinsic-value band       (fair zone)
    -10  price is above the upper intrinsic-value band  (premium)
    """
    if price < fair_value_low:
        return 10
    elif price <= fair_value_high:
        return 5
    else:
        return -10


def _downside_risk_factor(downside_percent: float) -> int:
    """
    downside_percent is the bear-case return in % (expected to be ≤ 0 for losses).

    0   downside is mild  (> -15%)
    5   moderate downside (-15% to -25%)
    10  severe downside   (< -25%)
    """
    if downside_percent > -15.0:
        return 0
    elif downside_percent >= -25.0:
        return 5
    else:
        return 10


def _volatility_penalty(beta: float) -> int:
    """
    0   low volatility   (beta < 1.2)
    5   elevated         (1.2 – 1.5)
    10  high             (> 1.5)
    """
    if beta < 1.2:
        return 0
    elif beta <= 1.5:
        return 5
    else:
        return 10


def _normalize(raw: float) -> float:
    """Clamp-normalise raw composite to [0, 100]."""
    span = _RAW_MAX - _RAW_MIN          # 340
    normalized = (raw - _RAW_MIN) / span * 100.0
    return max(0.0, min(100.0, normalized))


def _status_from_score(score: float) -> str:
    if score >= 65.0:
        return "INITIATE"
    elif score >= 50.0:
        return "WATCHLIST"
    else:
        return "WAIT"


# ── EV computation ──────────────────────────────────────────────────────────────

def _compute_ev_percent(price: float, price_targets: Dict[str, Any]) -> float:
    """
    Probability-weighted expected return (%) computed directly from the
    scenario probability tree.  Does not rely on any pre-aggregated field.
    """
    if price <= 0:
        return 0.0

    bull_target  = float(price_targets.get("bull_target")  or price)
    base_target  = float(price_targets.get("base_target")  or price)
    bear_target  = float(price_targets.get("bear_target")  or price)
    bull_prob    = float(price_targets.get("bull_probability") or 0.25)
    base_prob    = float(price_targets.get("base_probability") or 0.50)
    bear_prob    = float(price_targets.get("bear_probability") or 0.25)

    bull_return = (bull_target - price) / price * 100.0
    base_return = (base_target - price) / price * 100.0
    bear_return = (bear_target - price) / price * 100.0

    return bull_prob * bull_return + base_prob * base_return + bear_prob * bear_return


# ── Rationale builder ───────────────────────────────────────────────────────────

def _build_rationale(
    status: str,
    score: float,
    ev_percent: float,
    quality_score: float,
    drf: int,
    vp: int,
    starter_alloc: float,
) -> str:
    ev_str   = f"EV {ev_percent:+.1f}%"
    qual_str = f"quality {quality_score:.1f}/10"

    if status == "INITIATE":
        return (
            f"Score {score:.0f}/100 — {ev_str}, {qual_str}. "
            f"Starter {starter_alloc:.1f}% recommended."
        )

    if status == "WATCHLIST":
        blockers = []
        if drf >= 5:
            blockers.append("downside risk elevated")
        if vp >= 5:
            blockers.append("volatility high")
        reason = "; ".join(blockers) if blockers else "conditions mixed"
        return (
            f"Score {score:.0f}/100 — {ev_str}, {qual_str}. "
            f"Monitoring: {reason}."
        )

    # WAIT
    blockers = []
    if ev_percent < 5.0:
        blockers.append("insufficient expected return")
    if drf >= 10:
        blockers.append("high downside risk")
    if vp >= 10:
        blockers.append("elevated volatility")
    reason = "; ".join(blockers) if blockers else "risk/reward not favourable"
    return (
        f"Score {score:.0f}/100 — {ev_str}, {qual_str}. "
        f"Wait: {reason}."
    )


# ── Public API ──────────────────────────────────────────────────────────────────

def calculate_initiation_decision(
    current_price: float,
    conviction_position: Optional[Dict[str, Any]],
    price_targets: Optional[Dict[str, Any]],
    signal_breakdown: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Deterministic INITIATE / WATCHLIST / WAIT decision.

    Args:
        current_price:      Live price from valuation_metrics
        conviction_position: From decision_intelligence_calculator output
        price_targets:      Fundamentalist PriceTargetScenarios dict
        signal_breakdown:   Quant signal_breakdown dict (for beta)

    Returns:
        Dict matching InitiationDecision, or None if inputs are insufficient.
        Never raises — failures return None and log a message.

    Note:
        This function is read-only with respect to all upstream calculations.
        It does NOT modify EV, quality scores, or valuation outputs.
    """
    if not price_targets or not conviction_position or current_price <= 0:
        return None

    try:
        # ── Input extraction ───────────────────────────────────────────────────

        # 1. Probability-weighted expected return
        ev_percent = _compute_ev_percent(current_price, price_targets)

        # 2. Bear-case downside return
        bear_target = float(price_targets.get("bear_target") or current_price)
        downside_percent = (bear_target - current_price) / current_price * 100.0

        # 3. Quality score (0–10) — from valuation_metadata written by blended_valuation
        valuation_metadata: Dict = price_targets.get("valuation_metadata") or {}
        raw_quality = valuation_metadata.get("quality_score")
        quality_score = float(raw_quality) if raw_quality is not None else 5.0
        quality_score = max(0.0, min(10.0, quality_score))

        # 4. Fair-value band endpoints
        fair_value_low  = float(price_targets.get("fair_value_low")  or current_price)
        fair_value_mid  = float(price_targets.get("fair_value_mid")  or current_price)
        fair_value_high = float(price_targets.get("fair_value_high") or current_price)

        # 5. Volatility/beta proxy
        factor_diag = (signal_breakdown or {}).get("factor_diagnostics") or {}
        raw_beta = factor_diag.get("beta_estimate")
        volatility_beta = float(raw_beta) if raw_beta is not None else 1.0

        # ── Step 1: Intermediate factors ───────────────────────────────────────

        vdf = _valuation_discount_factor(current_price, fair_value_low, fair_value_high)
        drf = _downside_risk_factor(downside_percent)
        vp  = _volatility_penalty(volatility_beta)

        # ── Step 2: Raw composite ──────────────────────────────────────────────
        # VDF (valuation discount factor) excluded — price vs intrinsic must
        # never gate initiation. Score reflects quality + risk only.

        raw = (
            ev_percent   * 3.0
            + quality_score * 4.0
            - drf           * 3.0
            - vp            * 2.0
        )

        # ── Step 3: Normalise → 0–100, apply threshold ─────────────────────────

        score  = _normalize(raw)
        status = _status_from_score(score)

        # ── Step 4: Starter allocation ─────────────────────────────────────────

        base_position = float(conviction_position.get("recommended_pct") or 5.0)
        max_position  = float(conviction_position.get("max_pct") or 10.0)

        starter_alloc = base_position * (ev_percent / 10.0) * (quality_score / 8.0)
        min_alloc = 1.0
        max_alloc = max_position * 0.40          # "40% of max allowed position"
        starter_alloc = max(min_alloc, min(max_alloc, starter_alloc))
        starter_alloc = round(starter_alloc, 2)

        # ── Step 5: Required entry zone ────────────────────────────────────────

        required_entry_zone = [round(fair_value_low, 2), round(fair_value_mid, 2)]

        # ── Step 6: One-line rationale ─────────────────────────────────────────

        rationale = _build_rationale(
            status, score, ev_percent, quality_score,
            drf, vp, starter_alloc,
        )

        return {
            "status": status,
            "initiation_score": round(score, 1),
            "starter_allocation_percent": starter_alloc,
            "required_entry_zone": required_entry_zone,
            "rationale_summary": rationale,
            # ── Transparency diagnostics (not rendered by default) ─────────────
            "_diagnostics": {
                "ev_percent":               round(ev_percent, 2),
                "downside_percent":          round(downside_percent, 2),
                "quality_score":             quality_score,
                "volatility_beta":           volatility_beta,
                "valuation_discount_factor": vdf,
                "downside_risk_factor":      drf,
                "volatility_penalty":        vp,
                "raw_composite":             round(raw, 2),
            },
        }

    except Exception as exc:
        print(f"[InitiationModel] Calculation failed: {exc}")
        return None
