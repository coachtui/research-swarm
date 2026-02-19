"""
Strategy calculator for investment recommendations.

Calculates entry/exit strategies, position sizing, and risk/reward analysis
based on technical levels, valuation targets, and risk assessment.
"""
from typing import Dict, Any, Optional, Tuple
from research_swarm.logger import logger


def _to_price_zone(price: float, zone_width_pct: float = 0.02) -> Tuple[float, float]:
    """
    Convert a single price estimate to a volatility-aware zone.

    Prevents false precision: $228.16 → $223–$233 (±2% band).
    Width is intentionally modest; callers can widen for ATR-driven contexts.
    """
    half = price * zone_width_pct
    return round(price - half, 2), round(price + half, 2)


class StrategyCalculator:
    """Calculates investment strategy recommendations."""

    def calculate_entry_strategy(
        self,
        current_price: float,
        valuation_targets: Dict[str, Any],
        technical_levels: Optional[Dict[str, Any]] = None,
        risk_level: str = "Medium",
        conviction: float = 0.7
    ) -> Dict[str, Any]:
        """
        Calculate entry strategy based on current price vs targets.

        Logic:
        - If price < base_target: Buy now
        - If price near base_target (±5%): Scale in
        - If price > base_target: Wait for pullback

        Args:
            current_price: Current stock price
            valuation_targets: Dict with base_target, bull_target, bear_target
            technical_levels: Optional dict with support/resistance levels
            risk_level: Low/Medium/High
            conviction: Analysis confidence (0-1)

        Returns:
            Dict with entry strategy, ideal zones, and tranched buying plan
        """
        if not current_price or not valuation_targets:
            return self._default_entry_strategy()

        base_target = valuation_targets.get("base_target", current_price)
        bear_target = valuation_targets.get("bear_target", current_price * 0.85)

        # Determine recommendation
        discount_pct = ((base_target - current_price) / base_target) * 100

        # Calculate ideal entry zone based on current price position
        # CRITICAL: ideal_zone should be at or BELOW current price for new buyers
        if current_price < bear_target:
            # Stock is trading below bear case - ideal zone is around current price
            ideal_low = current_price * 0.92   # 8% below current (on deeper dip)
            ideal_high = current_price * 0.97  # 3% below current (slight pullback)
        elif current_price < base_target:
            # Stock is between bear and base - ideal zone is below current
            ideal_low = bear_target
            ideal_high = min(base_target * 0.95, current_price * 0.97)  # 5% below base OR 3% below current
        else:
            # Stock is above base target - ideal zone is the bear-to-base range
            ideal_low = bear_target
            ideal_high = base_target * 0.95  # 5% below base target

        if discount_pct >= 15:
            recommendation = "Price Below Intrinsic Value Band — Risk/Reward Favorable"
            entry_methodology = (
                f"Entry zone derived from intrinsic value discount band. "
                f"Current price is {discount_pct:.1f}% below base-case fair value — "
                "risk/reward meets minimum threshold. Zone anchored at ±3% around current price."
            )
        elif discount_pct >= 5:
            recommendation = "Price Approaching Intrinsic Value Zone — Moderate Discount"
            entry_methodology = (
                f"Entry zone derived from bear-to-base range. "
                f"Current price is {discount_pct:.1f}% below base case (${base_target:.2f}). "
                f"Ideal entry: bear scenario (${bear_target:.2f}) to base ×95%."
            )
        elif discount_pct >= -5:
            recommendation = "Price Within Intrinsic Value Band — Scale In"
            entry_methodology = (
                "Entry zone reflects current trading range — price is near intrinsic value midpoint. "
                "Scale-in approach appropriate; avoid large single-tranche entry at full valuation."
            )
        elif discount_pct >= -15:
            recommendation = "Price Above Intrinsic Value Band — Await Pullback"
            entry_methodology = (
                f"Entry zone derived from bear-to-base discount range. "
                f"Current price trades {abs(discount_pct):.1f}% above base case (${base_target:.2f}). "
                f"Ideal zone: ${ideal_low:.2f}–${ideal_high:.2f} represents reversion toward intrinsic value."
            )
        else:
            recommendation = "Price Above Intrinsic Value Band — Risk/Reward Unfavorable"
            entry_methodology = (
                f"Price significantly elevated vs intrinsic value. "
                f"Entry zone (${ideal_low:.2f}–${ideal_high:.2f}) requires meaningful pullback. "
                "Derived from bear scenario floor as minimum acceptable discount."
            )

        # Calculate tranched buying plan
        if discount_pct >= 0:  # At or below fair value
            # Aggressive entry
            initial_percent = 50
            add_percent = 30
            final_percent = 20

            initial_price = current_price * 0.98  # 2% below current
            add_price = current_price * 0.92  # 8% below current (if it dips)
            final_price = current_price * 0.88  # 12% below current (deep dip)
        else:  # Above fair value
            # Conservative entry - wait for pullback
            initial_percent = 30
            add_percent = 40
            final_percent = 30

            initial_price = ideal_high  # Wait for pullback to ideal high
            add_price = (ideal_high + ideal_low) / 2  # Mid-range
            final_price = ideal_low  # Best price

        # P2: Precision normalization — express entry as a zone, not a point
        entry_zone_low, entry_zone_high = _to_price_zone(
            (ideal_low + ideal_high) / 2, zone_width_pct=0.015
        )

        return {
            "preferred_entry_zone": {
                "low": round(ideal_low, 2),
                "high": round(ideal_high, 2),
                "label": "Preferred Entry Zone: Low–Mid Band"
            },
            # Keep ideal_zone for backward-compatibility with downstream consumers
            "ideal_zone": {
                "low": round(ideal_low, 2),
                "high": round(ideal_high, 2)
            },
            # P2: Normalized zone (replaces single-point display)
            "entry_zone_display": {
                "low": entry_zone_low,
                "high": entry_zone_high,
                "label": f"${entry_zone_low}–${entry_zone_high}"
            },
            # P1: Provenance label — every displayed price maps to a methodology
            "entry_methodology": entry_methodology,
            "current_price": round(current_price, 2),
            "discount_to_target_pct": round(discount_pct, 1),
            "recommendation": recommendation,
            "tranched_buying": {
                "initial_percent": initial_percent,
                "initial_price": round(initial_price, 2),
                "add_percent": add_percent,
                "add_price": round(add_price, 2),
                "final_percent": final_percent,
                "final_price": round(final_price, 2),
                "rationale": f"{'Aggressive' if discount_pct >= 0 else 'Conservative'} entry based on intrinsic value estimate"
            }
        }

    def calculate_position_sizing(
        self,
        risk_level: str,
        conviction: float,
        moat_score: float,
        rating: str = "HOLD"
    ) -> Dict[str, Any]:
        """
        Calculate recommended position sizing.

        Logic:
        - Base size on risk level (Low=10%, Medium=5-7%, High=2-3%)
        - Adjust for conviction (high conviction = larger position)
        - Adjust for rating strength

        Args:
            risk_level: Low/Medium/High
            conviction: Analysis confidence (0-1)
            moat_score: Overall moat score (0-10)
            rating: STRONG BUY/BUY/HOLD/SELL/STRONG SELL

        Returns:
            Dict with recommended and max position sizes with rationale
        """
        # Base sizing by risk level
        if risk_level == "Low":
            base_size = 8.0
            max_size = 12.0
        elif risk_level == "High":
            base_size = 2.5
            max_size = 4.0
        else:  # Medium
            base_size = 5.0
            max_size = 7.5

        # Adjust for conviction (±30%)
        conviction_multiplier = 0.7 + (conviction * 0.6)  # Range: 0.7 to 1.3
        recommended = base_size * conviction_multiplier

        # Adjust for rating strength
        if rating == "STRONG BUY":
            recommended *= 1.2
            max_size *= 1.2
        elif rating == "SELL" or rating == "STRONG SELL":
            recommended *= 0.5
            max_size *= 0.5

        # Cap at reasonable limits
        recommended = min(recommended, 15.0)
        max_size = min(max_size, 20.0)

        # Generate rationale
        rationale_parts = []

        if risk_level == "Low":
            rationale_parts.append("Low risk profile allows larger position")
        elif risk_level == "High":
            rationale_parts.append("High risk requires smaller position")
        else:
            rationale_parts.append("Moderate risk suggests balanced position")

        if conviction > 0.8:
            rationale_parts.append("high conviction in analysis")
        elif conviction < 0.6:
            rationale_parts.append("lower conviction suggests caution")

        if moat_score >= 8.0:
            rationale_parts.append("strong moat supports larger allocation")

        rationale = "; ".join(rationale_parts)

        return {
            "recommended_pct": round(recommended, 1),
            "max_pct": round(max_size, 1),
            "rationale": rationale.capitalize()
        }

    def calculate_exit_plan(
        self,
        current_price: float,
        price_targets: Dict[str, Any],
        risk_level: str = "Medium",
        technical_resistance: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Calculate exit strategy with targets and stop loss.

        Logic:
        - Target 1: Base case target (sell 50%)
        - Target 2: Bull case target (sell remaining 50%)
        - Stop loss: Based on risk level (Low=20%, Medium=15%, High=10%)
        - Trailing stop: 15-20% from peak

        Args:
            current_price: Current stock price
            price_targets: Dict with base_target, bull_target
            risk_level: Low/Medium/High
            technical_resistance: Optional resistance level

        Returns:
            Dict with exit targets, stop loss, trailing stop, risk/reward
        """
        if not current_price or not price_targets:
            return self._default_exit_plan()

        base_target = price_targets.get("base_target", current_price * 1.15)
        bull_target = price_targets.get("bull_target", current_price * 1.30)
        bear_target = price_targets.get("bear_target", current_price * 0.85)

        # Target 1: Intrinsic value midpoint reached (sell 50%)
        target_1_price = base_target
        target_1_percent = 50
        target_1_rationale = "Price reached intrinsic value midpoint — reduce position, reassess thesis"

        # Target 2: Upside scenario (sell remaining)
        target_2_price = bull_target
        target_2_percent = 50
        target_2_rationale = "Price reached upside scenario — exit remaining position"

        # Stop loss based on risk level
        if risk_level == "Low":
            stop_loss_pct = 20  # Can afford larger drawdown
        elif risk_level == "High":
            stop_loss_pct = 10  # Tight stop for high risk
        else:
            stop_loss_pct = 15  # Standard stop

        stop_loss = current_price * (1 - stop_loss_pct / 100)

        # P0: Stop ≤ Bear constraint — stop must not exceed bear case
        stop_quality = "ALIGNED"
        stop_alignment_note = ""
        if bear_target > 0 and stop_loss > bear_target:
            # Stop is above bear case — logically inconsistent: triggers before bear plays out
            stop_loss = round(bear_target * 0.97, 2)
            stop_quality = "ADJUSTED"
            stop_alignment_note = (
                f"Stop adjusted to ${stop_loss:.2f} — original stop exceeded bear case "
                f"(${bear_target:.2f}), which would trigger exit before the downside scenario "
                "fully played out. Re-anchored 3% below bear case threshold."
            )
        elif bear_target > 0 and stop_loss < bear_target * 0.80:
            stop_quality = "WIDE"
            gap_pct = ((bear_target - stop_loss) / bear_target) * 100
            stop_alignment_note = (
                f"Stop (${stop_loss:.2f}) is {gap_pct:.0f}% below bear case "
                f"(${bear_target:.2f}). Allows for temporary breach of bear scenario — "
                "appropriate only for long-horizon conviction positions."
            )
        else:
            if bear_target > 0:
                gap_pct = ((bear_target - stop_loss) / bear_target) * 100
                stop_alignment_note = (
                    f"Stop structurally aligned — positioned {gap_pct:.0f}% below bear case "
                    f"(${bear_target:.2f})."
                )
            else:
                stop_alignment_note = f"Stop derived from {stop_loss_pct}% risk-level rule."

        # P1: Stop provenance label
        stop_methodology = (
            f"Stop derived from {risk_level.lower()} risk profile: {stop_loss_pct}% below entry price. "
            "Rule: Low risk = 20% (wider tolerance), Medium = 15% (standard), High = 10% (tight). "
            f"Bear case constraint applied: stop ≤ ${bear_target:.2f}."
        )

        # P2: Precision normalization — express stop as a zone, not a point
        stop_zone_low, stop_zone_high = _to_price_zone(stop_loss, zone_width_pct=0.015)

        # Trailing stop
        trailing_stop_pct = 15
        trailing_stop = f"{trailing_stop_pct}% trailing stop from peak"

        # Calculate risk/reward
        avg_target = (target_1_price + target_2_price) / 2
        potential_gain = avg_target - current_price
        potential_loss = current_price - stop_loss

        if potential_loss > 0:
            risk_reward_ratio = potential_gain / potential_loss
        else:
            risk_reward_ratio = 0.0

        # Expected holding period based on targets
        upside_pct = ((base_target - current_price) / current_price) * 100

        if upside_pct > 30:
            holding_period = "12-18 months"
        elif upside_pct > 15:
            holding_period = "6-12 months"
        elif upside_pct > 5:
            holding_period = "3-6 months"
        else:
            holding_period = "Hold - reassess in 3 months"

        # Calculate expected returns
        expected_return_total = ((avg_target - current_price) / current_price) * 100

        # Simple annualized return (assume 12-month holding period)
        if holding_period.startswith("12-18"):
            months = 15
        elif holding_period.startswith("6-12"):
            months = 9
        elif holding_period.startswith("3-6"):
            months = 4.5
        else:
            months = 12

        expected_return_annualized = (expected_return_total / months) * 12

        return {
            "target_1": {
                "price": round(target_1_price, 2),
                "percent": target_1_percent,
                "rationale": target_1_rationale
            },
            "target_2": {
                "price": round(target_2_price, 2),
                "percent": target_2_percent,
                "rationale": target_2_rationale
            },
            "stop_loss": round(stop_loss, 2),
            "stop_loss_pct": stop_loss_pct,
            # P0: Stop/bear alignment
            "stop_quality": stop_quality,
            "stop_alignment_note": stop_alignment_note,
            # P1: Stop provenance
            "stop_methodology": stop_methodology,
            # P2: Stop zone (precision normalization)
            "stop_zone": {
                "low": stop_zone_low,
                "high": stop_zone_high,
                "label": f"${stop_zone_low}–${stop_zone_high}"
            },
            "trailing_stop": trailing_stop,
            "risk_reward_ratio": round(risk_reward_ratio, 1),
            "holding_period": holding_period,
            "expected_return_total": round(expected_return_total, 1),
            "expected_return_annualized": round(expected_return_annualized, 1)
        }

    def calculate_full_strategy(
        self,
        current_price: float,
        valuation_targets: Dict[str, Any],
        risk_level: str,
        conviction: float,
        moat_score: float,
        rating: str,
        technical_levels: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Calculate complete investment strategy.

        Combines entry, position sizing, and exit strategies.

        Args:
            current_price: Current stock price
            valuation_targets: Price target scenarios
            risk_level: Low/Medium/High
            conviction: Analysis confidence (0-1)
            moat_score: Overall moat score (0-10)
            rating: 5-tier rating
            technical_levels: Optional technical support/resistance

        Returns:
            Complete strategy dict with entry, position_sizing, and exit
        """
        entry = self.calculate_entry_strategy(
            current_price=current_price,
            valuation_targets=valuation_targets,
            technical_levels=technical_levels,
            risk_level=risk_level,
            conviction=conviction
        )

        position_sizing = self.calculate_position_sizing(
            risk_level=risk_level,
            conviction=conviction,
            moat_score=moat_score,
            rating=rating
        )

        exit = self.calculate_exit_plan(
            current_price=current_price,
            price_targets=valuation_targets,
            risk_level=risk_level,
            technical_resistance=technical_levels.get("resistance") if technical_levels else None
        )

        return {
            "entry": entry,
            "position_sizing": position_sizing,
            "exit": exit
        }

    def _default_entry_strategy(self) -> Dict[str, Any]:
        """Return default entry strategy when data insufficient."""
        return {
            "preferred_entry_zone": {"low": 0.0, "high": 0.0, "label": "Preferred Entry Zone: Low–Mid Band"},
            "ideal_zone": {"low": 0.0, "high": 0.0},
            "current_price": 0.0,
            "discount_to_target_pct": 0.0,
            "recommendation": "Insufficient data for entry strategy",
            "tranched_buying": {
                "initial_percent": 0,
                "initial_price": 0.0,
                "add_percent": 0,
                "add_price": 0.0,
                "final_percent": 0,
                "final_price": 0.0,
                "rationale": "No data"
            }
        }

    def _default_exit_plan(self) -> Dict[str, Any]:
        """Return default exit plan when data insufficient."""
        return {
            "target_1": {"price": 0.0, "percent": 50, "rationale": "No data"},
            "target_2": {"price": 0.0, "percent": 50, "rationale": "No data"},
            "stop_loss": 0.0,
            "stop_loss_pct": 15,
            "trailing_stop": "15% from peak",
            "risk_reward_ratio": 0.0,
            "holding_period": "Unknown",
            "expected_return_total": 0.0,
            "expected_return_annualized": 0.0
        }


# Global calculator instance
strategy_calculator = StrategyCalculator()
