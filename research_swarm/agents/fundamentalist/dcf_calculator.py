"""
DCF (Discounted Cash Flow) valuation calculator.

Pure Python math — zero LLM cost. Uses DCFInputs extracted by EnhancedFilingParser.
Produces PriceTargetScenarios with bull/base/bear cases.

Improvements:
- WACC uses real market cap for equity weight (not synthetic 3x debt estimate)
- FCF growth = Revenue Growth × Margin Stability Factor (not naive revenue growth proxy)
"""
import statistics
from typing import Optional, List
from research_swarm.logger import logger
from research_swarm.agents.fundamentalist.models import DCFInputs, PriceTargetScenarios


class DCFCalculator:
    """Calculates intrinsic value using DCF methodology."""

    def calculate_dcf(
        self,
        dcf_inputs: DCFInputs,
        current_price: float
    ) -> Optional[PriceTargetScenarios]:
        """
        Run 3-scenario DCF model.

        Args:
            dcf_inputs: Extracted from filing via EnhancedFilingParser
            current_price: Current stock price from yfinance

        Returns:
            PriceTargetScenarios with bull/base/bear cases, or None if insufficient data
        """
        # Validate minimum required inputs
        if not dcf_inputs.fcf_history or not dcf_inputs.shares_outstanding:
            logger.warning("Insufficient data for DCF: need fcf_history and shares_outstanding")
            return None

        if dcf_inputs.shares_outstanding <= 0:
            logger.warning("Invalid shares_outstanding for DCF")
            return None

        base_fcf = dcf_inputs.fcf_history[-1]  # Most recent FCF
        if base_fcf <= 0:
            # Try average of positive FCFs
            positive_fcfs = [f for f in dcf_inputs.fcf_history if f > 0]
            if not positive_fcfs:
                logger.warning("No positive FCF history for DCF")
                return None
            base_fcf = sum(positive_fcfs) / len(positive_fcfs)

        # Calculate WACC
        wacc = self._calculate_wacc(dcf_inputs)

        # Revenue growth anchor (clamped)
        revenue_growth = (dcf_inputs.revenue_growth_rate or 10.0) / 100.0
        revenue_growth = max(0.02, min(revenue_growth, 0.35))

        # IMPROVEMENT: Apply margin stability factor — FCF growth != revenue growth
        # When margins are volatile or contracting, FCF grows slower than revenue
        margin_stability = self._calculate_margin_stability_factor(dcf_inputs)
        base_growth = revenue_growth * margin_stability
        base_growth = max(0.02, min(base_growth, 0.35))

        logger.info(
            f"DCF growth: {base_growth:.1%} "
            f"(revenue={revenue_growth:.1%} × margin_stability={margin_stability:.2f})"
        )

        terminal_growth = 0.025  # 2.5% long-term GDP growth

        # Cash and debt for equity bridge
        cash = dcf_inputs.cash_and_equivalents or 0
        debt = dcf_inputs.total_debt or 0
        shares = dcf_inputs.shares_outstanding

        try:
            # === BASE CASE (50% probability) ===
            base_fcfs = self._project_fcf(base_fcf, base_growth, years=5, decay=0.85)
            base_tv = self._calculate_terminal_value(base_fcfs[-1], wacc, terminal_growth)
            base_ev = self._discount_to_present(base_fcfs, base_tv, wacc)
            base_value = self._per_share_value(base_ev, cash, debt, shares)

            # === BULL CASE (25% probability) ===
            bull_growth = min(base_growth + 0.03, 0.40)
            bull_fcfs = self._project_fcf(base_fcf * 1.05, bull_growth, years=5, decay=0.85)
            bull_tv = self._calculate_terminal_value(bull_fcfs[-1], wacc - 0.005, terminal_growth)
            bull_ev = self._discount_to_present(bull_fcfs, bull_tv, wacc - 0.005)
            bull_value = self._per_share_value(bull_ev, cash, debt, shares)

            # === BEAR CASE (25% probability) ===
            bear_growth = max(base_growth - 0.05, 0.0)
            bear_fcfs = self._project_fcf(base_fcf * 0.90, bear_growth, years=5, decay=0.80)
            bear_tv = self._calculate_terminal_value(bear_fcfs[-1], wacc + 0.01, terminal_growth)
            bear_ev = self._discount_to_present(bear_fcfs, bear_tv, wacc + 0.01)
            bear_value = self._per_share_value(bear_ev, cash, debt, shares)

            # Ensure values are positive and ordered
            base_value = max(base_value, 0.01)
            bull_value = max(bull_value, base_value * 1.1)
            bear_value = max(min(bear_value, base_value * 0.9), 0.01)

            # Build scenario descriptions
            margin_note = ""
            if dcf_inputs.operating_margin_trend:
                margin_note = f", margins {dcf_inputs.operating_margin_trend}"

            base_assumptions = (
                f"FCF growth: {base_growth*100:.1f}%/yr declining to {terminal_growth*100:.1f}%, "
                f"WACC: {wacc*100:.1f}% (margin stability: {margin_stability:.2f}){margin_note}"
            )
            bull_assumptions = (
                f"FCF growth: {bull_growth*100:.1f}%/yr with margin expansion, "
                f"lower WACC: {(wacc-0.005)*100:.1f}%"
            )
            bear_assumptions = (
                f"FCF growth: {bear_growth*100:.1f}%/yr with margin contraction, "
                f"higher WACC: {(wacc+0.01)*100:.1f}%"
            )

            result = PriceTargetScenarios(
                base_target=round(base_value, 2),
                base_assumptions=base_assumptions,
                base_probability=0.50,
                bull_target=round(bull_value, 2),
                bull_assumptions=bull_assumptions,
                bull_probability=0.25,
                bear_target=round(bear_value, 2),
                bear_assumptions=bear_assumptions,
                bear_probability=0.25,
                methodology="DCF (5-year projection + terminal value)"
            )

            upside = ((result.expected_value() - current_price) / current_price) * 100
            logger.success(
                f"✓ DCF complete: Base=${base_value:.2f} Bull=${bull_value:.2f} Bear=${bear_value:.2f} "
                f"(EV=${result.expected_value():.2f}, {upside:+.1f}% vs ${current_price:.2f})"
            )
            return result

        except Exception as e:
            logger.error(f"Error calculating DCF: {e}")
            return None

    def _calculate_wacc(self, dcf_inputs: DCFInputs) -> float:
        """
        Calculate Weighted Average Cost of Capital.

        WACC = (E/V * Re) + (D/V * Rd * (1-T))

        IMPROVEMENT: Uses real market cap for equity weight when available,
        instead of synthetic 3x debt proxy which biases WACC for leveraged companies.
        """
        beta = dcf_inputs.beta or 1.0
        risk_free = dcf_inputs.risk_free_rate / 100.0
        erp = dcf_inputs.equity_risk_premium / 100.0
        tax_rate = (dcf_inputs.effective_tax_rate or 21.0) / 100.0

        # Cost of equity: CAPM
        cost_of_equity = risk_free + beta * erp

        # Estimate cost of debt (~risk-free + 1.5-3% spread)
        cost_of_debt = risk_free + 0.02

        # Capital structure weights
        debt = dcf_inputs.total_debt or 0

        # IMPROVEMENT: Use real market cap if available, else fall back to synthetic proxy
        if dcf_inputs.market_cap_millions and dcf_inputs.market_cap_millions > 0:
            equity = dcf_inputs.market_cap_millions * 1_000_000  # millions → actual dollars
            logger.debug(f"WACC using real market cap: ${equity/1e9:.1f}B equity, ${debt/1e9:.1f}B debt")
        else:
            # Fallback: 3x debt proxy or $1B minimum
            equity = max(debt * 3, 1_000_000_000)
            logger.debug(f"WACC using synthetic equity proxy: ${equity/1e9:.1f}B")

        total_capital = equity + debt
        equity_weight = equity / total_capital
        debt_weight = debt / total_capital

        wacc = (equity_weight * cost_of_equity) + (debt_weight * cost_of_debt * (1 - tax_rate))

        # Clamp WACC to reasonable range (5-20%)
        wacc = max(0.05, min(wacc, 0.20))

        return wacc

    def _calculate_margin_stability_factor(self, dcf_inputs: DCFInputs) -> float:
        """
        Calculate margin stability factor (0.50 - 1.00).

        This translates revenue growth into FCF growth:
          FCF_Growth = Revenue_Growth × Margin_Stability_Factor

        Stable/expanding margins → FCF tracks revenue growth (~1.0)
        Volatile/contracting margins → FCF grows slower (~0.50-0.70)
        """
        # Base factor from operating margin trend
        trend = dcf_inputs.operating_margin_trend
        if trend == "expanding":
            base_factor = 1.0
        elif trend == "stable":
            base_factor = 0.85
        elif trend == "contracting":
            base_factor = 0.65
        else:
            base_factor = 0.80  # Default: moderate translation

        # Refine with margin history if available (more data → more precision)
        if dcf_inputs.operating_margin_history and len(dcf_inputs.operating_margin_history) >= 3:
            valid_margins = [m for m in dcf_inputs.operating_margin_history if m is not None]
            if len(valid_margins) >= 3:
                margin_std = statistics.stdev(valid_margins)
                # High margin volatility → cyclical → FCF less predictable
                if margin_std > 5.0:
                    base_factor = max(0.50, base_factor - 0.20)
                elif margin_std > 2.5:
                    base_factor = max(0.60, base_factor - 0.10)
                logger.debug(f"Margin history std dev: {margin_std:.1f}% → stability factor: {base_factor:.2f}")

        return round(base_factor, 2)

    def _project_fcf(
        self,
        base_fcf: float,
        growth_rate: float,
        years: int = 5,
        decay: float = 0.85
    ) -> List[float]:
        """
        Project FCF for N years with growth rate decay.

        Growth decays toward terminal rate each year:
        Year 1: base * (1 + growth)
        Year 2: prev * (1 + growth * decay)
        Year 3: prev * (1 + growth * decay^2)
        """
        fcfs = []
        current_fcf = base_fcf
        current_growth = growth_rate

        for year in range(years):
            current_fcf = current_fcf * (1 + current_growth)
            fcfs.append(current_fcf)
            current_growth = current_growth * decay  # Decay growth toward terminal

        return fcfs

    def _calculate_terminal_value(
        self,
        final_fcf: float,
        wacc: float,
        terminal_growth: float = 0.025
    ) -> float:
        """
        Calculate terminal value using Gordon Growth Model.

        TV = FCF * (1 + g) / (WACC - g)
        """
        if wacc <= terminal_growth:
            # WACC must exceed terminal growth; adjust if needed
            wacc = terminal_growth + 0.02

        return final_fcf * (1 + terminal_growth) / (wacc - terminal_growth)

    def _discount_to_present(
        self,
        cash_flows: List[float],
        terminal_value: float,
        wacc: float
    ) -> float:
        """Discount all future cash flows to present value."""
        pv = 0.0
        for i, cf in enumerate(cash_flows):
            pv += cf / (1 + wacc) ** (i + 1)

        # Discount terminal value from end of projection period
        pv += terminal_value / (1 + wacc) ** len(cash_flows)

        return pv

    def _per_share_value(
        self,
        enterprise_value: float,
        cash: float,
        debt: float,
        shares: float
    ) -> float:
        """
        Calculate equity value per share.

        Equity = Enterprise Value + Cash - Debt
        Per Share = Equity / Shares Outstanding
        """
        equity_value = enterprise_value + cash - debt
        if shares <= 0:
            return 0.0
        return equity_value / shares


# Global instance
dcf_calculator = DCFCalculator()
