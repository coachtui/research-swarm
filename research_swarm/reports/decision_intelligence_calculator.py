"""
Decision intelligence calculator for actionable investment guidance.

Transforms raw analysis data into explicit action recommendations:
- Decision framework (HOLD/ADD/REDUCE for holders, BUY NOW/WAIT/AVOID for buyers)
- Enhanced trade setups (conservative vs aggressive with 3 profit targets)
- Fundamental vs technical divergence detection
- Conviction-linked position sizing with dollar amounts

All calculations are deterministic — no LLM calls, no API calls.
"""
from typing import Dict, Any, Optional
from research_swarm.logger import logger


class DecisionIntelligenceCalculator:
    """Calculates actionable decision intelligence from analysis data."""

    def calculate_decision_framework(
        self,
        rating: str,
        risk_level: str,
        discount_to_target_pct: float,
        moat_score: float,
        conviction_level: str,
        has_divergence: bool,
        fund_tech_divergence: Optional[Dict[str, Any]],
        stop_loss: float,
        current_price: float,
        entry_zone_low: float,
        entry_zone_high: float,
    ) -> Dict[str, Any]:
        """
        Produce explicit guidance for current holders and new buyers.

        Args:
            rating: 5-tier rating (STRONG BUY/BUY/HOLD/SELL/STRONG SELL)
            risk_level: Low/Medium/High
            discount_to_target_pct: % discount to base target (positive = undervalued)
            moat_score: Overall moat score (0-10)
            conviction_level: High/Medium/Low
            has_divergence: Whether signal divergence exists
            fund_tech_divergence: Fundamental vs technical divergence dict (or None)
            stop_loss: Stop loss price from strategy
            current_price: Current stock price
            entry_zone_low: Lower bound of ideal entry zone
            entry_zone_high: Upper bound of ideal entry zone

        Returns:
            Dict with current_holders, new_buyers, and one_liner guidance
        """
        # --- Current holders guidance ---
        if rating in ("STRONG SELL", "SELL"):
            holder_action = "REDUCE"
            trim_pct = "50-75%" if rating == "STRONG SELL" else "30-50%"
            holder_detail = (
                f"Trim {trim_pct} of position to reduce risk. "
                f"Fundamentals deteriorating — lock in remaining value."
            )
            holder_conditions = [
                f"Exit entirely if price breaks below ${stop_loss:.2f}",
                "Re-evaluate if upgrade triggers are met",
            ]
        elif rating in ("STRONG BUY", "BUY") and discount_to_target_pct >= 5:
            holder_action = "ADD"
            holder_detail = (
                f"Add to position on pullbacks to ${entry_zone_low:.2f}-${entry_zone_high:.2f} zone. "
                f"Stock trades {discount_to_target_pct:.0f}% below fair value."
            )
            holder_conditions = [
                f"Maintain stop loss at ${stop_loss:.2f}",
                "Scale in gradually — don't add all at once",
            ]
        elif rating in ("STRONG BUY", "BUY"):
            holder_action = "HOLD"
            holder_detail = (
                f"Maintain position — thesis intact with {rating} rating. "
                f"Near fair value, so adding here offers limited margin of safety."
            )
            holder_conditions = [
                f"Maintain stop loss at ${stop_loss:.2f}",
                "Consider adding only on 5%+ pullback",
            ]
        else:
            holder_action = "HOLD"
            holder_detail = (
                f"Maintain current position. Moat score {moat_score:.1f}/10 "
                f"supports continued ownership but doesn't justify adding."
            )
            holder_conditions = [
                f"Maintain stop loss at ${stop_loss:.2f}",
                "Watch for rating upgrade triggers to add",
            ]

        # --- New buyers guidance ---
        buyer_caveat = None

        if rating in ("SELL", "STRONG SELL"):
            buyer_action = "AVOID"
            buyer_urgency = "N/A"
            buyer_detail = (
                f"Do not initiate position. {rating} rating with "
                f"moat score {moat_score:.1f}/10 indicates unfavorable risk/reward."
            )
        elif discount_to_target_pct >= 15 and conviction_level in ("High", "Medium"):
            buyer_action = "BUY NOW"
            buyer_urgency = "High"
            buyer_detail = (
                f"Significant discount ({discount_to_target_pct:.0f}%) to fair value. "
                f"Enter at current ${current_price:.2f} or set limit near ${entry_zone_high:.2f}."
            )
        elif discount_to_target_pct >= 5 and conviction_level == "High":
            buyer_action = "BUY NOW"
            buyer_urgency = "Medium"
            buyer_detail = (
                f"Moderate discount ({discount_to_target_pct:.0f}%) with high conviction. "
                f"Scale in with initial 50% position at ${current_price:.2f}."
            )
        elif discount_to_target_pct >= 0:
            buyer_action = "SCALE IN"
            buyer_urgency = "Low"
            buyer_detail = (
                f"Near fair value — build position gradually. "
                f"Start with 30% allocation, add on dips to "
                f"${entry_zone_low:.2f}-${entry_zone_high:.2f}."
            )
        else:
            buyer_action = "WAIT"
            buyer_urgency = "Low"
            buyer_detail = (
                f"Trading {abs(discount_to_target_pct):.0f}% above fair value. "
                f"Set alerts for ${entry_zone_high:.2f} (ideal entry zone)."
            )

        # Divergence override: HIGH severity forces WAIT for new buyers
        if fund_tech_divergence and fund_tech_divergence.get("severity") == "HIGH":
            if buyer_action in ("BUY NOW", "SCALE IN"):
                buyer_action = "WAIT"
                buyer_urgency = "Low"
                buyer_caveat = fund_tech_divergence.get("recommendation", "")

        one_liner = f"{rating} | {buyer_action} for new buyers | {holder_action} for holders"

        return {
            "current_holders": {
                "action": holder_action,
                "detail": holder_detail,
                "conditions": holder_conditions,
            },
            "new_buyers": {
                "action": buyer_action,
                "urgency": buyer_urgency,
                "detail": buyer_detail,
                "caveat": buyer_caveat,
            },
            "one_liner": one_liner,
        }

    def calculate_enhanced_trade_setup(
        self,
        current_price: float,
        entry_strategy: Dict[str, Any],
        exit_plan: Dict[str, Any],
        price_targets: Dict[str, Any],
        technical_levels: Dict[str, Any],
        volume_profile_data: Dict[str, Any],
        risk_level: str,
    ) -> Dict[str, Any]:
        """
        Calculate conservative and aggressive trade setups with 3 targets each.

        Args:
            current_price: Current stock price
            entry_strategy: From strategy_calculator (ideal_zone, tranched_buying)
            exit_plan: From strategy_calculator (target_1, target_2, stop_loss)
            price_targets: DCF bull/base/bear from fundamentalist
            technical_levels: From quant entry_exit_signals.key_levels
            volume_profile_data: From quant volume_profile (poc, value_area)
            risk_level: Low/Medium/High

        Returns:
            Dict with conservative and aggressive trade setups
        """
        # Extract available levels with fallbacks
        base_target = price_targets.get("base_target", current_price * 1.15)
        bull_target = price_targets.get("bull_target", current_price * 1.30)

        tech_entry = technical_levels.get("entry")
        tech_stop = technical_levels.get("stop_loss")
        tech_take_profit = technical_levels.get("take_profit")

        poc = volume_profile_data.get("poc")
        val_low = volume_profile_data.get("value_area_low")
        val_high = volume_profile_data.get("value_area_high")

        ideal_low = entry_strategy.get("ideal_zone", {}).get("low", current_price * 0.90)
        ideal_high = entry_strategy.get("ideal_zone", {}).get("high", current_price * 0.95)

        # --- Conservative setup: wait for pullback, wider stops ---
        conservative_entry = self._best_of(
            [tech_entry, val_low, ideal_high],
            fallback=current_price * 0.97,
            prefer="lowest",
        )
        # Ensure conservative entry is at or below current price
        conservative_entry = min(conservative_entry, current_price)

        stop_pct = {"Low": 0.12, "Medium": 0.10, "High": 0.08}.get(risk_level, 0.10)
        conservative_stop = self._best_of(
            [tech_stop, val_low and val_low * 0.97],
            fallback=conservative_entry * (1 - stop_pct),
            prefer="lowest",
        )
        # Stop must be below entry
        conservative_stop = min(conservative_stop, conservative_entry * 0.95)

        # 3 conservative targets (progressively higher)
        conservative_t1 = self._best_of(
            [poc, tech_take_profit, val_high],
            fallback=current_price * 1.07,
            prefer="lowest",
        )
        # T1 must be above entry
        conservative_t1 = max(conservative_t1, conservative_entry * 1.05)

        # T2 must be above T1 (use base_target but ensure it's higher)
        conservative_t2 = max(base_target, conservative_t1 * 1.05)

        # T3 must be above T2 (use bull_target but ensure it's higher)
        conservative_t3 = max(bull_target, conservative_t2 * 1.10)

        # --- Aggressive setup: market entry, tighter stops ---
        aggressive_entry = current_price
        aggressive_stop_pct = {"Low": 0.10, "Medium": 0.08, "High": 0.05}.get(risk_level, 0.08)
        aggressive_stop = current_price * (1 - aggressive_stop_pct)

        # 3 aggressive targets (progressively higher)
        aggressive_t1 = base_target

        # T2 must be above T1
        aggressive_t2 = max(bull_target, aggressive_t1 * 1.07)

        # T3 must be above T2 (10% beyond T2)
        aggressive_t3 = aggressive_t2 * 1.10

        def per_100(entry, target):
            return round(abs(target - entry) * 100, 2)

        def risk_reward(entry, stop, t2):
            loss = entry - stop
            gain = t2 - entry
            if loss > 0:
                return round(gain / loss, 1)
            return 0.0

        return {
            "conservative": {
                "label": "Conservative (Recommended)",
                "entry": round(conservative_entry, 2),
                "stop_loss": round(conservative_stop, 2),
                "targets": [
                    {"price": round(conservative_t1, 2), "sell_pct": 30, "label": "T1 (Near-term)"},
                    {"price": round(conservative_t2, 2), "sell_pct": 40, "label": "T2 (Base case)"},
                    {"price": round(conservative_t3, 2), "sell_pct": 30, "label": "T3 (Bull case)"},
                ],
                "max_loss_per_100": per_100(conservative_entry, conservative_stop),
                "max_gain_per_100": per_100(conservative_entry, conservative_t3),
                "risk_reward": risk_reward(conservative_entry, conservative_stop, conservative_t2),
            },
            "aggressive": {
                "label": "Aggressive (Higher risk)",
                "entry": round(aggressive_entry, 2),
                "stop_loss": round(aggressive_stop, 2),
                "targets": [
                    {"price": round(aggressive_t1, 2), "sell_pct": 33, "label": "T1 (Base case)"},
                    {"price": round(aggressive_t2, 2), "sell_pct": 34, "label": "T2 (Bull case)"},
                    {"price": round(aggressive_t3, 2), "sell_pct": 33, "label": "T3 (Stretch)"},
                ],
                "max_loss_per_100": per_100(aggressive_entry, aggressive_stop),
                "max_gain_per_100": per_100(aggressive_entry, aggressive_t3),
                "risk_reward": risk_reward(aggressive_entry, aggressive_stop, aggressive_t2),
            },
        }

    def detect_fund_tech_divergence(
        self,
        moat_score: float,
        rating: str,
        technical_score: float,
        overall_signal: str,
        signal_confidence: float,
        rsi_value: float,
        macd_signal: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Detect divergence between fundamental rating and technical signals.

        Args:
            moat_score: Overall fundamental moat score (0-10)
            rating: Fundamental rating (STRONG BUY/BUY/HOLD/SELL/STRONG SELL)
            technical_score: Quant technical score (0-10)
            overall_signal: From entry_exit_signals (strong_buy/buy/neutral/sell/strong_sell)
            signal_confidence: Confidence in technical signal (0-1)
            rsi_value: RSI 14 value
            macd_signal: MACD signal (bullish/bearish/neutral)

        Returns:
            None if aligned, or dict with divergence details
        """
        # Map fundamental rating to -2..+2 scale
        fund_map = {
            "STRONG BUY": 2, "BUY": 1, "HOLD": 0, "SELL": -1, "STRONG SELL": -2
        }
        fund_direction = fund_map.get(rating, 0)

        # Map technical signal to -2..+2 scale
        tech_map = {
            "strong_buy": 2, "buy": 1, "neutral": 0, "sell": -1, "strong_sell": -2
        }
        tech_direction = tech_map.get(overall_signal, 0)

        divergence_gap = fund_direction - tech_direction

        # Only flag if gap >= 2 (meaningful divergence)
        if abs(divergence_gap) < 2:
            return None

        severity = "HIGH" if abs(divergence_gap) >= 3 else "MODERATE"

        if divergence_gap > 0:
            # Fundamentals bullish, technicals bearish
            divergence_type = "FUNDAMENTAL_BULLISH_TECH_BEARISH"
            interpretation = (
                f"Fundamentals rate {rating} (moat {moat_score:.1f}/10) but technicals signal "
                f"{overall_signal.upper().replace('_', ' ')} (confidence {signal_confidence:.0%}). "
                f"RSI: {rsi_value:.0f}, MACD: {macd_signal}."
            )
            recommendation = (
                "Wait for technical confirmation before initiating new positions. "
                "The market may be pricing in something fundamentals haven't captured yet, "
                "or this is a contrarian accumulation opportunity as technicals catch up to fundamentals."
            )
            resolution_bias = "Fundamentals usually prevail over 3-6 months"
        else:
            # Technicals bullish, fundamentals bearish
            divergence_type = "TECH_BULLISH_FUNDAMENTAL_BEARISH"
            interpretation = (
                f"Technicals signal {overall_signal.upper().replace('_', ' ')} "
                f"(confidence {signal_confidence:.0%}) but fundamentals rate {rating} "
                f"(moat {moat_score:.1f}/10). RSI: {rsi_value:.0f}, MACD: {macd_signal}."
            )
            recommendation = (
                "Technically driven rally may not be sustainable without fundamental support. "
                "If entering on momentum, use tight stops. "
                "Better suited for short-term traders than long-term investors."
            )
            resolution_bias = "Technical momentum can persist 2-8 weeks before reverting"

        return {
            "has_divergence": True,
            "divergence_type": divergence_type,
            "severity": severity,
            "gap": abs(divergence_gap),
            "fundamental_signal": rating,
            "technical_signal": overall_signal.upper().replace("_", " "),
            "interpretation": interpretation,
            "recommendation": recommendation,
            "resolution_bias": resolution_bias,
        }

    def link_conviction_to_position(
        self,
        conviction_level: str,
        position_sizing: Dict[str, Any],
        risk_level: str,
        moat_score: float,
        rating: str,
    ) -> Dict[str, Any]:
        """
        Tie conviction level to concrete position sizing with dollar examples.

        Args:
            conviction_level: High/Medium/Low from conviction_generator
            position_sizing: From strategy_calculator (recommended_pct, max_pct)
            risk_level: Low/Medium/High
            moat_score: Overall moat score (0-10)
            rating: 5-tier rating

        Returns:
            Dict with adjusted position sizes and dollar amounts
        """
        recommended_pct = position_sizing.get("recommended_pct", 5.0)
        max_pct = position_sizing.get("max_pct", 7.5)

        # Apply conviction multiplier
        multiplier = {"High": 1.0, "Medium": 0.7, "Low": 0.4}.get(conviction_level, 0.7)
        adjusted_pct = round(recommended_pct * multiplier, 1)
        adjusted_max = round(max_pct * multiplier, 1)

        # Dollar examples for $100K portfolio
        dollar_per_100k = round(adjusted_pct * 1000, 0)

        # Build conviction justification
        justification = self._build_conviction_justification(
            conviction_level, moat_score, rating, risk_level
        )

        return {
            "conviction_level": conviction_level,
            "conviction_score": {"High": "8-10", "Medium": "5-7", "Low": "1-4"}.get(
                conviction_level, "5-7"
            ),
            "recommended_pct": adjusted_pct,
            "max_pct": adjusted_max,
            "dollar_per_100k": dollar_per_100k,
            "rationale": position_sizing.get("rationale", ""),
            "conviction_justification": justification,
        }

    def calculate_all(
        self,
        current_price: float,
        rating: str,
        risk_level: str,
        moat_score: float,
        conviction_level: str,
        discount_to_target_pct: float,
        entry_strategy: Dict[str, Any],
        exit_plan: Dict[str, Any],
        position_sizing: Dict[str, Any],
        price_targets: Dict[str, Any],
        technical_indicators: Dict[str, Any],
        signal_breakdown: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Calculate all decision intelligence components.

        Calls functions in correct dependency order:
        1. detect_fund_tech_divergence (needed by decision_framework)
        2. calculate_decision_framework
        3. calculate_enhanced_trade_setup
        4. link_conviction_to_position

        Args:
            current_price: Current stock price
            rating: 5-tier fundamental rating
            risk_level: Low/Medium/High
            moat_score: Overall moat score (0-10)
            conviction_level: High/Medium/Low
            discount_to_target_pct: % discount to base target
            entry_strategy: From strategy_calculator
            exit_plan: From strategy_calculator
            position_sizing: From strategy_calculator
            price_targets: DCF bull/base/bear from fundamentalist
            technical_indicators: Full quant technical_indicators dict
            signal_breakdown: Signal divergence data from news analysis

        Returns:
            Dict with all four decision intelligence components
        """
        # Extract quant technical data
        entry_exit = technical_indicators.get("entry_exit_signals", {})
        volume_profile = technical_indicators.get("volume_profile", {})
        rsi = technical_indicators.get("rsi", {})
        macd = technical_indicators.get("macd", {})

        # 1. Detect fundamental vs technical divergence
        fund_tech_divergence = None
        try:
            overall_signal = entry_exit.get("overall_signal", "neutral")
            fund_tech_divergence = self.detect_fund_tech_divergence(
                moat_score=moat_score,
                rating=rating,
                technical_score=entry_exit.get("confidence", 0.5) * 10,
                overall_signal=overall_signal,
                signal_confidence=entry_exit.get("confidence", 0.5),
                rsi_value=rsi.get("rsi_14", 50),
                macd_signal=macd.get("macd_signal", "neutral"),
            )
        except Exception as e:
            logger.warning(f"Fund-tech divergence detection failed: {e}")

        # 2. Decision framework
        has_signal_divergence = (
            signal_breakdown.get("has_divergence", False) if signal_breakdown else False
        )
        stop_loss = exit_plan.get("stop_loss", current_price * 0.90)
        entry_zone_low = entry_strategy.get("ideal_zone", {}).get("low", current_price * 0.90)
        entry_zone_high = entry_strategy.get("ideal_zone", {}).get("high", current_price * 0.95)

        decision_framework = None
        try:
            decision_framework = self.calculate_decision_framework(
                rating=rating,
                risk_level=risk_level,
                discount_to_target_pct=discount_to_target_pct,
                moat_score=moat_score,
                conviction_level=conviction_level,
                has_divergence=has_signal_divergence,
                fund_tech_divergence=fund_tech_divergence,
                stop_loss=stop_loss,
                current_price=current_price,
                entry_zone_low=entry_zone_low,
                entry_zone_high=entry_zone_high,
            )
        except Exception as e:
            logger.warning(f"Decision framework calculation failed: {e}")

        # 3. Enhanced trade setup
        enhanced_trade_setup = None
        try:
            tech_levels = entry_exit.get("key_levels", {})
            enhanced_trade_setup = self.calculate_enhanced_trade_setup(
                current_price=current_price,
                entry_strategy=entry_strategy,
                exit_plan=exit_plan,
                price_targets=price_targets,
                technical_levels=tech_levels,
                volume_profile_data=volume_profile,
                risk_level=risk_level,
            )
        except Exception as e:
            logger.warning(f"Enhanced trade setup calculation failed: {e}")

        # 4. Conviction-position link
        conviction_position = None
        try:
            conviction_position = self.link_conviction_to_position(
                conviction_level=conviction_level,
                position_sizing=position_sizing,
                risk_level=risk_level,
                moat_score=moat_score,
                rating=rating,
            )
        except Exception as e:
            logger.warning(f"Conviction-position link failed: {e}")

        return {
            "decision_framework": decision_framework,
            "enhanced_trade_setup": enhanced_trade_setup,
            "fund_tech_divergence": fund_tech_divergence,
            "conviction_position": conviction_position,
        }

    # --- Private helpers ---

    @staticmethod
    def _best_of(
        candidates: list,
        fallback: float,
        prefer: str = "lowest",
    ) -> float:
        """Pick the best available price level from candidates, ignoring None."""
        valid = [c for c in candidates if c is not None and c > 0]
        if not valid:
            return fallback
        return min(valid) if prefer == "lowest" else max(valid)

    @staticmethod
    def _build_conviction_justification(
        conviction_level: str,
        moat_score: float,
        rating: str,
        risk_level: str,
    ) -> str:
        """Build a human-readable conviction justification."""
        parts = []

        if conviction_level == "High":
            parts.append(f"Strong signal alignment supports high conviction")
        elif conviction_level == "Medium":
            parts.append(f"Mixed signals warrant moderate conviction")
        else:
            parts.append(f"Significant uncertainty limits conviction")

        if moat_score >= 8.0:
            parts.append(f"exceptional moat ({moat_score:.1f}/10)")
        elif moat_score >= 6.5:
            parts.append(f"solid moat ({moat_score:.1f}/10)")
        elif moat_score >= 5.0:
            parts.append(f"average moat ({moat_score:.1f}/10)")
        else:
            parts.append(f"weak moat ({moat_score:.1f}/10)")

        if risk_level == "High":
            parts.append("elevated risk profile")
        elif risk_level == "Low":
            parts.append("favorable risk profile")

        return ". ".join(parts[:2]) + "."


# Global singleton
decision_intelligence_calculator = DecisionIntelligenceCalculator()
