"""
Fair Value Divergence Analysis Layer.

Maintains strict separation between two fundamentally different quantities:

  Internal Fair Value  — DVRG's structural intrinsic valuation estimate.
                         Derived from blended P/E, EV/EBITDA, and DCF applied to
                         reported fundamentals. Measures economic worth.

  Analyst Consensus Target — Forward market expectation proxy.
                         Sell-side mean price target. Measures where professional
                         market participants expect the stock to trade in 12 months.

These are NOT averaged or blended. The layer computes divergence_ratio between
them, classifies the regime, and flags model stability anomalies.  Fair value
and price targets are NEVER modified.

Three divergence regimes:
  Consensus Validated ✓      |ratio - 1| <= ALIGNED_THRESHOLD
  Model-Conservative Regime  ratio < 1 - ALIGNED_THRESHOLD  (FV << consensus)
  Model-Driven Upside        ratio > 1 + ALIGNED_THRESHOLD  (FV >> consensus)

Stability warning (separate from regime):
  Triggered when model output is anomalous vs current market price or when
  internal valuation methods disagree heavily — NOT a recalibration signal,
  just a data quality flag.
"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from research_swarm.logger import logger


class FairValueCalibration(BaseModel):
    """
    Divergence analysis metadata produced by the calibration layer.

    The internal fair value and all price targets are UNTOUCHED.
    This model only carries the analysis of how they relate to consensus.
    """

    # Regime classification (by forward revenue growth)
    regime: str = Field(..., description="Growth | Stable | Value/Turnaround")
    regime_rev_growth_pct: float = Field(..., description="Forward revenue growth used for classification (%)")

    # Internal model output — unchanged, for display reference
    internal_fair_value: float = Field(
        ...,
        description="fair_value_mid from DVRG blended model. This value is never modified."
    )
    internal_method_dispersion_pct: Optional[float] = Field(
        None,
        description="Spread across internal valuation methods (P/E, EV/EBITDA, DCF). "
                    "High dispersion indicates method disagreement."
    )

    # Analyst consensus target (market expectation proxy)
    consensus_target: Optional[float] = Field(
        None,
        description="Analyst mean price target — forward market expectation proxy. "
                    "Conceptually distinct from intrinsic fair value."
    )
    num_analysts: Optional[int] = Field(None, description="Number of analyst estimates in consensus")

    # Divergence analysis
    divergence_ratio: Optional[float] = Field(
        None,
        description="internal_fair_value / consensus_target. "
                    "<0.80: model conservative, >1.20: model-driven upside, else aligned."
    )
    divergence_pct: Optional[float] = Field(
        None,
        description="(internal_fair_value - consensus_target) / consensus_target × 100. Signed."
    )
    divergence_state: str = Field(
        ...,
        description="Consensus Validated ✓ | Model-Conservative Regime | "
                    "Model-Driven Upside Scenario | No Consensus Data"
    )

    # Anomaly guardrail — separate from regime classification
    model_stability_warning: bool = Field(
        False,
        description="True when model output appears anomalous. Does NOT trigger recalibration. "
                    "Signals data quality review is warranted."
    )
    stability_warning_reasons: List[str] = Field(
        default_factory=list,
        description="Specific anomaly conditions detected (e.g., extreme price deviation, high internal dispersion)"
    )

    # Audit
    qa_flags: List[str] = Field(default_factory=list, description="Human-readable flags for admin review")

    # Display
    display_label: str = Field(..., description="Label shown in UI chip")


class FairValueCalibrator:
    """
    Computes divergence between DVRG intrinsic fair value and analyst consensus target.

    Does NOT modify PriceTargetScenarios. Fair value and scenario targets are the
    outputs of the valuation model and must remain economically pure.
    """

    # Divergence band for "aligned" classification
    # Wider than typical because intrinsic value and 12-month price targets are
    # legitimately different measures — some gap is expected even when both are correct.
    ALIGNED_THRESHOLD = 0.20            # ±20%: within this → Consensus Validated

    # Anomaly guardrail thresholds (configurable)
    # These detect likely model input errors, not valuation disagreements.
    PRICE_DEVIATION_WARNING = 0.70      # flag if |FV / market_price - 1| > 70% (mid/small-cap default)
    DISPERSION_WARNING = 50.0           # flag if internal method spread > 50%

    # Scale-aware deviation caps — large-cap equity price structure is far more
    # institutionally anchored over multi-year windows.  Intrinsic values that
    # deviate beyond observed institutional bands almost always indicate input
    # data issues rather than genuine fundamental mispricing at scale.
    #   Mega-cap  (≥$50B):  ±40%  — tightly-held, deep analyst coverage
    #   Large-cap (≥$10B):  ±50%  — broad coverage, mean-reversion priced in
    #   Mid/small-cap:      ±70%  — wider valuation dispersion is expected
    MEGA_CAP_THRESHOLD  = 50_000_000_000   # $50B market cap
    LARGE_CAP_THRESHOLD = 10_000_000_000   # $10B market cap
    MEGA_CAP_DEVIATION  = 0.40
    LARGE_CAP_DEVIATION = 0.50

    def calibrate(
        self,
        blended_result: Any,            # PriceTargetScenarios (read-only)
        current_price: float,
        stock_info: Optional[Dict[str, Any]],
        valuation_metrics: Optional[Dict[str, Any]],
        analyst_target_data: Optional[Dict[str, Any]],
    ) -> Optional[FairValueCalibration]:
        """
        Analyse divergence between internal fair value and analyst consensus target.

        Returns FairValueCalibration metadata, or None if the blended result is
        invalid (should not happen in practice).

        IMPORTANT: blended_result is never mutated.
        """
        try:
            stock_info = stock_info or {}
            valuation_metrics = valuation_metrics or {}
            analyst_target_data = analyst_target_data or {}

            internal_fv = float(blended_result.fair_value_mid)
            if internal_fv <= 0:
                return None

            # 0. Market-cap scale (used for scale-aware stability guardrail)
            market_cap: Optional[float] = None
            try:
                mc = stock_info.get("marketCap")
                if mc is not None:
                    market_cap = float(mc)
            except (TypeError, ValueError):
                pass

            # 1. Regime classification
            rev_growth = stock_info.get("revenueGrowth") or 0.0
            rev_growth_pct = float(rev_growth) * 100.0          # yfinance returns decimal
            regime = self._classify_regime(rev_growth_pct)

            # 2. Internal method dispersion (from blended model, already computed)
            internal_dispersion: Optional[float] = None
            try:
                d = getattr(blended_result, "valuation_dispersion_pct", None)
                if d is not None:
                    internal_dispersion = float(d)
            except (TypeError, ValueError):
                pass

            # 3. Analyst consensus target — the ONLY market expectation proxy
            consensus_target: Optional[float] = None
            num_analysts: Optional[int] = None
            try:
                raw = analyst_target_data.get("target_mean")
                n = analyst_target_data.get("num_analysts")
                if raw and float(raw) > 0:
                    consensus_target = round(float(raw), 2)
                if n is not None:
                    num_analysts = int(n)
            except (TypeError, ValueError, AttributeError):
                pass

            # 4. Divergence analysis (only meaningful if consensus is available)
            divergence_ratio: Optional[float] = None
            divergence_pct: Optional[float] = None
            divergence_state: str = "No Consensus Data"

            if consensus_target and consensus_target > 0:
                divergence_ratio = round(internal_fv / consensus_target, 4)
                divergence_pct = round((internal_fv - consensus_target) / consensus_target * 100.0, 1)
                divergence_state = self._classify_divergence(divergence_ratio)

            # 5. Anomaly guardrail — independent of divergence classification
            stability_warning, warning_reasons = self._check_stability(
                internal_fv=internal_fv,
                current_price=current_price,
                internal_dispersion=internal_dispersion,
                ticker=stock_info.get("symbol", "UNKNOWN"),
                market_cap=market_cap,
            )

            # 6. QA flags
            qa_flags: List[str] = []
            ticker = stock_info.get("symbol") or valuation_metrics.get("ticker", "UNKNOWN")
            if divergence_state == "Model-Conservative Regime":
                qa_flags.append(
                    f"{ticker}: Model-Conservative Regime — FV ${internal_fv:.2f} is "
                    f"{abs(divergence_pct or 0):.1f}% below analyst consensus "
                    f"${consensus_target:.2f}. Intrinsic value below market expectation."
                )
            elif divergence_state == "Model-Driven Upside Scenario":
                qa_flags.append(
                    f"{ticker}: Model-Driven Upside — FV ${internal_fv:.2f} is "
                    f"{divergence_pct or 0:.1f}% above analyst consensus "
                    f"${consensus_target:.2f}. Contrarian signal, verify assumptions."
                )
            if stability_warning:
                for r in warning_reasons:
                    qa_flags.append(f"{ticker}: STABILITY WARNING — {r}")

            display_label = self._display_label(divergence_state, stability_warning)

            return FairValueCalibration(
                regime=regime,
                regime_rev_growth_pct=round(rev_growth_pct, 1),
                internal_fair_value=round(internal_fv, 2),
                internal_method_dispersion_pct=round(internal_dispersion, 1) if internal_dispersion is not None else None,
                consensus_target=consensus_target,
                num_analysts=num_analysts,
                divergence_ratio=divergence_ratio,
                divergence_pct=divergence_pct,
                divergence_state=divergence_state,
                model_stability_warning=stability_warning,
                stability_warning_reasons=warning_reasons,
                qa_flags=qa_flags,
                display_label=display_label,
            )

        except Exception as e:
            logger.warning(f"FairValueCalibrator failed (non-fatal): {e}")
            return None

    # ------------------------------------------------------------------ helpers

    def _classify_regime(self, rev_growth_pct: float) -> str:
        if rev_growth_pct > 20.0:
            return "Growth"
        elif rev_growth_pct >= 5.0:
            return "Stable"
        else:
            return "Value/Turnaround"

    def _classify_divergence(self, ratio: float) -> str:
        lower = 1.0 - self.ALIGNED_THRESHOLD
        upper = 1.0 + self.ALIGNED_THRESHOLD
        if ratio < lower:
            return "Model-Conservative Regime"
        elif ratio > upper:
            return "Model-Driven Upside Scenario"
        else:
            return "Consensus Validated ✓"

    def _scale_deviation_cap(self, market_cap: Optional[float]) -> tuple[float, str]:
        """
        Return (threshold, scale_label) for the price-deviation stability check.

        Thresholds are tighter for large-cap equities because their multi-year
        price structure is institutionally anchored — extreme deviations from
        current price almost always reflect input data quality issues, not
        genuine fundamental mispricing at that scale.
        """
        if market_cap is None:
            return self.PRICE_DEVIATION_WARNING, "general"
        if market_cap >= self.MEGA_CAP_THRESHOLD:
            return self.MEGA_CAP_DEVIATION, "mega-cap"
        if market_cap >= self.LARGE_CAP_THRESHOLD:
            return self.LARGE_CAP_DEVIATION, "large-cap"
        return self.PRICE_DEVIATION_WARNING, "general"

    def _check_stability(
        self,
        internal_fv: float,
        current_price: float,
        internal_dispersion: Optional[float],
        ticker: str,
        market_cap: Optional[float] = None,
    ) -> tuple[bool, List[str]]:
        """
        Detect anomalous model outputs that suggest input data errors, not just
        valuation disagreement. Returns (warning_flag, reasons_list).

        For large-cap and mega-cap equities a tighter scale-aware threshold is
        applied because intrinsic values inconsistent with observed institutional
        price bands almost always indicate bad input data rather than legitimate
        multi-year re-rating opportunity.
        """
        reasons: List[str] = []

        if current_price > 0:
            price_deviation = abs(internal_fv / current_price - 1.0)
            cap_threshold, scale_label = self._scale_deviation_cap(market_cap)
            if price_deviation > cap_threshold:
                direction = "below" if internal_fv < current_price else "above"
                scale_note = (
                    f" Institutional deviation band for {scale_label} equities: ±{cap_threshold * 100:.0f}%."
                    if scale_label != "general" else ""
                )
                reasons.append(
                    f"Fair value ${internal_fv:.2f} is {price_deviation * 100:.0f}% "
                    f"{direction} current market price ${current_price:.2f}.{scale_note} "
                    f"Verify input data quality."
                )

        if internal_dispersion is not None and internal_dispersion > self.DISPERSION_WARNING:
            reasons.append(
                f"Internal valuation methods disagree by {internal_dispersion:.0f}% "
                f"(P/E, EV/EBITDA, DCF produce widely divergent estimates). "
                f"Model output may be unreliable."
            )

        return bool(reasons), reasons

    def _display_label(self, divergence_state: str, stability_warning: bool) -> str:
        if stability_warning:
            return "⚠ Model Stability Warning"
        return divergence_state


# Module-level singleton
fair_value_calibrator = FairValueCalibrator()
