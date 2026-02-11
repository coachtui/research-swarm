"""
Valuation sensitivity calculator for the Fundamentalist agent.

Calculates price sensitivity to:
- EPS changes (±10%, ±5%, base)
- P/E multiple changes (±2x, ±1x, base)
"""
from typing import Dict, Any, Optional
from research_swarm.logger import logger


class SensitivityCalculator:
    """Calculates valuation sensitivity to EPS and P/E changes."""

    def calculate_sensitivity_matrix(
        self,
        base_eps: float,
        base_pe: float,
        current_price: float,
        valuation_metrics: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Calculate price sensitivity matrix to EPS and P/E changes.

        Sensitivity Analysis:
        - EPS Sensitivity: -10%, -5%, 0%, +5%, +10%
        - P/E Multiple Sensitivity: -2x, -1x, 0x, +1x, +2x

        Args:
            base_eps: Base case EPS estimate (next 12 months)
            base_pe: Base case P/E multiple
            current_price: Current stock price
            valuation_metrics: Optional dict with forward_pe, peg_ratio, etc.

        Returns:
            Dict with eps_sensitivity, pe_sensitivity, most_likely_outcome, confidence_level
        """
        if not base_eps or not base_pe or not current_price:
            logger.warning("Insufficient data for sensitivity analysis, returning defaults")
            return self._default_sensitivity()

        # Ensure positive values
        if base_eps <= 0 or base_pe <= 0 or current_price <= 0:
            logger.warning(f"Invalid inputs: EPS={base_eps}, PE={base_pe}, Price={current_price}")
            return self._default_sensitivity()

        # Calculate EPS sensitivity
        eps_changes = [-0.10, -0.05, 0.0, 0.05, 0.10]
        eps_sensitivity = {}

        for change in eps_changes:
            adjusted_eps = base_eps * (1 + change)
            price = adjusted_eps * base_pe
            upside = ((price - current_price) / current_price) * 100

            label = f"{change:+.0%}"
            eps_sensitivity[label] = {
                "eps": round(adjusted_eps, 2),
                "price": round(price, 2),
                "upside_pct": round(upside, 1)
            }

        # Calculate P/E multiple sensitivity
        pe_changes = [-2, -1, 0, 1, 2]
        pe_sensitivity = {}

        for change in pe_changes:
            adjusted_pe = base_pe + change
            if adjusted_pe <= 0:
                continue  # Skip negative P/E multiples

            price = base_eps * adjusted_pe
            upside = ((price - current_price) / current_price) * 100

            label = f"{change:+d}x"
            pe_sensitivity[label] = {
                "pe": round(adjusted_pe, 1),
                "price": round(price, 2),
                "upside_pct": round(upside, 1)
            }

        # Most likely outcome (base case)
        base_price = base_eps * base_pe
        base_upside = ((base_price - current_price) / current_price) * 100

        most_likely_outcome = {
            "eps": round(base_eps, 2),
            "pe": round(base_pe, 1),
            "price": round(base_price, 2),
            "upside_pct": round(base_upside, 1)
        }

        # Determine confidence level
        confidence_level = self._assess_confidence(
            base_eps, base_pe, current_price, valuation_metrics
        )

        return {
            "eps_sensitivity": eps_sensitivity,
            "pe_sensitivity": pe_sensitivity,
            "most_likely_outcome": most_likely_outcome,
            "confidence_level": confidence_level,
            "base_inputs": {
                "base_eps": round(base_eps, 2),
                "base_pe": round(base_pe, 1),
                "current_price": round(current_price, 2)
            }
        }

    def _assess_confidence(
        self,
        base_eps: float,
        base_pe: float,
        current_price: float,
        valuation_metrics: Optional[Dict[str, Any]]
    ) -> str:
        """
        Assess confidence in the valuation sensitivity analysis.

        High confidence: Low PEG (<1.5), reasonable P/E, stable fundamentals
        Medium confidence: Moderate metrics
        Low confidence: High uncertainty, volatile metrics

        Args:
            base_eps: Base EPS estimate
            base_pe: Base P/E multiple
            current_price: Current price
            valuation_metrics: Optional valuation metrics

        Returns:
            "High" | "Medium" | "Low"
        """
        confidence_factors = []

        # Factor 1: PEG ratio (if available)
        if valuation_metrics:
            peg = valuation_metrics.get("peg_ratio")
            if peg:
                if 0.5 <= peg <= 1.5:
                    confidence_factors.append(1)  # Good PEG = higher confidence
                elif peg > 2.5:
                    confidence_factors.append(-1)  # High PEG = lower confidence
                else:
                    confidence_factors.append(0)  # Moderate PEG = neutral

        # Factor 2: P/E multiple reasonableness
        if 10 <= base_pe <= 30:
            confidence_factors.append(1)  # Reasonable P/E = higher confidence
        elif base_pe > 50 or base_pe < 5:
            confidence_factors.append(-1)  # Extreme P/E = lower confidence
        else:
            confidence_factors.append(0)  # Moderate P/E = neutral

        # Factor 3: Price vs intrinsic value alignment
        implied_value = base_eps * base_pe
        deviation = abs((implied_value - current_price) / current_price)

        if deviation < 0.15:  # Within 15%
            confidence_factors.append(1)  # Close alignment = higher confidence
        elif deviation > 0.50:  # More than 50% deviation
            confidence_factors.append(-1)  # Large deviation = lower confidence
        else:
            confidence_factors.append(0)  # Moderate deviation = neutral

        # Calculate confidence score
        confidence_score = sum(confidence_factors)

        if confidence_score >= 2:
            return "High"
        elif confidence_score <= -2:
            return "Low"
        else:
            return "Medium"

    def _default_sensitivity(self) -> Dict[str, Any]:
        """Return default sensitivity when data is insufficient."""
        return {
            "eps_sensitivity": {},
            "pe_sensitivity": {},
            "most_likely_outcome": {
                "eps": 0.0,
                "pe": 0.0,
                "price": 0.0,
                "upside_pct": 0.0
            },
            "confidence_level": "Low",
            "base_inputs": {
                "base_eps": 0.0,
                "base_pe": 0.0,
                "current_price": 0.0
            },
            "error": "Insufficient data for sensitivity analysis"
        }


# Global calculator instance
sensitivity_calculator = SensitivityCalculator()
