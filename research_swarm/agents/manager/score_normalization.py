"""
Component normalization for the composite scores.

A weighted average only distributes influence the way its weights claim when
the components share a comparable spread. Ours did not. The technical score
sits high and narrow (a stock with no signal at all lands near 7.6), while the
ROIC/WACC score is wide and nearly bimodal (1.5 for value destroyers, 9.5-10
for compounders). Averaging those raw means the wide component dominates
regardless of the number written next to it: the technical composite's stated
weights of 30/25/20/15/10 were measured to behave closer to 38/10/3/46/3.

So every component is mapped onto a common scale before weighting:

    normalized = 5.0 + 2.0 * (raw - center) / spread     (clamped to [0, 10])

which places each component at 5.0 when it is typical and moves it ~2 points
per standard deviation. After this, a one-sigma move in any component shifts
the composite by (2 x its weight), and the weights mean what they say.

CALIBRATION HONESTY
-------------------
The constants below are SEED ESTIMATES, derived from the score distributions
observed during development plus the audit's measurements — not from a fitted
cross-sectional sample. They are deliberately conservative (wide spreads,
centers near the observed middle) so normalization corrects the gross
mis-weighting without manufacturing false precision.

They should be re-fit against a real universe. The procedure:

    1. Score a broad universe (S&P 500 is the natural choice) and record every
       raw component.
    2. Set `center` to that component's median and `spread` to its standard
       deviation (or IQR/1.35 if the tail is heavy).
    3. Re-check the rating distribution afterwards — normalization changes the
       composite's spread, so the tier thresholds in `scorer.py` must be
       reviewed at the same time.

Until that run happens, treat any single component's normalized value as
directionally right rather than precisely calibrated.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from research_swarm.logger import logger

# component name -> (center, spread) on the raw 0-10 scale.
#
# center: the value a typical company scores
# spread: roughly one standard deviation of the raw component
COMPONENT_CALIBRATION: Dict[str, Tuple[float, float]] = {
    # ALL MEASURED — no seed estimates remain.
    #
    # Sources (scripts/calibrate_score_components.py):
    #   stored — 373 completed analyses in Neon, for components whose
    #            calculation is unchanged and whose history is therefore valid
    #   fresh  — 188 S&P names rescored live, for components recalculated in
    #            recent work whose stored history the current code would never
    #            reproduce
    #
    # Every seeded center was too LOW, and consistently so on the three quality
    # components. Together they inflated the quality score by roughly 1.8
    # points, which pushed most of the market into the top tier and is exactly
    # the compression the weight review set out to fix. Guessing centers is not
    # a small error: it is a systematic bias in the headline number.
    #
    #   component            seeded        measured       center miss
    #   roic_wacc_spread     (6.0, 2.5)  → (8.00, 3.27)   -2.00
    #   financial_health     (6.5, 1.4)  → (7.73, 1.56)   -1.23
    #   earnings_momentum    (5.5, 1.5)  → (7.07, 2.00)   -1.57
    #   valuation            (5.0, 2.0)  → (5.00, 1.78)    0.00
    #   sentiment_catalysts  (5.5, 1.2)  → (6.76, 1.82)   -1.26
    #   technical            (6.5, 1.2)  → (5.99, 1.30)   +0.51

    # Very wide and saturating at both ends: p10 1.5 (value destroyers), p90
    # 10.0 (the bands top out, so compounders pile at the ceiling).
    "roic_wacc_spread": (8.00, 3.27),      # fresh,  n=178, p10 1.5 / p90 10.0
    "financial_health": (7.73, 1.56),      # stored, n=373, p10 4.9 / p90  9.2
    "earnings_momentum": (7.07, 2.00),     # fresh,  n=188, p10 4.1 / p90  9.4
    # The one component already centred where it was guessed — and the only one
    # with a genuinely symmetric spread, since price richness cuts both ways.
    "valuation": (5.00, 1.78),             # fresh,  n=188, p10 2.6 / p90  7.8
    "sentiment_catalysts": (6.76, 1.82),   # stored, n=373, p10 4.7 / p90  8.8
    "technical": (5.99, 1.30),             # stored, n=373, p10 4.0 / p90  7.4
}

# Composite rescaling, measured over 188 scored names.
#
# Normalizing the COMPONENTS is necessary but not sufficient. The quality
# components turn out to be almost uncorrelated in practice —
# corr(roic, momentum) = +0.13, corr(roic, valuation) = -0.03 — and averaging
# uncorrelated variables shrinks variance. Three normalized components with
# spread ~2.0 at weights .35/.35/.30 produce a composite with spread ~1.1:
#
#     sigma_composite = 2.0 * sqrt(.35^2 + .35^2 + .30^2) = 1.16   (measured 1.10)
#
# So tier bounds meant to sit at +/-0.75 sigma were really at +/-1.36 sigma, and
# the market split 4.3% high / 55.9% mid / 39.9% low. Only eight of 188 large
# caps clearing "high quality" is not a credible read; it is the same
# compression the weight review set out to remove, one level up.
#
# Rescaling the composite back to a 2-points-per-sigma scale keeps the tier
# thresholds interpretable — 6.5 really is about the top quartile, 4.5 about
# the bottom — instead of being numbers that happen to land somewhere.
#
# Re-measure alongside COMPONENT_CALIBRATION: the composite's centre and spread
# depend on the component correlations, so they move whenever a component's
# calculation changes.
# The spread below is correlation-ADJUSTED, not the raw simulated figure.
#
# Measuring the composite directly needs a per-ticker financial_health, which
# only the (expensive) LLM scorer produces — so the sample drew it from its
# measured distribution INDEPENDENTLY. That understates the spread, because
# these components are not independent. Production data gives
# corr(health, sentiment) +0.27, corr(sentiment, technical) +0.30,
# corr(health, technical) -0.05; the fresh sample gives
# corr(roic, momentum) +0.13.
#
# Applying the mean of those measured correlations (+0.163) to the two
# unmeasured pairs, via  s^2 = sum wi^2 si^2 + 2 sum wi wj si sj rho :
#
#     independent           sigma = 1.158   (matches the 1.10 simulated)
#     correlation-adjusted  sigma = 1.320   <- used
#
# Using 1.10 would over-widen the composite by ~15% and push too many names
# into the outer tiers. Replace both figures with a direct measurement once
# per-ticker financial_health is available.
COMPOSITE_CALIBRATION: Dict[str, Tuple[float, float]] = {
    "quality": (4.81, 1.32),   # centre n=188; spread correlation-adjusted
}

# Normalized output bounds. Kept at the raw scale's bounds so every downstream
# consumer, threshold and UI label continues to read a 0-10 number.
_MIN_SCORE = 0.0
_MAX_SCORE = 10.0

# Points of normalized movement per standard deviation of raw movement.
_POINTS_PER_SIGMA = 2.0


def normalize_component(name: str, raw: Optional[float]) -> Optional[float]:
    """Map one raw component onto the shared scale.

    Unknown component names pass through untouched rather than being silently
    rescaled against someone else's calibration — a wrong normalization is
    worse than none.
    """
    if raw is None:
        return None

    calibration = COMPONENT_CALIBRATION.get(name)
    if calibration is None:
        logger.debug(f"No calibration for component '{name}' — passing through raw")
        return raw

    center, spread = calibration
    if spread <= 0:
        return raw

    normalized = 5.0 + _POINTS_PER_SIGMA * (raw - center) / spread
    return round(max(_MIN_SCORE, min(_MAX_SCORE, normalized)), 3)


def normalize_components(components: Dict[str, Optional[float]]) -> Dict[str, Optional[float]]:
    """Normalize a whole component dict, preserving None entries."""
    return {name: normalize_component(name, raw) for name, raw in components.items()}


def rescale_composite(name: str, value: float) -> float:
    """Put a weighted composite back on the 2-points-per-sigma scale.

    Averaging shrinks spread, so a composite of normalized components is NOT
    itself on the normalized scale. Without this the tier thresholds read as
    far more extreme than intended — see COMPOSITE_CALIBRATION.
    """
    calibration = COMPOSITE_CALIBRATION.get(name)
    if calibration is None:
        return value

    center, spread = calibration
    if spread <= 0:
        return value

    rescaled = 5.0 + _POINTS_PER_SIGMA * (value - center) / spread
    return round(max(_MIN_SCORE, min(_MAX_SCORE, rescaled)), 3)
