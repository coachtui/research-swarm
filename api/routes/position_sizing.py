"""
POST /api/position-sizing

Dynamic Position Sizing Engine — Noise-Adjusted Exposure.

Accepts a structured input describing the noise/sensitivity/dispersion
characteristics of a stock's signal environment and returns a recommended
position weight with full multiplier explainability.

Config version: v1.0.0 (mirrors config/sizing-config.v1.json)
"""

import math
from typing import Optional, Literal, Dict, List, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator

router = APIRouter()

# ─── Versioned config (mirrors config/sizing-config.v1.json) ─────────────────

CONFIG_VERSION = "v1.0.0"

BASE_WEIGHTS: Dict[str, float] = {
    "CORE": 0.12,
    "SATELLITE": 0.05,
}

CAPS = {
    "min_weight": 0.0025,
    "max_weight": 0.12,
    "satellite_cap": 0.052,
}

NOISE_BUCKETS = [
    {"min": 0,  "max": 20,   "multiplier": 1.20, "label": "Very Low Noise"},
    {"min": 20, "max": 35,   "multiplier": 1.00, "label": "Low Noise"},
    {"min": 35, "max": 50,   "multiplier": 0.70, "label": "High Noise"},
    {"min": 50, "max": 70,   "multiplier": 0.50, "label": "Very High Noise"},
    {"min": 70, "max": None, "multiplier": 0.30, "label": "Extreme Noise"},
]

SENSITIVITY_MAP = {
    "LOW":      {"multiplier": 1.10, "label": "Low Sensitivity"},
    "MODERATE": {"multiplier": 0.90, "label": "Moderate Sensitivity"},
    "HIGH":     {"multiplier": 0.65, "label": "High Sensitivity"},
}

DISPERSION_BUCKETS = [
    {"min": 0,   "max": 1.5,  "multiplier": 1.10, "label": "Tight Dispersion (<1.5σ)"},
    {"min": 1.5, "max": 2.2,  "multiplier": 1.00, "label": "Normal Dispersion (1.5–2.2σ)"},
    {"min": 2.2, "max": None, "multiplier": 0.75, "label": "Wide Dispersion (>2.2σ)"},
]

STOP_BUCKETS = [
    {"min": 0,    "max": 0.15, "multiplier": 1.05, "label": "Low Stop Risk (<15%)"},
    {"min": 0.15, "max": 0.25, "multiplier": 1.00, "label": "Moderate Stop Risk (15–25%)"},
    {"min": 0.25, "max": None, "multiplier": 0.80, "label": "High Stop Risk (>25%)"},
]

BETA_CLAMP_MIN = 0.70
BETA_CLAMP_MAX = 1.10

EV_BUCKETS = [
    {"min": 0,    "max": 0.30, "multiplier": 0.80, "label": "Low EV Percentile (<30th)"},
    {"min": 0.30, "max": 0.60, "multiplier": 1.00, "label": "Mid EV Percentile (30–60th)"},
    {"min": 0.60, "max": None, "multiplier": 1.15, "label": "High EV Percentile (>60th)"},
]

EXPOSURE_SIZES = [10000, 50000, 100000]

# ─── Internal utilities ────────────────────────────────────────────────────────

def bucket_by_range(value: float, buckets: List[Dict]) -> Dict:
    """
    Select the matching bucket for a given value.

    Boundary convention: [min, max) — lower inclusive, upper exclusive.
    Final bucket (max=None) matches everything >= min.
    """
    for bucket in buckets:
        hi = bucket.get("max")
        if hi is None:
            return bucket
        if bucket["min"] <= value < hi:
            return bucket
    return buckets[-1]  # fallback


def _round6(v: float) -> float:
    return round(v, 6)


# ─── Request / Response models ────────────────────────────────────────────────

class SizingFlags(BaseModel):
    signal_conflict_active: bool = False
    cap_at_satellite: bool = False


class PositionSizingRequest(BaseModel):
    symbol: str = Field(..., description="Ticker symbol, e.g. 'NVDA'")
    classification: Literal["CORE", "SATELLITE"] = Field(
        ..., description="CORE = 12% base; SATELLITE = 5% base"
    )
    noise_score: float = Field(
        ..., ge=0, le=100, description="0–100: higher = noisier signal regime"
    )
    overall_sensitivity: Literal["LOW", "MODERATE", "HIGH"] = Field(
        ..., description="From ModelSensitivityAttribution"
    )
    signal_dispersion_sigma: float = Field(
        ..., ge=0, description="σ across all signals; higher = more internal disagreement"
    )
    stop_probability: float = Field(
        ..., ge=0, le=1, description="0–1: probability of hitting stop loss"
    )
    beta: Optional[float] = Field(
        None, gt=0, description="Market beta. Triggers M_beta = clamp(1/√β, 0.70, 1.10)"
    )
    ev_percentile: Optional[float] = Field(
        None, ge=0, le=1, description="0–1 percentile of expected value distribution"
    )
    flags: SizingFlags = Field(default_factory=SizingFlags)
    custom_exposure_sizes: Optional[List[int]] = Field(
        None, description="Custom portfolio sizes for dollar exposure examples"
    )


class MultiplierDetail(BaseModel):
    value: float
    bucket_label: str
    reason: str
    input_value: Any


class CapState(BaseModel):
    active: bool
    reason: str
    cap_value: Optional[float] = None


class PositionSizingResponse(BaseModel):
    symbol: str
    base_weight: float
    multipliers: Dict[str, MultiplierDetail]
    product_of_multipliers: float
    adjusted_weight: float
    adjusted_weight_pct: float
    cap_state: CapState
    notes: List[str]
    exposure_examples: Dict[str, int]
    config_version: str


# ─── Engine ───────────────────────────────────────────────────────────────────

def _compute_sizing(req: PositionSizingRequest) -> PositionSizingResponse:
    # Base weight
    base_weight = BASE_WEIGHTS[req.classification]

    # Noise multiplier
    nb = bucket_by_range(req.noise_score, NOISE_BUCKETS)
    noise_m = MultiplierDetail(
        value=nb["multiplier"],
        bucket_label=nb["label"],
        reason=f"Noise score {req.noise_score} → {nb['label']} bucket",
        input_value=req.noise_score,
    )

    # Sensitivity multiplier
    sens_entry = SENSITIVITY_MAP[req.overall_sensitivity]
    sensitivity_m = MultiplierDetail(
        value=sens_entry["multiplier"],
        bucket_label=sens_entry["label"],
        reason=f"Overall sensitivity {req.overall_sensitivity} → {sens_entry['label']}",
        input_value=req.overall_sensitivity,
    )

    # Dispersion multiplier
    db = bucket_by_range(req.signal_dispersion_sigma, DISPERSION_BUCKETS)
    dispersion_m = MultiplierDetail(
        value=db["multiplier"],
        bucket_label=db["label"],
        reason=f"Dispersion σ {req.signal_dispersion_sigma:.2f} → {db['label']}",
        input_value=req.signal_dispersion_sigma,
    )

    # Stop risk multiplier
    sb = bucket_by_range(req.stop_probability, STOP_BUCKETS)
    stoprisk_m = MultiplierDetail(
        value=sb["multiplier"],
        bucket_label=sb["label"],
        reason=f"Stop probability {req.stop_probability * 100:.0f}% → {sb['label']}",
        input_value=req.stop_probability,
    )

    # Optional: beta multiplier
    beta_m: Optional[MultiplierDetail] = None
    if req.beta is not None:
        raw_m = 1 / math.sqrt(req.beta)
        clamped = max(BETA_CLAMP_MIN, min(BETA_CLAMP_MAX, raw_m))
        was_clamped_low = clamped == BETA_CLAMP_MIN and raw_m < BETA_CLAMP_MIN
        was_clamped_high = clamped == BETA_CLAMP_MAX and raw_m > BETA_CLAMP_MAX
        beta_label = (
            "Clamped (high β)" if was_clamped_low
            else "Clamped (low β)" if was_clamped_high
            else "Beta-normalized"
        )
        beta_m = MultiplierDetail(
            value=clamped,
            bucket_label=beta_label,
            reason=(
                f"β {req.beta:.2f}: 1/√{req.beta:.2f} = {raw_m:.3f} "
                f"→ clamped [{BETA_CLAMP_MIN}, {BETA_CLAMP_MAX}] → {clamped:.3f}"
            ),
            input_value=req.beta,
        )

    # Optional: EV percentile multiplier
    ev_m: Optional[MultiplierDetail] = None
    if req.ev_percentile is not None:
        ev_b = bucket_by_range(req.ev_percentile, EV_BUCKETS)
        ev_m = MultiplierDetail(
            value=ev_b["multiplier"],
            bucket_label=ev_b["label"],
            reason=f"EV percentile {req.ev_percentile * 100:.0f}th → {ev_b['label']}",
            input_value=req.ev_percentile,
        )

    # Product of all multipliers
    total_product = (
        nb["multiplier"]
        * sens_entry["multiplier"]
        * db["multiplier"]
        * sb["multiplier"]
        * (beta_m.value if beta_m else 1.0)
        * (ev_m.value if ev_m else 1.0)
    )

    adjusted_weight = base_weight * total_product

    # Guardrails
    notes: List[str] = []
    cap_state = CapState(active=False, reason="")

    if req.flags.signal_conflict_active or req.flags.cap_at_satellite:
        sat_cap = CAPS["satellite_cap"]
        if adjusted_weight > sat_cap:
            adjusted_weight = sat_cap
            reason = (
                f"Signal conflict active — capped at satellite max ({sat_cap * 100:.1f}%)"
                if req.flags.signal_conflict_active
                else f"cap_at_satellite flag — capped at {sat_cap * 100:.1f}%"
            )
            cap_state = CapState(active=True, reason=reason, cap_value=sat_cap)
            notes.append(f"⚠ Position capped at {sat_cap * 100:.1f}% (satellite guardrail)")
        else:
            notes.append(
                f"Satellite cap {sat_cap * 100:.1f}% not triggered — "
                f"{adjusted_weight * 100:.2f}% is within guardrail"
            )

    min_w = CAPS["min_weight"]
    max_w = CAPS["max_weight"]
    pre_clamp = adjusted_weight
    adjusted_weight = max(min_w, min(max_w, adjusted_weight))
    if not cap_state.active and adjusted_weight != pre_clamp:
        if adjusted_weight == min_w:
            notes.append(f"Floor applied — minimum position weight {min_w * 100:.2f}%")
        else:
            cap_state = CapState(
                active=True,
                reason=f"Hard ceiling {max_w * 100:.0f}% reached",
                cap_value=max_w,
            )
            notes.append(f"Ceiling applied — maximum weight {max_w * 100:.0f}% enforced")

    if req.noise_score >= 50:
        notes.append("High Noise Environment — compress size")
    if req.overall_sensitivity == "HIGH":
        notes.append("High sensitivity — aggressive size reduction applied")
    notes.append(
        f"{'Satellite' if req.classification == 'SATELLITE' else 'Core'} mandate "
        f"— base weight {base_weight * 100:.0f}%"
    )

    # Dollar exposure
    sizes = req.custom_exposure_sizes or EXPOSURE_SIZES
    exposure_examples: Dict[str, int] = {
        str(size): round(size * adjusted_weight) for size in sizes
    }

    # Assemble multipliers dict
    multipliers: Dict[str, MultiplierDetail] = {
        "noise": noise_m,
        "sensitivity": sensitivity_m,
        "dispersion": dispersion_m,
        "stoprisk": stoprisk_m,
    }
    if beta_m:
        multipliers["beta"] = beta_m
    if ev_m:
        multipliers["ev_percentile"] = ev_m

    return PositionSizingResponse(
        symbol=req.symbol,
        base_weight=base_weight,
        multipliers=multipliers,
        product_of_multipliers=_round6(total_product),
        adjusted_weight=_round6(adjusted_weight),
        adjusted_weight_pct=round(adjusted_weight * 10000) / 100,
        cap_state=cap_state,
        notes=notes,
        exposure_examples=exposure_examples,
        config_version=CONFIG_VERSION,
    )


# ─── Route ────────────────────────────────────────────────────────────────────

@router.post("/position-sizing", response_model=PositionSizingResponse)
async def compute_position_sizing(request: PositionSizingRequest):
    """
    Compute noise-adjusted position sizing.

    Given a stock's signal regime diagnostics (noise score, sensitivity,
    dispersion, stop risk), returns a recommended position weight with
    full multiplier explainability and dollar exposure examples.

    **Formula:**
    AdjustedWeight = BaseWeight × M_noise × M_sensitivity × M_dispersion × M_stoprisk
                   × M_beta (optional) × M_ev_percentile (optional)

    **Acceptance test (NVDA):**
    - noise=40 → M_noise=0.70 (High Noise)
    - sensitivity=MODERATE → M_sensitivity=0.90
    - sigma=2.53 → M_dispersion=0.75 (Wide)
    - stop=0.22 → M_stoprisk=1.00 (Moderate)
    - Result: 5% × 0.70 × 0.90 × 0.75 × 1.00 ≈ 2.36%

    Config version: v1.0.0
    """
    try:
        return _compute_sizing(request)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
