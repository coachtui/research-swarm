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
        signal_breakdown: Optional[Dict[str, Any]] = None,
        value_area_high: Optional[float] = None,
        value_area_low: Optional[float] = None,
        bb_upper: Optional[float] = None,
        regime_mode: Optional[str] = None,
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
            # MOMENTUM regime: stock is technically extended above intrinsic value.
            # Surface specific trim levels so holders have an actionable risk management posture.
            if regime_mode == "MOMENTUM" and (value_area_high or bb_upper):
                holder_detail = (
                    f"Thesis intact but technically extended. "
                    f"Risk management posture recommended."
                )
                holder_conditions = []
                if value_area_high:
                    holder_conditions.append(
                        f"Consider trimming 15–20% of position above ${value_area_high:.0f} "
                        f"(Value Area High) into strength"
                    )
                if bb_upper:
                    holder_conditions.append(
                        f"Upper Bollinger Band (${bb_upper:.0f}) represents secondary trim target "
                        f"if momentum continues"
                    )
                holder_conditions.append(
                    f"Maintain core position with hard stop at ${stop_loss:.0f}"
                )
                holder_conditions.append(
                    f"Do not add to position at current levels — wait for pullback to "
                    f"${entry_zone_low:.0f}–${entry_zone_high:.0f} preferred entry zone"
                )
            else:
                holder_detail = (
                    f"Maintain current position. Moat score {moat_score:.1f}/10 "
                    f"supports continued ownership but doesn't justify adding at current signal levels."
                )
                holder_conditions = [
                    f"Maintain hard stop at ${stop_loss:.2f}",
                    "No additions until support holds on volume and signals align",
                    "Watch for rating upgrade triggers before adding",
                ]

        # --- New buyers guidance ---
        buyer_caveat = None

        # C1: Buy limit validation — a buy limit for pullback entry must always be BELOW current price.
        # If the computed entry_zone_low >= current_price (degenerate zone), fall back to 85% of current.
        _buy_limit = entry_zone_low if entry_zone_low < current_price else round(current_price * 0.85, 2)

        if rating in ("SELL", "STRONG SELL"):
            buyer_action = "AVOID"
            buyer_urgency = "N/A"
            buyer_detail = (
                f"Do not initiate position. {rating} rating with "
                f"moat score {moat_score:.1f}/10 indicates unfavorable risk/reward."
            )
        elif rating == "HOLD":
            # HOLD = mixed signals — cap new buyer action at SCALE IN regardless of discount.
            # A deeply discounted HOLD is an opportunity to build gradually, not to rush in.
            if discount_to_target_pct >= 5:
                buyer_action = "SCALE IN"
                buyer_urgency = "Low"
                buyer_detail = (
                    f"Discount of {discount_to_target_pct:.0f}% to fair value, but mixed signals "
                    f"warrant a patient, staged approach. Initiate cautiously only at support "
                    f"(${_buy_limit:.2f} zone) — no more than 10-15% of intended position "
                    f"until thesis confirms through signal alignment or price reclaim above ${entry_zone_high:.2f}."
                )
            elif discount_to_target_pct >= 0:
                buyer_action = "WAIT"
                buyer_urgency = "Low"
                buyer_detail = (
                    f"Near fair value with mixed signals — no compelling entry here. "
                    f"Wait for either a pullback to ${_buy_limit:.2f} or clearer signal alignment "
                    f"before initiating a position."
                )
            else:
                buyer_action = "WAIT"
                buyer_urgency = "Low"
                buyer_detail = (
                    f"Trading {abs(discount_to_target_pct):.0f}% above fair value with mixed signals. "
                    f"Wait for pullback to ${entry_zone_high:.2f} before considering entry."
                )
        elif discount_to_target_pct >= 15 and conviction_level in ("High", "Medium"):
            buyer_action = "BUY NOW"
            buyer_urgency = "High"
            buyer_detail = (
                f"Significant discount ({discount_to_target_pct:.0f}%) to fair value. "
                f"Enter at current ${current_price:.2f} (market order for immediate entry) or set a buy limit at "
                f"${_buy_limit:.2f} to get an even better entry if the stock dips further."
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
                f"${_buy_limit:.2f}–${entry_zone_high:.2f}."
            )
        else:
            buyer_action = "WAIT"
            buyer_urgency = "Low"
            buyer_detail = (
                f"Trading {abs(discount_to_target_pct):.0f}% above fair value. "
                f"Wait for pullback to ${entry_zone_high:.2f} (ideal entry zone). "
                f"Set a buy limit at ${_buy_limit:.2f} to automatically enter if price dips to attractive levels."
            )

        # Divergence override: HIGH severity forces WAIT for new buyers
        if fund_tech_divergence and fund_tech_divergence.get("severity") == "HIGH":
            if buyer_action in ("BUY NOW", "SCALE IN"):
                buyer_action = "WAIT"
                buyer_urgency = "Low"
                buyer_caveat = fund_tech_divergence.get("recommendation", "")

        # Market regime overlay: when macro signals are Risk-Off + Contraction/Stress,
        # downgrade holder ADD → HOLD (don't add into active institutional selling)
        regime_caveat = None
        if signal_breakdown:
            overall_sig = signal_breakdown.get("overall_score", 5.0)
            institutional_sig = signal_breakdown.get("institutional_score", 5.0)
            dark_pool_sig = signal_breakdown.get("dark_pool_score", 5.0)
            signal_spread_val = signal_breakdown.get("signal_spread", 0.0)

            is_risk_off = overall_sig < 4.0
            is_contraction = (institutional_sig + dark_pool_sig) / 2 < 4.2
            is_stress = signal_spread_val >= 3.5

            if is_risk_off and (is_contraction or is_stress):
                regime_parts = ["Risk-Off signal environment"]
                if is_contraction:
                    regime_parts.append("institutional selling (Contraction)")
                if is_stress:
                    regime_parts.append("high signal divergence (Stress)")
                regime_desc = ", ".join(regime_parts)

                # Downgrade ADD → HOLD for current holders
                if holder_action == "ADD":
                    holder_action = "HOLD"
                    holder_detail = (
                        f"Hold current position — the underlying thesis remains intact ({rating} rating), "
                        f"but the current market regime shows {regime_desc}. "
                        f"Adding into active selling pressure reduces risk/reward. "
                        f"Resume adding when market regime stabilizes."
                    )
                    holder_conditions = [
                        f"Maintain stop loss at ${stop_loss:.2f}",
                        "Resume adding when market regime shifts to Risk-On or Neutral",
                        "Monitor institutional flow for accumulation signal",
                    ]
                    regime_caveat = regime_desc

                # Warn buyers about unfavorable macro backdrop
                if buyer_action in ("BUY NOW", "SCALE IN") and not buyer_caveat:
                    buyer_caveat = (
                        f"Market regime is currently {regime_desc} — "
                        f"consider waiting for stabilization before initiating new positions."
                    )

        one_liner = self._build_clean_one_liner(rating, buyer_action, holder_action)
        action_subtext = self._build_action_subtext(
            rating, buyer_action, holder_action,
            entry_zone_low, entry_zone_high, _buy_limit, stop_loss,
            value_area_high=value_area_high,
            value_area_low=value_area_low,
            regime_mode=regime_mode,
        )

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
            "action_subtext": action_subtext,
            "regime_caveat": regime_caveat,
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
        fair_value: Optional[float] = None,
        analyst_consensus_target: Optional[float] = None,
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
        bear_target = price_targets.get("bear_target", current_price * 0.85)

        # QA flags — collect every constraint violation or clamping event for admin review
        qa_flags: list = []

        # Sanity gate: reject targets wildly out of range (broken valuation / stale cache data)
        if base_target > current_price * 3.0 or base_target < current_price * 0.20:
            logger.warning(
                f"base_target ${base_target:.2f} is unreasonable vs current_price ${current_price:.2f} "
                f"(ratio={base_target/current_price:.1f}x) — using percentage fallback"
            )
            qa_flags.append(
                f"base_target ${base_target:.2f} outside 0.2x–3.0x range vs current ${current_price:.2f}; "
                "recalculated to current_price × 1.15"
            )
            base_target = current_price * 1.15
            bull_target = current_price * 1.30  # reset bull too since it was derived from bad base
        elif bull_target > current_price * 4.0 or bull_target < current_price * 0.25:
            logger.warning(
                f"bull_target ${bull_target:.2f} is unreasonable vs current_price ${current_price:.2f} "
                f"— using percentage fallback"
            )
            qa_flags.append(
                f"bull_target ${bull_target:.2f} outside 0.25x–4.0x range vs current ${current_price:.2f}; "
                "recalculated to current_price × 1.30"
            )
            bull_target = current_price * 1.30

        # H1: Enforce bear < base < bull fair value chain consistency
        if bear_target >= base_target:
            qa_flags.append(
                f"Chain violation: bear_target (${bear_target:.2f}) >= base_target (${base_target:.2f}); "
                "bear recalculated to base × 0.85"
            )
            bear_target = round(base_target * 0.85, 2)
        if bull_target <= base_target:
            qa_flags.append(
                f"Chain violation: bull_target (${bull_target:.2f}) <= base_target (${base_target:.2f}); "
                "bull recalculated to base × 1.15"
            )
            bull_target = round(base_target * 1.15, 2)

        tech_entry = technical_levels.get("entry")
        tech_stop = technical_levels.get("stop_loss")
        tech_take_profit = technical_levels.get("take_profit")
        bb_middle = technical_levels.get("bb_middle")
        sma_50 = technical_levels.get("sma_50")
        sma_200 = technical_levels.get("sma_200")

        poc = volume_profile_data.get("poc")
        val_low = volume_profile_data.get("value_area_low")
        val_high = volume_profile_data.get("value_area_high")

        ideal_low = entry_strategy.get("ideal_zone", {}).get("low", current_price * 0.90)
        ideal_high = entry_strategy.get("ideal_zone", {}).get("high", current_price * 0.95)

        # --- Regime detection ---
        # MOMENTUM: price > 150% of fair value — targets must anchor to current price, not intrinsic value
        # DISTRESSED: price < 50% of fair value
        # STANDARD: price within 50–150% of fair value
        regime_mode = "STANDARD"
        if fair_value and fair_value > 0:
            fv_ratio = current_price / fair_value
            if fv_ratio > 1.50:
                regime_mode = "MOMENTUM"
            elif fv_ratio < 0.50:
                regime_mode = "DISTRESSED"

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
        # Stop must be at least stop_pct below entry (guarantees > 5% risk buffer)
        conservative_stop = min(conservative_stop, conservative_entry * (1 - stop_pct))

        # Build sorted technical resistance levels above conservative entry.
        # These route T1 and T2 through sequential technical gates before
        # falling back to fundamental targets for T3. T4 = regime expansion.
        _resistance_candidates = [bb_middle, sma_50, sma_200, poc, val_high, tech_take_profit]
        conservative_resistances = sorted([
            r for r in _resistance_candidates
            if r is not None and r > conservative_entry * 1.01
        ])

        # T1: first technical resistance above entry (tactical bounce / near-term)
        if conservative_resistances:
            conservative_t1 = conservative_resistances[0]
            conservative_t1_label = "T1 — Tactical Bounce Target"
        else:
            conservative_t1 = max(
                poc or 0, tech_take_profit or 0, val_high or 0, conservative_entry * 1.08
            )
            conservative_t1_label = "T1 — Continuation Scenario"
        conservative_t1 = max(conservative_t1, conservative_entry * 1.05)

        # T2: second technical resistance (trend repair / moving average reclaim)
        if len(conservative_resistances) >= 2:
            conservative_t2 = conservative_resistances[1]
            conservative_t2_label = "T2 — Trend Repair Target"
        else:
            conservative_t2 = min(base_target, max(conservative_t1 * 1.15, conservative_t1 * 1.20))
            conservative_t2_label = "T2 — Re-rating Scenario"
        conservative_t2 = max(conservative_t2, conservative_t1 * 1.05)

        # T3: fundamental fair value (base-case intrinsic value)
        conservative_t3 = max(base_target, conservative_t2 * 1.05)
        conservative_t3_label = "T3 — Fundamental Re-rating Target"

        # T4: regime expansion (bull-case — conditional, muted in display)
        conservative_t4 = max(bull_target, conservative_t3 * 1.15)
        conservative_t4_label = "T4 — Regime Expansion Scenario"

        # --- Aggressive setup: market entry, tighter stops ---
        aggressive_entry = current_price
        aggressive_stop_pct = {"Low": 0.10, "Medium": 0.08, "High": 0.05}.get(risk_level, 0.08)
        aggressive_stop = current_price * (1 - aggressive_stop_pct)

        # Build resistance levels above aggressive entry (current price)
        aggressive_resistances = sorted([
            r for r in _resistance_candidates
            if r is not None and r > aggressive_entry * 1.01
        ])

        # T1: first technical resistance (tactical bounce)
        if aggressive_resistances:
            aggressive_t1 = aggressive_resistances[0]
            aggressive_t1_label = "T1 — Tactical Bounce Target"
        else:
            aggressive_t1 = aggressive_entry * 1.10
            aggressive_t1_label = "T1 — Continuation Scenario"
        aggressive_t1 = max(aggressive_t1, aggressive_entry * 1.05)

        # T2: second technical resistance or trend repair
        if len(aggressive_resistances) >= 2:
            aggressive_t2 = aggressive_resistances[1]
            aggressive_t2_label = "T2 — Trend Repair Target"
        else:
            aggressive_t2 = min(base_target, max(aggressive_t1 * 1.15, aggressive_t1 * 1.20))
            aggressive_t2_label = "T2 — Re-rating Scenario"
        aggressive_t2 = max(aggressive_t2, aggressive_t1 * 1.05)

        # T3: fundamental fair value
        aggressive_t3 = max(base_target, aggressive_t2 * 1.05)
        aggressive_t3_label = "T3 — Fundamental Re-rating Target"

        # T4: regime expansion
        aggressive_t4 = max(bull_target, aggressive_t3 * 1.15)
        aggressive_t4_label = "T4 — Regime Expansion Scenario"

        # --- MOMENTUM regime: ensure aggressive targets are anchored above current price ---
        # When price > 150% of intrinsic fair value, the structural base/bull targets are
        # far below current price and would produce illogical profit targets.
        # Override to use technical resistance + momentum projections instead.
        if regime_mode == "MOMENTUM":
            # T2 override: analyst consensus (if above current) or 25% momentum continuation
            if analyst_consensus_target and analyst_consensus_target > current_price * 1.01:
                aggressive_t2 = analyst_consensus_target
                aggressive_t2_label = "T2 — Analyst Consensus Target (6–12 mo)"
            elif aggressive_t2 <= current_price:
                aggressive_t2 = current_price * 1.25
                aggressive_t2_label = "T2 — Momentum Continuation (25% above current)"
            # T3 override: extended momentum if below current price
            if aggressive_t3 <= current_price:
                aggressive_t3 = max(aggressive_t2 * 1.15, current_price * 1.40)
                aggressive_t3_label = "T3 — Momentum Continuation (not anchored to intrinsic value)"
            # T4 override: label as structural reversion, zero sell %
            aggressive_t4 = fair_value if fair_value else aggressive_t4
            aggressive_t4_label = "T4 — Structural Reversion (long-term only)"

        _MIN_RISK_BUFFER = 0.05  # 5% minimum gap between entry and stop

        # C2: Conservative setup — enforce minimum risk buffer
        conservative_risk_pct = (
            (conservative_entry - conservative_stop) / conservative_entry
            if conservative_entry > 0 else 0.0
        )
        conservative_setup_unavailable: str | None = None
        if conservative_risk_pct < _MIN_RISK_BUFFER and conservative_entry > 0:
            enforced_stop = round(conservative_entry * (1 - _MIN_RISK_BUFFER), 2)
            if enforced_stop < conservative_stop:
                # Widen stop to meet minimum buffer
                qa_flags.append(
                    f"Conservative stop widened from ${conservative_stop:.2f} to ${enforced_stop:.2f} "
                    f"to enforce {_MIN_RISK_BUFFER*100:.0f}% minimum risk buffer"
                )
                conservative_stop = enforced_stop
                conservative_risk_pct = _MIN_RISK_BUFFER
            else:
                # Cannot satisfy minimum buffer — entry and stop are too close
                conservative_setup_unavailable = (
                    "Setup Unavailable — insufficient risk buffer. "
                    f"Entry (${conservative_entry:.2f}) and stop (${conservative_stop:.2f}) "
                    "are within 5% of each other; risk parameters do not support a valid setup."
                )
                qa_flags.append(f"Conservative setup unavailable: entry/stop collision (<5% buffer)")

        # C2: Aggressive setup — enforce minimum risk buffer
        aggressive_risk_pct = (
            (aggressive_entry - aggressive_stop) / aggressive_entry
            if aggressive_entry > 0 else 0.0
        )
        aggressive_setup_unavailable: str | None = None
        if aggressive_risk_pct < _MIN_RISK_BUFFER and aggressive_entry > 0:
            enforced_agg_stop = round(aggressive_entry * (1 - _MIN_RISK_BUFFER), 2)
            if enforced_agg_stop < aggressive_stop:
                qa_flags.append(
                    f"Aggressive stop widened from ${aggressive_stop:.2f} to ${enforced_agg_stop:.2f} "
                    f"to enforce {_MIN_RISK_BUFFER*100:.0f}% minimum risk buffer"
                )
                aggressive_stop = enforced_agg_stop
                aggressive_risk_pct = _MIN_RISK_BUFFER
            else:
                aggressive_setup_unavailable = (
                    "Setup Unavailable — insufficient risk buffer. "
                    f"Entry (${aggressive_entry:.2f}) and stop (${aggressive_stop:.2f}) "
                    "are within 5% of each other; risk parameters do not support a valid setup."
                )
                qa_flags.append(f"Aggressive setup unavailable: entry/stop collision (<5% buffer)")

        def per_100(entry, target):
            return round(abs(target - entry) * 100, 2)

        def risk_reward(entry, stop, t2):
            loss = entry - stop
            gain = t2 - entry
            if loss > 0:
                return round(gain / loss, 1)
            return 0.0

        # Identify which anchor drove the conservative entry (for label transparency)
        if tech_entry and conservative_entry == min(tech_entry, current_price):
            conservative_entry_anchor = "Technical Regime Level"
        elif val_low and abs(conservative_entry - val_low) < 0.01:
            conservative_entry_anchor = "Market Structure Value Area (Volume Profile)"
        else:
            conservative_entry_anchor = "Execution Discount Zone (Intrinsic Value Derived)"

        def _build_target(price, sell_pct, label, current_price=current_price):
            """Build a target dict, flagging suppression if price < current_price for long setups."""
            t = {"price": round(price, 2), "sell_pct": sell_pct, "label": label}
            if price < current_price and sell_pct > 0:
                # Target is below current price — illogical as a profit target for a long position
                t["suppressed"] = True
                fv_str = f"${fair_value:.0f}" if fair_value else "fair value"
                t["suppression_reason"] = (
                    f"Target below current price — suppressed in momentum regime. "
                    f"See structural value zone ({fv_str}) for long-term mean reversion basis."
                )
            else:
                t["suppressed"] = False
            return t

        cons_targets = [
            _build_target(conservative_t1, 30, conservative_t1_label),
            _build_target(conservative_t2, 40, conservative_t2_label),
            _build_target(conservative_t3, 30, conservative_t3_label),
            _build_target(conservative_t4, 0, conservative_t4_label),
        ]
        agg_targets = [
            _build_target(aggressive_t1, 33, aggressive_t1_label),
            _build_target(aggressive_t2, 34, aggressive_t2_label),
            _build_target(aggressive_t3, 33, aggressive_t3_label),
            _build_target(aggressive_t4, 0, aggressive_t4_label),
        ]

        conservative_side = {
            "label": "Conservative (Recommended)",
            "entry": round(conservative_entry, 2),
            "entry_anchor": conservative_entry_anchor,
            "stop_loss": round(conservative_stop, 2),
            "targets": cons_targets,
            "max_loss_per_100": per_100(conservative_entry, conservative_stop),
            "max_gain_per_100": per_100(conservative_entry, conservative_t4),
            "risk_reward": risk_reward(conservative_entry, conservative_stop, conservative_t2),
            "setup_unavailable": conservative_setup_unavailable,
        }

        # In MOMENTUM mode: expose the structural anchor's asymmetry separately so
        # users understand that the high R/R is from the structural entry, not current price.
        if regime_mode == "MOMENTUM":
            conservative_side["structural_anchor_price"] = round(conservative_entry, 2)
            # Asymmetry from current price: gain = T2 - current_price (may be negative)
            current_price_gain = conservative_t2 - current_price
            current_price_risk = current_price - conservative_stop
            if current_price_risk > 0:
                rr_from_current = round(current_price_gain / current_price_risk, 1)
            else:
                rr_from_current = None
            conservative_side["asymmetry_from_current_price"] = rr_from_current

        result = {
            "conservative": conservative_side,
            "aggressive": {
                "label": "Aggressive (Higher risk)",
                "entry": round(aggressive_entry, 2),
                "entry_anchor": "Market Order (Current Price)",
                "stop_loss": round(aggressive_stop, 2),
                "targets": agg_targets,
                "max_loss_per_100": per_100(aggressive_entry, aggressive_stop),
                "max_gain_per_100": per_100(aggressive_entry, aggressive_t4),
                "risk_reward": risk_reward(aggressive_entry, aggressive_stop, aggressive_t2),
                "setup_unavailable": aggressive_setup_unavailable,
            },
            # Regime classification — STANDARD / MOMENTUM / DISTRESSED
            "regime_mode": regime_mode,
            "intrinsic_fair_value": round(fair_value, 2) if fair_value else None,
            # Taxonomy clarification for display
            "scenario_taxonomy": (
                "T1 (Tactical Bounce Target): First meaningful technical resistance above entry — "
                "typically Bollinger Band midline or nearest resistance level. Requires RSI reclaim "
                "above 50 with volume confirmation. "
                "T2 (Trend Repair Target): Second resistance or moving average reclaim (SMA 50/200 "
                "confluence) — signals trend reversal confirmation. Requires sustained close above "
                "both moving averages. "
                "T3 (Fundamental Re-rating Target): Base-case intrinsic value — requires trend repair "
                "and catalyst-driven re-rating; conditional on earnings thesis validation. "
                "T4 (Regime Expansion Scenario): Bull-case regime expansion — extended timeline "
                "(24-36 months), conditional on full thesis validation and favorable macro. "
                "Displayed as reference only; not a primary position management target."
            ),
            "technical_resistance_levels": conservative_resistances,
            "report_qa_flags": qa_flags,
        }

        # Add momentum regime warning when stock trades far above intrinsic value
        if regime_mode == "MOMENTUM" and fair_value:
            result["momentum_regime_warning"] = (
                f"⚠️ Momentum Regime: Targets anchored to current market price, not intrinsic value. "
                f"Fair value (${fair_value:.2f}) represents long-term mean reversion basis only."
            )
        elif regime_mode == "MOMENTUM":
            result["momentum_regime_warning"] = (
                "⚠️ Momentum Regime: Stock trades significantly above intrinsic value. "
                "Targets anchored to current market price."
            )
        else:
            result["momentum_regime_warning"] = None

        return result

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
        fair_value: Optional[float] = None,
        analyst_consensus_target: Optional[float] = None,
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

        # Technical trim levels for MOMENTUM HOLD guidance — derived from same sources as trade setup
        _val_high = volume_profile.get("value_area_high") if volume_profile else None
        _val_low = volume_profile.get("value_area_low") if volume_profile else None
        _bb_upper = technical_indicators.get("bollinger_bands", {}).get("upper_band")
        # Regime detection: mirrors calculate_enhanced_trade_setup logic exactly.
        # signal_breakdown does NOT carry regime_mode — must compute from fair_value ratio.
        if fair_value and fair_value > 0:
            _fv_ratio = current_price / fair_value
            if _fv_ratio > 1.50:
                _regime_mode = "MOMENTUM"
            elif _fv_ratio < 0.50:
                _regime_mode = "DISTRESSED"
            else:
                _regime_mode = "STANDARD"
        else:
            _regime_mode = "STANDARD"

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
                signal_breakdown=signal_breakdown,
                value_area_high=_val_high,
                value_area_low=_val_low,
                bb_upper=_bb_upper,
                regime_mode=_regime_mode,
            )
        except Exception as e:
            logger.warning(f"Decision framework calculation failed: {e}")

        # 3. Enhanced trade setup
        enhanced_trade_setup = None
        report_qa_flags: list = []
        try:
            tech_levels = dict(entry_exit.get("key_levels", {}))  # copy to avoid mutation
            # Inject Bollinger Band midline and SMA levels for sequential T1/T2/T3 resistance routing
            _bb = technical_indicators.get("bollinger_bands", {})
            _bb_middle = _bb.get("middle_band")
            if not _bb_middle:
                _upper = _bb.get("upper_band")
                _lower = _bb.get("lower_band")
                if _upper and _lower:
                    _bb_middle = (_upper + _lower) / 2
            _ma = technical_indicators.get("moving_averages", {})
            _sma_50 = _ma.get("sma_50")
            _sma_200 = _ma.get("sma_200")
            if _bb_middle:
                tech_levels["bb_middle"] = _bb_middle
            if _sma_50:
                tech_levels["sma_50"] = _sma_50
            if _sma_200:
                tech_levels["sma_200"] = _sma_200
            _setup_result = self.calculate_enhanced_trade_setup(
                current_price=current_price,
                entry_strategy=entry_strategy,
                exit_plan=exit_plan,
                price_targets=price_targets,
                technical_levels=tech_levels,
                volume_profile_data=volume_profile,
                risk_level=risk_level,
                fair_value=fair_value,
                analyst_consensus_target=analyst_consensus_target,
            )
            # Extract qa_flags before storing the trade setup
            if _setup_result:
                report_qa_flags = _setup_result.pop("report_qa_flags", [])
                enhanced_trade_setup = _setup_result
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
            "report_qa_flags": report_qa_flags,
        }

    # --- Private helpers ---

    @staticmethod
    def _build_clean_one_liner(rating: str, buyer_action: str, holder_action: str) -> str:
        """
        Build a clean, non-contradictory one-liner headline.

        Eliminates the "HOLD | BUY NOW for new buyers | HOLD for holders" pattern
        that confuses readers by presenting a single primary action statement.
        """
        if rating in ("STRONG SELL", "SELL"):
            return f"{rating} — Reduce exposure"

        if rating == "HOLD":
            if buyer_action == "WAIT":
                return "HOLD — Wait for better entry"
            elif buyer_action == "SCALE IN":
                return "HOLD — Wait for signal resolution"
            elif buyer_action == "BUY NOW":
                return "HOLD — Discounted entry; proceed cautiously"
            else:
                return "HOLD — Maintain current position"

        # BUY / STRONG BUY
        if buyer_action == "BUY NOW":
            return f"{rating} — Enter at current levels"
        elif buyer_action == "SCALE IN":
            return f"{rating} — Build position gradually"
        elif buyer_action == "WAIT":
            return f"{rating} — Wait for pullback entry"

        # Fallback
        return f"{rating} — {holder_action.title()} position"

    @staticmethod
    def _build_action_subtext(
        rating: str,
        buyer_action: str,
        holder_action: str,
        entry_zone_low: float,
        entry_zone_high: float,
        buy_limit: float,
        stop_loss: float,
        value_area_high: Optional[float] = None,
        value_area_low: Optional[float] = None,
        regime_mode: Optional[str] = None,
    ) -> list:
        """
        Build concise per-reader-type guidance lines shown below the one_liner.

        Separates New Positions / Current Holders / Traders without contradiction.
        In MOMENTUM regime, Current Holders line uses market-price-anchored levels
        (value_area_high trim trigger, value_area_low stop) instead of the structural
        value-zone levels which are irrelevant to a holder at a significantly higher price.
        """
        lines = []

        # New positions guidance
        if buyer_action == "WAIT":
            lines.append(f"New positions: Target ${entry_zone_low:.0f}–${entry_zone_high:.0f} entry zone")
        elif buyer_action == "SCALE IN":
            if rating == "HOLD":
                # HOLD + SCALE IN: conservative support-anchored language, never "25-30% at market"
                lines.append(f"New positions: Initiate cautiously at ${buy_limit:.0f} support only — 10-15% max until thesis confirms")
            else:
                lines.append(f"New positions: Start 25–30% at market, add on dips to ${buy_limit:.0f}")
        elif buyer_action == "BUY NOW":
            lines.append(f"New positions: Enter at market or set buy limit at ${buy_limit:.0f}")
        elif buyer_action == "AVOID":
            lines.append("New positions: Avoid — unfavorable risk/reward")

        # Current holders guidance
        if holder_action == "HOLD":
            if regime_mode == "MOMENTUM" and value_area_high:
                # MOMENTUM regime (price > 1.5× fair value): structural stop_loss is anchored to
                # intrinsic value zone — irrelevant to any holder at current market price.
                # Apply to all ratings (BUY or HOLD) — holder_action drives this, not rating.
                momentum_stop = value_area_low or entry_zone_high
                lines.append(
                    f"Current holders: Thesis intact — consider trimming above ${value_area_high:.0f} "
                    f"(Value Area High). Core stop at ${momentum_stop:.0f}. "
                    f"No additions at current levels — preferred re-entry "
                    f"${entry_zone_low:.0f}–${entry_zone_high:.0f} on any pullback."
                )
            elif rating == "HOLD":
                lines.append(f"Current holders: Maintain with hard stop at ${stop_loss:.0f} — no additions until ${buy_limit:.0f} support holds on volume")
            else:
                lines.append(f"Current holders: Maintain with stop at ${stop_loss:.0f}")
        elif holder_action == "ADD":
            lines.append(f"Current holders: Add on pullbacks below ${entry_zone_high:.0f}")
        elif holder_action == "REDUCE":
            lines.append(f"Current holders: Trim position to reduce risk")

        # Traders (only when signals conflict or negative)
        if rating in ("HOLD", "SELL", "STRONG SELL"):
            lines.append(f"Traders: Avoid until trend reversal confirmed above ${entry_zone_high:.0f}")

        return lines

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
