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
    # ── MEASURED — from 373 completed analyses in production (Neon), via
    #    scripts/calibrate_score_components.py --stored. These components'
    #    calculations are unchanged, so stored history is a valid sample.
    #
    #    Note how far the seed estimates were off: financial_health was seeded
    #    at 6.5 when the real median is 7.73, so every company was being
    #    normalized ~1.6 points too high on a component carrying 35% of the
    #    quality score.
    "financial_health": (7.73, 1.56),      # n=373, p10 4.9 / p90 9.2
    "sentiment_catalysts": (6.76, 1.82),   # n=373, p10 4.7 / p90 8.8
    "technical": (5.99, 1.30),             # n=373, p10 4.0 / p90 7.4

    # ── SEED ESTIMATES — still unmeasured.
    #    These three were recalculated in recent work (ROIC replaced ROE;
    #    earnings momentum was unpinned from a constant), so stored history
    #    holds values the current code would never produce and cannot be used
    #    as a sample. Run `calibrate_score_components.py --fresh` to replace
    #    them; it is deterministic and needs no LLM calls.
    #
    # Wide and close to bimodal: value destroyers band at 1.5-3.0, compounders
    # at 8.5-10, with comparatively few names in between.
    "roic_wacc_spread": (6.0, 2.5),
    # Revision breadth spans 2-9 and surprise spans 0-10, but the 57/43 blend
    # of two mid-centred legs pulls the composite in.
    "earnings_momentum": (5.5, 1.5),
    # Inverse of price richness; the one component with a real low tail, since
    # premium-multiple names score genuinely low.
    "valuation": (5.0, 2.0),
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
