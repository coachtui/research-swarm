"""
Portfolio Intelligence Engine — Phase 1

Pure computation module. No async, no DB calls.

Takes a list of position dicts (with extracted scoring data from StockResult.fullOutput)
and returns a structured PortfolioIntelligenceResult dict suitable for JSON serialization.

Tier levels:
  basic  — Starter+: PM memo + 3-row alignment matrix + positions_scored
  full   — Investor+: + edge score + concentration + regime vulnerability + 3 misalignment flags
  stress — Trader:   + all 5 misalignment flags + thematic clustering
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Optional


# ── Sector → Thematic Theme Mapping ──────────────────────────────────────────

_SECTOR_TO_THEME: dict[str, str] = {
    "Technology":              "Tech / AI",
    "Communication Services":  "Tech / AI",
    "Consumer Cyclical":       "Consumer",
    "Consumer Defensive":      "Consumer",
    "Energy":                  "Energy",
    "Financial Services":      "Financial",
    "Healthcare":              "Healthcare",
    "Industrials":             "Industrials",
    "Basic Materials":         "Industrials",
    "Real Estate":             "Real Estate",
    "Utilities":               "Utilities",
}


# ── Score Helpers ─────────────────────────────────────────────────────────────

def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _valuation_gap_score(price_vs_intrinsic_pct: float) -> float:
    """
    Convert price_vs_intrinsic_pct to a 0-10 attractiveness score.
    -50% (deeply discounted) → 10
      0% (at fair value)     →  5
    +50% (expensive)         →  0
    """
    return _clamp((50.0 - price_vs_intrinsic_pct) / 10.0, 0.0, 10.0)


def _regime_score_from_status(status: str) -> float:
    """INITIATE → 9, WATCHLIST → 6.5, WAIT → 2.5. Smoothed to avoid cliff effects."""
    return {"INITIATE": 9.0, "WATCHLIST": 6.5, "WAIT": 2.5}.get(status, 2.5)


def _hhi(weights: list[float]) -> float:
    """Herfindahl-Hirschman Index. Input: decimal weights (0-1). Output: 0-10000."""
    return sum(w * w for w in weights) * 10_000


def _concentration_score_from_hhi(hhi: float) -> float:
    """
    10 (equal-weight) → 0 penalty → score 10
    HHI 2500 → full penalty → score 0
    Score = 10 - clamp((HHI - 1000) / 150, 0, 10)
    """
    return _clamp(10.0 - (hhi - 1000.0) / 150.0, 0.0, 10.0)


def _edge_label(score: float) -> str:
    if score >= 8.0:
        return "High Conviction Alignment"
    if score >= 6.0:
        return "Constructive"
    if score >= 4.0:
        return "Neutral"
    return "Defensive"


# ── Per-Position Extraction ───────────────────────────────────────────────────

def _extract_position(
    ticker: str,
    weight: float,
    full_output: Optional[dict],
    sector: str,
    moat_score: float,
) -> dict:
    """
    Extract scoring fields from a StockResult's fullOutput JSON.
    Returns a PositionIntelligence dict.
    Falls back to neutral defaults if data is missing.
    """
    if not full_output:
        return {
            "ticker": ticker,
            "weight": weight,
            "sector": sector or "Unknown",
            "structural_quality": 5.0,
            "valuation_gap_pct": 0.0,
            "divergence_score": 5.0,
            "divergence_phase": "Weak",
            "initiation_status": "WAIT",
            "initiation_score": 0.0,
            "bear_return_pct": -15.0,
            "bull_return_pct": 25.0,
            "moat_score": float(moat_score or 5.0),
            "has_data": False,
        }

    fund = full_output.get("fundamentalist_output") or {}
    di = full_output.get("decision_intelligence") or {}
    dvrg = di.get("divergence_overlay") or {}
    init_dec = di.get("initiation_decision") or {}
    pt = fund.get("price_targets") or {}
    quant = full_output.get("quant_output") or {}
    tech = quant.get("technical_indicators") or {}

    structural_quality = float(fund.get("financial_health_score") or 5.0)

    price_vs_intrinsic = dvrg.get("price_vs_intrinsic_pct")
    valuation_gap_pct = float(price_vs_intrinsic) if price_vs_intrinsic is not None else 0.0

    divergence_score = float(dvrg.get("divergence_score") or 5.0)
    divergence_phase = dvrg.get("divergence_phase") or "Weak"

    initiation_status = init_dec.get("status") or "WAIT"
    initiation_score = float(init_dec.get("initiation_score") or 0.0)

    # Bear/bull returns from price targets vs current price
    current_price = float(tech.get("current_price") or 0.0)
    bear_target = float(pt.get("bear_target") or 0.0)
    bull_target = float(pt.get("bull_target") or 0.0)

    if current_price > 0 and bear_target > 0:
        bear_return_pct = (bear_target / current_price - 1.0) * 100.0
    else:
        bear_return_pct = -15.0

    if current_price > 0 and bull_target > 0:
        bull_return_pct = (bull_target / current_price - 1.0) * 100.0
    else:
        bull_return_pct = 25.0

    return {
        "ticker": ticker,
        "weight": weight,
        "sector": sector or "Unknown",
        "structural_quality": _clamp(structural_quality, 0.0, 10.0),
        "valuation_gap_pct": valuation_gap_pct,
        "divergence_score": _clamp(divergence_score, 0.0, 10.0),
        "divergence_phase": divergence_phase,
        "initiation_status": initiation_status,
        "initiation_score": _clamp(initiation_score, 0.0, 100.0),
        "bear_return_pct": bear_return_pct,
        "bull_return_pct": bull_return_pct,
        "moat_score": float(moat_score or 5.0),
        "has_data": True,
    }


# ── Portfolio Edge Score ──────────────────────────────────────────────────────

def _compute_edge_score(positions: list[dict]) -> dict:
    """
    Compute weighted Portfolio Edge Score (0-10).
    Uses position weights as the weighting factor.
    Returns a dict with total, label, and component scores.
    """
    scored = [p for p in positions if p["has_data"]]
    if not scored:
        return {
            "total": 0.0,
            "label": "Defensive",
            "structural_component": 0.0,
            "valuation_component": 0.0,
            "divergence_component": 0.0,
            "regime_component": 0.0,
            "concentration_score": 5.0,
            "weights_applied": {"structural": 0.25, "valuation": 0.25, "divergence": 0.20,
                                 "regime": 0.15, "concentration": 0.15},
        }

    total_weight = sum(p["weight"] for p in scored)
    w = lambda p: p["weight"] / total_weight if total_weight > 0 else 1.0 / len(scored)

    # Structural (financial_health_score, already 0-10)
    structural = sum(p["structural_quality"] * w(p) for p in scored)

    # Valuation gap (map to 0-10 attractiveness)
    valuation = sum(_valuation_gap_score(p["valuation_gap_pct"]) * w(p) for p in scored)

    # Divergence (already 0-10)
    divergence = sum(p["divergence_score"] * w(p) for p in scored)

    # Regime alignment
    regime = sum(_regime_score_from_status(p["initiation_status"]) * w(p) for p in scored)

    # Concentration
    all_weights = [p["weight"] for p in positions]
    hhi = _hhi(all_weights)
    conc_score = _concentration_score_from_hhi(hhi)

    WEIGHTS = {"structural": 0.25, "valuation": 0.25, "divergence": 0.20,
               "regime": 0.15, "concentration": 0.15}

    total = (
        structural   * WEIGHTS["structural"]
        + valuation  * WEIGHTS["valuation"]
        + divergence * WEIGHTS["divergence"]
        + regime     * WEIGHTS["regime"]
        + conc_score * WEIGHTS["concentration"]
    )
    total = _clamp(total, 0.0, 10.0)

    return {
        "total": round(total, 2),
        "label": _edge_label(total),
        "structural_component": round(structural, 2),
        "valuation_component": round(valuation, 2),
        "divergence_component": round(divergence, 2),
        "regime_component": round(regime, 2),
        "concentration_score": round(conc_score, 2),
        "weights_applied": WEIGHTS,
    }


# ── Capital Alignment Matrix ──────────────────────────────────────────────────

def _compute_alignment_matrix(positions: list[dict], tier: str) -> list[dict]:
    """
    Return a list of alignment rows. Starter sees 3 rows; Investor/Trader see all 5.
    """
    scored = [p for p in positions if p["has_data"]]
    n = len(scored)
    total_w = sum(p["weight"] for p in scored) or 1.0

    def wavg(field: str) -> float:
        return sum(p[field] * p["weight"] for p in scored) / total_w

    # Structural Integrity
    avg_structural = wavg("structural_quality") if scored else 5.0
    structural_status = "Strong" if avg_structural >= 7.0 else ("Mixed" if avg_structural >= 4.0 else "Weak")

    # Valuation Exposure
    avg_gap = wavg("valuation_gap_pct") if scored else 0.0
    valuation_status = "Attractive" if avg_gap <= -10.0 else ("Fair" if avg_gap <= 10.0 else "Extended")

    # Concentration Risk
    all_weights = [p["weight"] for p in positions]
    hhi = _hhi(all_weights)
    conc_status = "Low" if hhi < 1500 else ("Moderate" if hhi < 2500 else "Elevated")

    rows_core = [
        {
            "dimension": "Structural Integrity",
            "status": structural_status,
            "metric_label": f"Avg quality {avg_structural:.1f}/10",
        },
        {
            "dimension": "Valuation Exposure",
            "status": valuation_status,
            "metric_label": f"Avg price-to-intrinsic {avg_gap:+.1f}%",
        },
        {
            "dimension": "Concentration Risk",
            "status": conc_status,
            "metric_label": f"HHI {hhi:.0f}",
        },
    ]

    if tier == "basic":
        return rows_core

    # Investor+ rows
    avg_divergence = wavg("divergence_score") if scored else 5.0
    divergence_status = "Confirmed" if avg_divergence >= 7.0 else ("Neutral" if avg_divergence >= 4.0 else "Weak")

    initiate_pct = (
        sum(1 for p in scored if p["initiation_status"] == "INITIATE") / n * 100
        if n > 0 else 0.0
    )
    regime_status = "Tailwind" if initiate_pct >= 60.0 else ("Neutral" if initiate_pct >= 30.0 else "Headwind")

    return rows_core + [
        {
            "dimension": "Divergence Alignment",
            "status": divergence_status,
            "metric_label": f"Avg score {avg_divergence:.1f}/10",
        },
        {
            "dimension": "Regime Fit",
            "status": regime_status,
            "metric_label": f"{initiate_pct:.0f}% positions at Initiate",
        },
    ]


# ── Concentration Diagnostics ─────────────────────────────────────────────────

def _compute_concentration(positions: list[dict], include_thematic: bool) -> dict:
    """
    Compute concentration diagnostics including top holdings, sector breakdown,
    and optionally thematic clusters.
    """
    sorted_positions = sorted(positions, key=lambda p: p["weight"], reverse=True)

    # Top 3 by weight
    top_3 = [{"ticker": p["ticker"], "weight": round(p["weight"] * 100, 1)}
              for p in sorted_positions[:3]]
    top_3_weight_pct = round(sum(p["weight"] for p in sorted_positions[:3]) * 100, 1)

    # Sector breakdown
    sector_weights: dict[str, float] = {}
    for p in positions:
        s = p["sector"] or "Unknown"
        sector_weights[s] = sector_weights.get(s, 0.0) + p["weight"]
    sector_breakdown = {k: round(v * 100, 1) for k, v in sorted(sector_weights.items(), key=lambda x: -x[1])}

    top_sector = max(sector_weights, key=sector_weights.get) if sector_weights else "Unknown"
    top_sector_weight_pct = round(sector_weights.get(top_sector, 0.0) * 100, 1)

    # HHI
    all_weights = [p["weight"] for p in positions]
    hhi = round(_hhi(all_weights), 1)
    concentration_label = "Low" if hhi < 1500 else ("Moderate" if hhi < 2500 else "Elevated")

    # Largest single-name downside impact
    downside_impacts = [
        (p["ticker"], p["weight"] * abs(p["bear_return_pct"]))
        for p in positions if p.get("has_data")
    ]
    downside_impacts.sort(key=lambda x: -x[1])
    largest_downside_ticker = downside_impacts[0][0] if downside_impacts else ""
    largest_downside_impact_pct = round(downside_impacts[0][1], 2) if downside_impacts else 0.0

    result = {
        "top_3_tickers": top_3,
        "top_3_weight_pct": top_3_weight_pct,
        "sector_breakdown": sector_breakdown,
        "top_sector": top_sector,
        "top_sector_weight_pct": top_sector_weight_pct,
        "hhi": hhi,
        "concentration_label": concentration_label,
        "largest_downside_ticker": largest_downside_ticker,
        "largest_downside_impact_pct": largest_downside_impact_pct,
    }

    # Thematic clusters (Trader only)
    if include_thematic:
        thematic_weights: dict[str, float] = {}
        for p in positions:
            theme = _SECTOR_TO_THEME.get(p["sector"], "Other")
            thematic_weights[theme] = thematic_weights.get(theme, 0.0) + p["weight"]
        result["thematic_clusters"] = {
            k: round(v * 100, 1)
            for k, v in sorted(thematic_weights.items(), key=lambda x: -x[1])
        }
    else:
        result["thematic_clusters"] = {}

    return result


# ── Regime Vulnerability ──────────────────────────────────────────────────────

def _compute_regime_vulnerability(positions: list[dict], alignment_matrix: list[dict]) -> dict:
    """
    Compute regime vulnerability metrics using bear/bull scenario returns.
    """
    scored = [p for p in positions if p.get("has_data")]
    total_w = sum(p["weight"] for p in scored) or 1.0

    # Weighted portfolio bear return
    projected_drawdown = sum(p["weight"] * p["bear_return_pct"] for p in scored)
    weighted_bull = sum(p["weight"] * p["bull_return_pct"] for p in scored)

    # Top 3 most vulnerable (by position weight × |bear_return|)
    vulnerability_scores = [
        {
            "ticker": p["ticker"],
            "impact_pct": round(p["weight"] * abs(p["bear_return_pct"]), 2),
            "bear_return_pct": round(p["bear_return_pct"], 1),
            "weight_pct": round(p["weight"] * 100, 1),
        }
        for p in scored
    ]
    vulnerability_scores.sort(key=lambda x: -x["impact_pct"])
    most_vulnerable = vulnerability_scores[:3]

    # Infer regime label from alignment matrix
    regime_row = next((r for r in alignment_matrix if r["dimension"] == "Regime Fit"), None)
    regime_fit = regime_row["status"] if regime_row else "Neutral"
    regime_label = {"Tailwind": "Expansion", "Neutral": "Neutral", "Headwind": "Contraction"}.get(
        regime_fit, "Neutral"
    )

    # Expansion compression risk: positions with price > intrinsic
    overvalued = [p for p in scored if p["valuation_gap_pct"] > 15.0]
    expansion_compression_risk = round(
        sum(p["valuation_gap_pct"] * p["weight"] for p in overvalued) / total_w, 1
    ) if overvalued else 0.0

    return {
        "projected_portfolio_drawdown": round(projected_drawdown, 1),
        "weighted_bull_return": round(weighted_bull, 1),
        "most_vulnerable": most_vulnerable,
        "regime_label": regime_label,
        "expansion_compression_risk": expansion_compression_risk,
    }


# ── Misalignment Flags ────────────────────────────────────────────────────────

def _compute_misalignment_flags(positions: list[dict], tier: str) -> list[dict]:
    """
    Compute misalignment flags. Investor+ sees first 3, Trader sees all 5.
    All 5 are always computed; the route/frontend controls visibility.
    """
    scored = [p for p in positions if p.get("has_data")]
    total_covered_weight = sum(p["weight"] for p in scored)
    total_w = sum(p["weight"] for p in positions) or 1.0
    covered_fraction = total_covered_weight / total_w

    flags: list[dict] = []

    # Flag 1: Low valuation gap but heavy allocation
    if scored:
        avg_gap = sum(p["valuation_gap_pct"] * p["weight"] for p in scored) / total_covered_weight
        if avg_gap > -5.0 and covered_fraction > 0.80:
            flags.append({
                "code": "LOW_VALUATION_HEAVY",
                "severity": "warning",
                "message": f"Average valuation gap limited ({avg_gap:+.1f}%) — limited asymmetry across deployed capital.",
                "affected_tickers": [p["ticker"] for p in scored if p["valuation_gap_pct"] > 0],
            })

    # Flag 2: Weak divergence overweight
    if scored:
        weak_weight = sum(
            p["weight"] for p in scored
            if p["divergence_phase"] in ("Weak",)
        )
        weak_pct = weak_weight / total_covered_weight if total_covered_weight > 0 else 0.0
        if weak_pct > 0.60:
            flags.append({
                "code": "WEAK_DIVERGENCE_OVERWEIGHT",
                "severity": "warning",
                "message": f"{weak_pct*100:.0f}% of portfolio weight shows weak dislocation — limited near-term edge.",
                "affected_tickers": [p["ticker"] for p in scored if p["divergence_phase"] == "Weak"],
            })

    # Flag 3: Sector concentration
    sector_weights: dict[str, float] = {}
    for p in positions:
        s = p["sector"] or "Unknown"
        sector_weights[s] = sector_weights.get(s, 0.0) + p["weight"]
    if sector_weights:
        top_sector = max(sector_weights, key=sector_weights.get)
        top_pct = sector_weights[top_sector]
        if top_pct > 0.40:
            flags.append({
                "code": "SECTOR_CONCENTRATION",
                "severity": "critical" if top_pct > 0.55 else "warning",
                "message": f"{top_pct*100:.0f}% concentration in {top_sector} — single-sector drawdown risk elevated.",
                "affected_tickers": [p["ticker"] for p in positions if p["sector"] == top_sector],
            })

    if tier == "full":
        return flags[:3]

    # Trader-only flags (flags 4 & 5)

    # Flag 4: Divergence-regime mismatch
    if scored:
        avg_dvrg = sum(p["divergence_score"] * p["weight"] for p in scored) / total_covered_weight
        initiate_count = sum(1 for p in scored if p["initiation_status"] == "INITIATE")
        initiate_pct = initiate_count / len(scored) if scored else 0.0
        if avg_dvrg >= 7.0 and initiate_pct < 0.30:
            flags.append({
                "code": "DVRG_REGIME_MISMATCH",
                "severity": "warning",
                "message": f"Strong dislocation signals (avg {avg_dvrg:.1f}/10) but {initiate_pct*100:.0f}% of positions at Initiate — regime misalignment.",
                "affected_tickers": [p["ticker"] for p in scored if p["divergence_score"] >= 7.0],
            })

    # Flag 5: WAIT-heavy allocation
    if scored:
        wait_weight = sum(p["weight"] for p in scored if p["initiation_status"] == "WAIT")
        wait_pct = wait_weight / total_covered_weight if total_covered_weight > 0 else 0.0
        if wait_pct > 0.60:
            flags.append({
                "code": "WAIT_HEAVY",
                "severity": "warning",
                "message": f"{wait_pct*100:.0f}% of capital in positions with WAIT initiation status — structural overcommitment risk.",
                "affected_tickers": [p["ticker"] for p in scored if p["initiation_status"] == "WAIT"],
            })

    return flags


# ── PM Memo ───────────────────────────────────────────────────────────────────

def _generate_pm_memo(
    positions: list[dict],
    alignment_matrix: list[dict],
    edge_score: Optional[dict],
    regime_vulnerability: Optional[dict],
    misalignment_flags: list[dict],
    tier: str,
) -> str:
    """
    Generate a concise institutional-tone PM memo summarising portfolio intelligence.
    """
    scored = [p for p in positions if p.get("has_data")]
    n = len(positions)
    n_scored = len(scored)
    total_w = sum(p["weight"] for p in scored) or 1.0

    # Structural label
    structural_row = next((r for r in alignment_matrix if r["dimension"] == "Structural Integrity"), None)
    structural_label = structural_row["status"].lower() if structural_row else "mixed"

    # Valuation label
    val_row = next((r for r in alignment_matrix if r["dimension"] == "Valuation Exposure"), None)
    valuation_label = val_row["status"].lower() if val_row else "fair"

    avg_gap = sum(p["valuation_gap_pct"] * p["weight"] for p in scored) / total_w if scored else 0.0
    gap_str = f"{avg_gap:+.1f}%" if scored else "unknown"

    parts: list[str] = []

    # Opening sentence
    coverage_note = "" if n_scored == n else f" ({n_scored}/{n} positions with current data)"
    parts.append(
        f"{n}-position portfolio demonstrates {structural_label} structural integrity{coverage_note}."
    )

    # Valuation
    parts.append(
        f"Valuation exposure {valuation_label} — average price-to-intrinsic {gap_str}."
    )

    # Divergence (Investor+)
    if tier in ("full", "stress") and scored:
        avg_dvrg = sum(p["divergence_score"] * p["weight"] for p in scored) / total_w
        dvrg_row = next((r for r in alignment_matrix if r["dimension"] == "Divergence Alignment"), None)
        dvrg_label = dvrg_row["status"] if dvrg_row else "Neutral"
        parts.append(
            f"Dislocation alignment {dvrg_label.lower()} — portfolio-weighted divergence score {avg_dvrg:.1f}/10."
        )

    # Regime (Investor+)
    if tier in ("full", "stress"):
        regime_row = next((r for r in alignment_matrix if r["dimension"] == "Regime Fit"), None)
        regime_label = regime_row["status"] if regime_row else "Neutral"
        initiate_row = next((r for r in alignment_matrix if r["dimension"] == "Regime Fit"), None)
        parts.append(f"Current regime positioning {regime_label.lower()}.")

    # Concentration
    conc_row = next((r for r in alignment_matrix if r["dimension"] == "Concentration Risk"), None)
    conc_status = conc_row["status"] if conc_row else "Moderate"
    if conc_status == "Elevated":
        sector_weights: dict[str, float] = {}
        for p in positions:
            s = p["sector"] or "Unknown"
            sector_weights[s] = sector_weights.get(s, 0.0) + p["weight"]
        top_sector = max(sector_weights, key=sector_weights.get) if sector_weights else "Unknown"
        top_pct = round(sector_weights.get(top_sector, 0.0) * 100, 0)
        parts.append(
            f"Concentration elevated — {top_pct:.0f}% exposure in {top_sector}."
        )

    # First active flag
    if misalignment_flags:
        parts.append(misalignment_flags[0]["message"])

    # Bear-case note
    if regime_vulnerability and tier in ("full", "stress"):
        drawdown = regime_vulnerability.get("projected_portfolio_drawdown", 0.0)
        parts.append(
            f"Bear-case scenario implies {abs(drawdown):.1f}% portfolio drawdown if regime deteriorates."
        )

    return " ".join(parts)


# ── Main Entry Point ──────────────────────────────────────────────────────────

def compute_portfolio_intelligence(
    portfolio_id: str,
    positions_data: list[dict],
    tier: str = "basic",
) -> dict:
    """
    Compute full Portfolio Intelligence result.

    Args:
        portfolio_id: The portfolio's ID string.
        positions_data: List of dicts, each with keys:
            - ticker: str
            - weight: float (decimal, 0-1)
            - full_output: dict | None  (StockResult.fullOutput parsed JSON)
            - sector: str | None
            - moat_score: float | None
        tier: "basic" | "full" | "stress"

    Returns:
        A JSON-serializable dict with the full portfolio intelligence result.
        The route may strip fields before returning based on caller tier.
    """
    if tier not in ("basic", "full", "stress"):
        tier = "basic"

    # 1. Extract per-position intelligence
    positions = [
        _extract_position(
            ticker=p["ticker"],
            weight=float(p.get("weight") or 0.0),
            full_output=p.get("full_output"),
            sector=p.get("sector") or "Unknown",
            moat_score=float(p.get("moat_score") or 5.0),
        )
        for p in positions_data
    ]

    scored = [p for p in positions if p["has_data"]]
    total_w_scored = sum(p["weight"] for p in scored)
    total_w_all = sum(p["weight"] for p in positions) or 1.0

    # 2. Alignment matrix
    alignment_matrix = _compute_alignment_matrix(positions, tier)

    # 3. Edge score (Investor+)
    edge_score = _compute_edge_score(positions) if tier in ("full", "stress") else None

    # 4. Concentration diagnostics (Investor+)
    include_thematic = tier == "stress"
    concentration = (
        _compute_concentration(positions, include_thematic) if tier in ("full", "stress") else None
    )

    # 5. Regime vulnerability (Investor+)
    regime_vulnerability = (
        _compute_regime_vulnerability(positions, alignment_matrix) if tier in ("full", "stress") else None
    )

    # 6. Misalignment flags
    if tier == "basic":
        misalignment_flags = []
    else:
        misalignment_flags = _compute_misalignment_flags(positions, tier)

    # 7. PM memo
    pm_memo = _generate_pm_memo(
        positions, alignment_matrix, edge_score, regime_vulnerability, misalignment_flags, tier
    )

    return {
        "portfolio_id": portfolio_id,
        "position_count": len(positions),
        "positions_with_data": len(scored),
        "total_weight_covered": round(total_w_scored / total_w_all, 3),
        "tier": tier,
        "edge_score": edge_score,
        "alignment_matrix": alignment_matrix,
        "concentration": concentration,
        "regime_vulnerability": regime_vulnerability,
        "misalignment_flags": misalignment_flags,
        "pm_memo": pm_memo,
        "positions_scored": positions,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }
