"""
Blended valuation calculator using multiple methodologies.

Combines P/E multiples, EV/EBITDA multiples, and DCF with proper sanity checks.
"""
from typing import Optional, Dict, Any
from research_swarm.logger import logger
from research_swarm.agents.fundamentalist.models import PriceTargetScenarios, DCFInputs


class BlendedValuationCalculator:
    """
    Calculates fair value using a blended methodology:
    - Forward P/E Multiple (50% weight)
    - EV/EBITDA Multiple (30% weight)
    - DCF Sanity Check (20% weight)

    With sanity gates to prevent misleading valuations.
    """

    def calculate_fair_value(
        self,
        ticker: str,
        current_price: float,
        valuation_metrics: Dict[str, Any],
        dcf_inputs: Optional[DCFInputs] = None,
        stock_info: Optional[Any] = None
    ) -> Optional[PriceTargetScenarios]:
        """
        Calculate fair value using blended methodology.

        Args:
            ticker: Stock ticker
            current_price: Current market price
            valuation_metrics: Valuation metrics from market_data_client.get_valuation_metrics()
            dcf_inputs: Optional DCF inputs for sanity check
            stock_info: Optional yfinance Ticker.info dict for additional data

        Returns:
            PriceTargetScenarios with bull/base/bear cases, or None if insufficient data
        """
        if not valuation_metrics:
            logger.warning(f"No valuation metrics available for {ticker}")
            return None

        # Extract market cap and determine if mega-cap
        market_cap_millions = valuation_metrics.get("market_cap_millions", 0)
        market_cap = market_cap_millions * 1_000_000 if market_cap_millions else 0
        is_mega_cap = market_cap > 50_000_000_000  # $50B threshold

        # Extract key valuation multiples
        pe_ratio = valuation_metrics.get("pe_ratio")  # Current trailing P/E
        ev_ebitda = valuation_metrics.get("ev_ebitda")  # Current EV/EBITDA

        # Get sector median multiples from valuation_metrics
        sector_pe = valuation_metrics.get("sector_avg_pe", 18.0)
        sector_ev_ebitda = valuation_metrics.get("sector_avg_ev_ebitda", 12.0)

        # Extract additional data for calculations
        enterprise_value_millions = valuation_metrics.get("enterprise_value_millions")

        # Get TTM EPS, EBITDA, shares, debt, cash from stock_info if available
        ttm_eps = None
        ebitda = None
        shares_outstanding = None
        total_debt = 0
        cash = 0

        if stock_info:
            ttm_eps = stock_info.get("trailingEps")
            ebitda = stock_info.get("ebitda")
            shares_outstanding = stock_info.get("sharesOutstanding")
            total_debt = stock_info.get("totalDebt", 0)
            cash = stock_info.get("cash", 0)

        # If TTM EPS not in stock_info, calculate from market cap and P/E
        if not ttm_eps and pe_ratio and market_cap_millions:
            ttm_eps = current_price / pe_ratio if pe_ratio else None

        logger.info(f"Fair value calculation for {ticker}: market_cap=${market_cap/1e9:.1f}B, "
                   f"sector_pe={sector_pe:.1f}x, sector_ev_ebitda={sector_ev_ebitda:.1f}x")

        # Calculate three fair value estimates
        fv_pe = self._calculate_pe_fair_value(ttm_eps, sector_pe, current_price)
        fv_ev_ebitda = self._calculate_ev_ebitda_fair_value(
            ebitda, enterprise_value_millions, sector_ev_ebitda,
            total_debt, cash, shares_outstanding
        )
        fv_dcf = self._calculate_dcf_fair_value(dcf_inputs, current_price) if dcf_inputs else None

        # Blend the estimates
        base_target = self._blend_estimates(fv_pe, fv_ev_ebitda, fv_dcf)

        if base_target is None:
            logger.warning(f"Insufficient data for blended valuation of {ticker}")
            return None

        # Apply sanity gate
        sanity_threshold = 0.30 if is_mega_cap else 0.40
        deviation = abs(base_target - current_price) / current_price

        if deviation > sanity_threshold:
            logger.warning(
                f"Fair value ${base_target:.2f} deviates {deviation:.0%} from current price ${current_price:.2f} "
                f"(threshold: {sanity_threshold:.0%} for {'mega-cap' if is_mega_cap else 'standard'} stock)"
            )

            # For mega-caps with extreme deviations, flag high valuation uncertainty
            if is_mega_cap and deviation > 0.40:
                logger.warning(f"High Valuation Uncertainty flagged for {ticker}")
                # Return targets that reflect uncertainty rather than misleading precision
                return self._create_uncertainty_scenarios(current_price)

            # Recalculate using alternative methodology (average of current price and calculated FV)
            logger.info("Recalculating with alternative methodology (blend with market price)")
            base_target = (base_target + current_price) / 2

        # Create bull/base/bear scenarios
        return self._create_scenarios(
            base_target=base_target,
            current_price=current_price,
            sector_pe=sector_pe,
            ttm_eps=ttm_eps,
            methodology_used=self._get_methodology_description(fv_pe, fv_ev_ebitda, fv_dcf)
        )

    def _calculate_pe_fair_value(
        self,
        ttm_eps: Optional[float],
        sector_pe: float,
        current_price: float
    ) -> Optional[float]:
        """Calculate fair value using P/E multiple methodology (50% weight)."""
        if not ttm_eps or ttm_eps <= 0:
            logger.debug("No valid TTM EPS for P/E valuation")
            return None

        fair_value = ttm_eps * sector_pe
        logger.info(f"P/E fair value: ${fair_value:.2f} (TTM EPS ${ttm_eps:.2f} × {sector_pe:.1f}x sector P/E)")
        return fair_value

    def _calculate_ev_ebitda_fair_value(
        self,
        ebitda: Optional[float],
        enterprise_value_millions: Optional[float],
        sector_ev_ebitda: float,
        total_debt: float,
        cash: float,
        shares_outstanding: Optional[float]
    ) -> Optional[float]:
        """Calculate fair value using EV/EBITDA multiple methodology (30% weight)."""
        # If we have current enterprise value, we can derive EBITDA
        if enterprise_value_millions and sector_ev_ebitda and not ebitda:
            # Assume current EV is fairly valued, derive EBITDA
            # Then apply sector multiple
            logger.debug("Deriving EBITDA from current EV/EBITDA")
            return None  # Skip EV/EBITDA method if we don't have direct EBITDA

        if not ebitda or ebitda <= 0 or not shares_outstanding or shares_outstanding <= 0:
            logger.debug("No valid EBITDA or shares outstanding for EV/EBITDA valuation")
            return None

        # Calculate implied enterprise value at sector multiple
        # EBITDA should be in actual dollars, not millions
        implied_ev_millions = (ebitda / 1_000_000) * sector_ev_ebitda

        # Back-calculate equity value per share
        # debt and cash should also be in actual dollars
        equity_value_millions = implied_ev_millions - (total_debt / 1_000_000) + (cash / 1_000_000)
        equity_value = equity_value_millions * 1_000_000
        fair_value_per_share = equity_value / shares_outstanding

        logger.info(f"EV/EBITDA fair value: ${fair_value_per_share:.2f} "
                   f"(EBITDA ${ebitda/1e6:.0f}M × {sector_ev_ebitda:.1f}x)")
        return fair_value_per_share

    def _calculate_dcf_fair_value(
        self,
        dcf_inputs: DCFInputs,
        current_price: float
    ) -> Optional[float]:
        """Calculate DCF-based fair value (20% weight - sanity check only)."""
        from research_swarm.agents.fundamentalist.dcf_calculator import dcf_calculator

        try:
            dcf_result = dcf_calculator.calculate_dcf(dcf_inputs, current_price)
            if dcf_result:
                logger.info(f"DCF fair value: ${dcf_result.base_target:.2f}")
                return dcf_result.base_target
        except Exception as e:
            logger.debug(f"DCF calculation failed: {e}")

        return None

    def _blend_estimates(
        self,
        fv_pe: Optional[float],
        fv_ev_ebitda: Optional[float],
        fv_dcf: Optional[float]
    ) -> Optional[float]:
        """
        Blend fair value estimates using weighted average.

        Weights (if all available):
        - P/E: 50%
        - EV/EBITDA: 30%
        - DCF: 20%

        If some methods unavailable, reweight remaining methods proportionally.
        """
        estimates = []
        weights = []

        if fv_pe is not None and fv_pe > 0:
            estimates.append(fv_pe)
            weights.append(0.50)

        if fv_ev_ebitda is not None and fv_ev_ebitda > 0:
            estimates.append(fv_ev_ebitda)
            weights.append(0.30)

        if fv_dcf is not None and fv_dcf > 0:
            estimates.append(fv_dcf)
            weights.append(0.20)

        if not estimates:
            return None

        # Normalize weights
        total_weight = sum(weights)
        normalized_weights = [w / total_weight for w in weights]

        # Calculate weighted average
        blended = sum(est * wgt for est, wgt in zip(estimates, normalized_weights))

        methods_used = []
        if fv_pe: methods_used.append(f"P/E")
        if fv_ev_ebitda: methods_used.append(f"EV/EBITDA")
        if fv_dcf: methods_used.append(f"DCF")

        logger.info(f"Blended fair value: ${blended:.2f} (using {', '.join(methods_used)})")
        return blended

    def _create_scenarios(
        self,
        base_target: float,
        current_price: float,
        sector_pe: float,
        ttm_eps: Optional[float],
        methodology_used: str
    ) -> PriceTargetScenarios:
        """Create bull/base/bear scenarios from base target."""
        # Bull case: +15% from base (strong growth scenario)
        bull_target = base_target * 1.15

        # Bear case: -15% from base (risk scenario)
        bear_target = base_target * 0.85

        # Ensure ordering
        bull_target = max(bull_target, base_target * 1.05)
        bear_target = min(bear_target, base_target * 0.95)

        base_assumptions = (
            f"Fair value of ${base_target:.2f} assumes {sector_pe:.1f}x forward P/E "
            f"based on sector median"
            + (f", applied to ${ttm_eps:.2f} TTM EPS" if ttm_eps else "")
            + f". {methodology_used}"
        )

        bull_assumptions = (
            f"Bull case assumes multiple expansion to {sector_pe*1.1:.1f}x P/E "
            "with margin improvement and market share gains"
        )

        bear_assumptions = (
            f"Bear case assumes multiple compression to {sector_pe*0.9:.1f}x P/E "
            "with competitive pressures or margin headwinds"
        )

        return PriceTargetScenarios(
            base_target=round(base_target, 2),
            base_assumptions=base_assumptions,
            base_probability=0.50,
            bull_target=round(bull_target, 2),
            bull_assumptions=bull_assumptions,
            bull_probability=0.25,
            bear_target=round(bear_target, 2),
            bear_assumptions=bear_assumptions,
            bear_probability=0.25,
            methodology=methodology_used
        )

    def _create_uncertainty_scenarios(self, current_price: float) -> PriceTargetScenarios:
        """Create scenarios when valuation uncertainty is too high."""
        # Use current price ±10% to reflect high uncertainty
        return PriceTargetScenarios(
            base_target=round(current_price, 2),
            base_assumptions="High Valuation Uncertainty — calculated fair value deviated >40% from market price. Using market price as base case.",
            base_probability=0.50,
            bull_target=round(current_price * 1.10, 2),
            bull_assumptions="Bull case: +10% from current price",
            bull_probability=0.25,
            bear_target=round(current_price * 0.90, 2),
            bear_assumptions="Bear case: -10% from current price",
            bear_probability=0.25,
            methodology="Market Price (High Uncertainty)"
        )

    def _get_methodology_description(
        self,
        fv_pe: Optional[float],
        fv_ev_ebitda: Optional[float],
        fv_dcf: Optional[float]
    ) -> str:
        """Generate description of methodology used."""
        methods = []
        if fv_pe: methods.append("P/E Multiple (50%)")
        if fv_ev_ebitda: methods.append("EV/EBITDA (30%)")
        if fv_dcf: methods.append("DCF Sanity Check (20%)")

        if len(methods) == 3:
            return "Blended: " + ", ".join(methods)
        elif len(methods) == 2:
            return "Blended: " + " + ".join(methods) + " (reweighted)"
        elif len(methods) == 1:
            return methods[0] + " only"
        else:
            return "Insufficient data"

    def _get_default_sector_pe(self, sector: str) -> float:
        """Get default P/E multiple by sector."""
        defaults = {
            "technology": 22.0,
            "industrials": 18.0,
            "financials": 15.0,
            "energy": 16.0,
            "healthcare": 20.0,
            "consumer": 19.0,
            "utilities": 17.0,
            "real estate": 19.0,
            "materials": 16.0,
            "communication": 21.0
        }

        for key, pe in defaults.items():
            if key in sector:
                return pe

        return 18.0  # Default

    def _get_default_sector_ev_ebitda(self, sector: str) -> float:
        """Get default EV/EBITDA multiple by sector."""
        defaults = {
            "technology": 15.0,
            "industrials": 11.0,
            "financials": 10.0,
            "energy": 9.0,
            "healthcare": 13.0,
            "consumer": 12.0,
            "utilities": 10.0,
            "real estate": 14.0,
            "materials": 10.0,
            "communication": 13.0
        }

        for key, ev_ebitda in defaults.items():
            if key in sector:
                return ev_ebitda

        return 12.0  # Default


# Global instance
blended_valuation_calculator = BlendedValuationCalculator()
