"""
Blended valuation calculator using multiple methodologies.

Institutional-grade improvements over naive blended approach:
1. Normalized EPS (3-5yr avg) instead of TTM EPS — eliminates cyclical noise amplification
2. EBITDA Quality Factor — penalizes high-SBC, capex-intensive, volatile-margin businesses
3. Dynamic model weights by business archetype — high-growth gets DCF, mature gets P/E
4. Confidence-weighted compression — preserves analytical signal, no blind price averaging
5. Dynamic bull/bear spread — tied to actual uncertainty (volatility, leverage, growth stability)
"""
import statistics
from typing import Optional, Dict, Any, List, Tuple
from research_swarm.logger import logger
from research_swarm.agents.fundamentalist.models import PriceTargetScenarios, DCFInputs


class BlendedValuationCalculator:
    """
    Calculates fair value using a blended methodology with institutional-grade refinements.

    Base weights (overridden by business archetype):
    - Normalized P/E Multiple: 50%
    - Quality-adjusted EV/EBITDA: 30%
    - DCF Sanity Check: 20%
    """

    def calculate_fair_value(
        self,
        ticker: str,
        current_price: float,
        valuation_metrics: Dict[str, Any],
        dcf_inputs: Optional[DCFInputs] = None,
        stock_info: Optional[Any] = None,
        historical_eps: Optional[List[float]] = None,
        sbc_ratio: Optional[float] = None,
        quarterly_margin_std: Optional[float] = None,
    ) -> Optional[PriceTargetScenarios]:
        """
        Calculate fair value using blended methodology.

        Args:
            ticker: Stock ticker
            current_price: Current market price
            valuation_metrics: From market_data_client.get_valuation_metrics()
            dcf_inputs: Optional DCF inputs
            stock_info: Optional yfinance Ticker.info dict
            historical_eps: Optional list of annual EPS values (3-5 years, newest first)
            sbc_ratio: Optional SBC/EBITDA ratio (0.0-1.0) for EBITDA quality penalty
            quarterly_margin_std: Optional operating margin std dev (%) across recent quarters

        Returns:
            PriceTargetScenarios with bull/base/bear cases, or None if insufficient data
        """
        if not valuation_metrics:
            logger.warning(f"No valuation metrics available for {ticker}")
            return None

        # Market cap and mega-cap flag
        market_cap_millions = valuation_metrics.get("market_cap_millions", 0)
        market_cap = market_cap_millions * 1_000_000 if market_cap_millions else 0
        is_mega_cap = market_cap > 50_000_000_000

        # Sector multiples
        sector_pe = valuation_metrics.get("sector_avg_pe", 18.0)
        sector_ev_ebitda = valuation_metrics.get("sector_avg_ev_ebitda", 12.0)
        enterprise_value_millions = valuation_metrics.get("enterprise_value_millions")

        # Raw data from stock_info
        ttm_eps = None
        ebitda = None
        shares_outstanding = None
        total_debt = 0
        cash = 0
        capex = None
        revenue_growth = None
        beta = None

        if stock_info:
            ttm_eps = stock_info.get("trailingEps")
            ebitda = stock_info.get("ebitda")
            shares_outstanding = stock_info.get("sharesOutstanding")
            total_debt = stock_info.get("totalDebt", 0) or 0
            cash = stock_info.get("cash", 0) or 0
            capex = stock_info.get("capitalExpenditures")
            revenue_growth = stock_info.get("revenueGrowth")
            beta = stock_info.get("beta")

        # Fallback EPS from P/E ratio
        if not ttm_eps and valuation_metrics.get("pe_ratio") and current_price:
            pe = valuation_metrics.get("pe_ratio")
            ttm_eps = current_price / pe if pe and pe > 0 else None

        # Revenue growth fallback from dcf_inputs
        if revenue_growth is None and dcf_inputs:
            revenue_growth = (dcf_inputs.revenue_growth_rate or 10.0) / 100.0

        # Debt ratio for archetype detection
        debt_ratio = (total_debt / market_cap) if market_cap > 0 and total_debt else 0.0

        # Operating margin trend (for archetype + spread)
        margin_trend = dcf_inputs.operating_margin_trend if dcf_inputs else None

        # --- 1. Normalize EPS ---
        normalized_eps = self._normalize_eps(ttm_eps, historical_eps, stock_info)

        # --- 2. EBITDA quality factor ---
        ebitda_quality = self._calculate_ebitda_quality_factor(
            ebitda=ebitda,
            sbc_ratio=sbc_ratio,
            capex=capex,
            quarterly_margin_std=quarterly_margin_std,
        )

        # --- 3. Dynamic model weights ---
        pe_weight, ev_weight, dcf_weight = self._calculate_dynamic_weights(
            revenue_growth=revenue_growth,
            debt_ratio=debt_ratio,
            operating_margin_trend=margin_trend,
            is_mega_cap=is_mega_cap,
        )

        logger.info(
            f"Fair value calc for {ticker}: mktcap=${market_cap/1e9:.1f}B, "
            f"sector_pe={sector_pe:.1f}x, ev_ebitda={sector_ev_ebitda:.1f}x, "
            f"ebitda_quality={ebitda_quality:.2f}, "
            f"weights=P/E:{pe_weight:.0%}/EV:{ev_weight:.0%}/DCF:{dcf_weight:.0%}"
        )

        # Calculate three fair value estimates
        fv_pe = self._calculate_pe_fair_value(normalized_eps, sector_pe)
        fv_ev_ebitda = self._calculate_ev_ebitda_fair_value(
            ebitda, enterprise_value_millions, sector_ev_ebitda,
            total_debt, cash, shares_outstanding, ebitda_quality
        )
        fv_dcf = self._calculate_dcf_fair_value(dcf_inputs, current_price) if dcf_inputs else None

        # Blend with dynamic weights
        base_target = self._blend_estimates(fv_pe, fv_ev_ebitda, fv_dcf, pe_weight, ev_weight, dcf_weight)

        if base_target is None:
            logger.warning(f"Insufficient data for blended valuation of {ticker}")
            return None

        deviation = abs(base_target - current_price) / current_price

        # Hard gate: extreme deviations are almost always calculation errors
        if deviation > 1.0:
            logger.warning(
                f"Extreme deviation ({deviation:.0%}) for {ticker} — calculation error suspected, "
                f"returning uncertainty scenarios"
            )
            return self._create_uncertainty_scenarios(current_price)

        if is_mega_cap and deviation > 0.45:
            logger.warning(f"High Valuation Uncertainty flagged for {ticker} (mega-cap, {deviation:.0%} deviation)")
            return self._create_uncertainty_scenarios(current_price)

        # --- 4. Confidence-weighted compression (replaces blind price averaging) ---
        # Preserves analytical signal — deviation remains visible in methodology notes
        model_confidence = self._calculate_model_confidence(
            fv_pe, fv_ev_ebitda, fv_dcf, deviation, is_mega_cap
        )

        hard_deviation_threshold = 0.35 if is_mega_cap else 0.50
        if deviation > hard_deviation_threshold:
            compressed_target = (
                base_target * model_confidence + current_price * (1 - model_confidence)
            )
            logger.info(
                f"Confidence-weighted compression: model=${base_target:.2f} → ${compressed_target:.2f} "
                f"(confidence={model_confidence:.0%}, deviation={deviation:.0%})"
            )
            base_target = compressed_target

        # --- 5. Dynamic bull/bear spread ---
        spread_factor = self._calculate_spread_factor(
            revenue_growth=revenue_growth,
            debt_ratio=debt_ratio,
            quarterly_margin_std=quarterly_margin_std,
            beta=beta,
            is_mega_cap=is_mega_cap,
        )

        methodology = self._get_methodology_description(
            fv_pe, fv_ev_ebitda, fv_dcf, pe_weight, ev_weight, dcf_weight
        )

        return self._create_scenarios(
            base_target=base_target,
            current_price=current_price,
            sector_pe=sector_pe,
            normalized_eps=normalized_eps,
            ttm_eps=ttm_eps,
            spread_factor=spread_factor,
            model_confidence=model_confidence,
            deviation_pct=deviation,
            methodology_used=methodology,
        )

    # ============================================================
    # Improvement 1: Normalized EPS
    # ============================================================

    def _normalize_eps(
        self,
        ttm_eps: Optional[float],
        historical_eps: Optional[List[float]],
        stock_info: Optional[Dict],
    ) -> Optional[float]:
        """
        Normalize EPS using 3-5 year historical average to reduce TTM noise.

        TTM EPS can be distorted by:
        - Cyclical earnings spikes/dips
        - One-time accounting items
        - Buyback timing effects
        - Temporary margin shifts

        Strategy:
        1. Use 3-5yr avg of positive annual EPS (primary)
        2. Blend TTM + Forward EPS as a two-point proxy (secondary)
        3. Fall back to TTM EPS as-is (last resort)

        A soft cap prevents historical avg from diverging too far from recent reality.
        """
        if not ttm_eps or ttm_eps <= 0:
            return ttm_eps

        # Primary: use historical EPS if ≥2 data points
        if historical_eps and len(historical_eps) >= 2:
            positive_eps = [e for e in historical_eps if e and e > 0]
            if len(positive_eps) >= 2:
                normalized = sum(positive_eps) / len(positive_eps)
                # Soft cap: prevent historical avg from being >2x or <0.4x TTM
                # This keeps us anchored to recent reality while smoothing noise
                normalized = max(ttm_eps * 0.4, min(normalized, ttm_eps * 2.0))
                logger.info(
                    f"EPS normalized: ${normalized:.2f} (3-5yr avg={sum(positive_eps)/len(positive_eps):.2f}, "
                    f"TTM=${ttm_eps:.2f}, capped to [${ttm_eps*0.4:.2f}, ${ttm_eps*2.0:.2f}])"
                )
                return normalized

        # Secondary: blend TTM + Forward EPS as two-point proxy
        if stock_info:
            forward_eps = stock_info.get("forwardEps")
            if forward_eps and forward_eps > 0:
                blended = (ttm_eps + forward_eps) / 2
                logger.info(
                    f"EPS normalized (TTM+Fwd avg): ${blended:.2f} "
                    f"(TTM=${ttm_eps:.2f}, Fwd=${forward_eps:.2f})"
                )
                return blended

        # Fallback: TTM as-is
        return ttm_eps

    # ============================================================
    # Improvement 2: EBITDA Quality Factor
    # ============================================================

    def _calculate_ebitda_quality_factor(
        self,
        ebitda: Optional[float],
        sbc_ratio: Optional[float],
        capex: Optional[float],
        quarterly_margin_std: Optional[float],
    ) -> float:
        """
        Calculate EBITDA quality factor (0.70 - 1.00).

        Penalizes EBITDA that overstates true earnings power:
        - High SBC: real economic cost excluded from EBITDA (dilutes shareholders)
        - High Capex/EBITDA: maintenance capex eats into free cash flow
        - High margin volatility: cyclical earnings deserve lower effective multiple
        """
        quality = 1.0
        penalties = []

        # SBC quality penalty: high-SBC companies overstate EBITDA vs true cash value
        if sbc_ratio is not None:
            if sbc_ratio > 0.20:  # SBC > 20% of EBITDA (very high)
                penalty = min(0.15, (sbc_ratio - 0.20) * 0.75)
                quality -= penalty
                penalties.append(f"High SBC={sbc_ratio:.0%} of EBITDA (−{penalty:.2f})")
            elif sbc_ratio > 0.10:  # Moderate SBC
                penalty = (sbc_ratio - 0.10) * 0.50
                quality -= penalty
                penalties.append(f"Moderate SBC={sbc_ratio:.0%} of EBITDA (−{penalty:.2f})")

        # Capex intensity penalty: heavy capex reduces available free cash
        if ebitda and ebitda > 0 and capex is not None:
            capex_abs = abs(capex)  # capex is typically negative in yfinance cashflow
            if capex_abs > 0:
                capex_ebitda_ratio = capex_abs / ebitda
                if capex_ebitda_ratio > 0.40:  # Capex > 40% of EBITDA
                    penalty = min(0.10, (capex_ebitda_ratio - 0.40) * 0.25)
                    quality -= penalty
                    penalties.append(f"High Capex/EBITDA={capex_ebitda_ratio:.0%} (−{penalty:.2f})")

        # Margin volatility penalty: cyclical margins → EBITDA multiple should be lower
        if quarterly_margin_std is not None and quarterly_margin_std > 3.0:
            penalty = min(0.10, (quarterly_margin_std - 3.0) * 0.02)
            quality -= penalty
            penalties.append(f"Margin volatility σ={quarterly_margin_std:.1f}% (−{penalty:.2f})")

        quality = max(0.70, quality)  # Floor at 0.70

        if penalties:
            logger.info(f"EBITDA quality: {quality:.2f} — {'; '.join(penalties)}")
        else:
            logger.debug(f"EBITDA quality: {quality:.2f} (no penalties)")

        return quality

    # ============================================================
    # Improvement 3: Dynamic Model Weights
    # ============================================================

    def _calculate_dynamic_weights(
        self,
        revenue_growth: Optional[float],
        debt_ratio: float,
        operating_margin_trend: Optional[str],
        is_mega_cap: bool,
    ) -> Tuple[float, float, float]:
        """
        Calculate dynamic model weights based on business archetype.

        Returns: (pe_weight, ev_ebitda_weight, dcf_weight)

        Archetype logic:
        - High growth (>20%/yr): DCF captures future value better than current multiples
        - Highly leveraged (D/E >0.5): EV/EBITDA is debt-aware and more reliable
        - Cyclical/contracting margins: P/E is unreliable; EV+DCF mix works better
        - Moderate growth (5-20%): Balanced blend
        - Mature/stable (<5% growth): P/E is most stable and interpretable
        """
        rev_growth = revenue_growth or 0.0

        if rev_growth > 0.20:
            # High-growth: current multiples understate future value
            weights = (0.25, 0.25, 0.50)
            archetype = "High Growth (DCF-dominant)"
        elif debt_ratio > 0.50:
            # Highly leveraged: EV/EBITDA accounts for debt structure
            weights = (0.20, 0.50, 0.30)
            archetype = "Highly Leveraged (EV/EBITDA-dominant)"
        elif operating_margin_trend == "contracting":
            # Cyclical/declining: P/E based on contracting earnings is unreliable
            weights = (0.25, 0.40, 0.35)
            archetype = "Cyclical/Contracting Margins (EV+DCF mix)"
        elif rev_growth > 0.05:
            # Moderate growth: slight P/E edge but balanced
            weights = (0.40, 0.35, 0.25)
            archetype = "Moderate Growth (Balanced)"
        else:
            # Mature/stable: earnings-driven, P/E dominant
            weights = (0.55, 0.30, 0.15)
            archetype = "Mature/Stable (P/E-dominant)"

        logger.info(
            f"Business archetype: {archetype} → "
            f"P/E:{weights[0]:.0%} EV/EBITDA:{weights[1]:.0%} DCF:{weights[2]:.0%}"
        )
        return weights

    # ============================================================
    # Improvement 4: Confidence-Weighted Compression
    # ============================================================

    def _calculate_model_confidence(
        self,
        fv_pe: Optional[float],
        fv_ev_ebitda: Optional[float],
        fv_dcf: Optional[float],
        deviation: float,
        is_mega_cap: bool,
    ) -> float:
        """
        Calculate confidence in the model's fair value vs the market price.

        Higher confidence → preserve model value (less compression toward market).
        Lower confidence → compress toward market price.

        Signals:
        - Method convergence: all 3 methods agree → higher confidence
        - Method divergence: methods spread widely → lower confidence
        - Mega-cap: market is highly efficient → model less likely to be right
        - Large deviation: bigger gap from market → more skepticism warranted

        Returns: float 0.30 - 0.80
        """
        # Base confidence by number of methods available
        available = sum(1 for fv in [fv_pe, fv_ev_ebitda, fv_dcf] if fv is not None)
        base_confidence = {1: 0.40, 2: 0.55, 3: 0.65}.get(available, 0.40)

        # Method convergence bonus/penalty
        values = [fv for fv in [fv_pe, fv_ev_ebitda, fv_dcf] if fv is not None]
        if len(values) >= 2:
            avg = sum(values) / len(values)
            max_spread = max(abs(v - avg) / avg for v in values)
            if max_spread < 0.10:    # Methods converge within 10%
                base_confidence = min(0.80, base_confidence + 0.15)
            elif max_spread > 0.30:  # Methods diverge widely
                base_confidence = max(0.30, base_confidence - 0.15)

        # Mega-cap penalty: price discovery is efficient for $50B+ companies
        if is_mega_cap:
            base_confidence = max(0.30, base_confidence - 0.10)

        # Large deviation penalty: model likely missing something
        if deviation > 0.60:
            base_confidence = max(0.30, base_confidence - 0.15)
        elif deviation > 0.40:
            base_confidence = max(0.30, base_confidence - 0.08)

        return round(base_confidence, 2)

    # ============================================================
    # Improvement 5: Dynamic Bull/Bear Spread
    # ============================================================

    def _calculate_spread_factor(
        self,
        revenue_growth: Optional[float],
        debt_ratio: float,
        quarterly_margin_std: Optional[float],
        beta: Optional[float],
        is_mega_cap: bool,
    ) -> float:
        """
        Calculate the bull/bear scenario spread as a fraction of base value.

        Returns: float 0.08 - 0.35 (i.e., ±8% to ±35% around base)

        Factors:
        - Revenue growth: high-growth businesses have wider uncertainty bands
        - Leverage: debt amplifies downside risk
        - Margin volatility: cyclical margins → wider spread
        - Beta: higher market sensitivity → wider spread
        - Mega-cap: large liquid companies have tighter bands (more efficient)
        """
        rev_growth = revenue_growth or 0.0
        spread = 0.15  # Default ±15%

        # Growth-based widening
        if rev_growth > 0.30:
            spread += 0.10
        elif rev_growth > 0.15:
            spread += 0.05

        # Leverage-based widening
        if debt_ratio > 0.50:
            spread += 0.08
        elif debt_ratio > 0.25:
            spread += 0.04

        # Margin volatility widening
        if quarterly_margin_std and quarterly_margin_std > 5.0:
            spread += 0.08
        elif quarterly_margin_std and quarterly_margin_std > 2.5:
            spread += 0.04

        # Beta-based widening
        if beta and beta > 1.5:
            spread += 0.05
        elif beta and beta > 1.2:
            spread += 0.02

        # Mega-cap compression (tighter band for large, liquid companies)
        if is_mega_cap:
            spread = min(spread, 0.20)
            spread = max(spread, 0.08)

        spread = max(0.08, min(spread, 0.35))
        logger.info(
            f"Scenario spread: ±{spread:.0%} "
            f"(rev_growth={rev_growth:.0%}, debt={debt_ratio:.2f}, "
            f"margin_std={quarterly_margin_std}, beta={beta})"
        )
        return spread

    # ============================================================
    # Core calculation methods
    # ============================================================

    def _calculate_pe_fair_value(
        self,
        normalized_eps: Optional[float],
        sector_pe: float,
    ) -> Optional[float]:
        """Calculate fair value using normalized EPS × sector P/E multiple."""
        if not normalized_eps or normalized_eps <= 0:
            logger.debug("No valid normalized EPS for P/E valuation")
            return None

        fair_value = normalized_eps * sector_pe
        logger.info(
            f"P/E fair value: ${fair_value:.2f} "
            f"(Normalized EPS=${normalized_eps:.2f} × {sector_pe:.1f}x sector P/E)"
        )
        return fair_value

    def _calculate_ev_ebitda_fair_value(
        self,
        ebitda: Optional[float],
        enterprise_value_millions: Optional[float],
        sector_ev_ebitda: float,
        total_debt: float,
        cash: float,
        shares_outstanding: Optional[float],
        ebitda_quality: float = 1.0,
    ) -> Optional[float]:
        """Calculate fair value using quality-adjusted EBITDA × sector EV/EBITDA multiple."""
        if enterprise_value_millions and sector_ev_ebitda and not ebitda:
            logger.debug("No direct EBITDA — skipping EV/EBITDA method")
            return None

        if not ebitda or ebitda <= 0 or not shares_outstanding or shares_outstanding <= 0:
            logger.debug("No valid EBITDA or shares for EV/EBITDA valuation")
            return None

        # Apply quality factor: discounts EBITDA for SBC, capex intensity, volatility
        adjusted_ebitda = ebitda * ebitda_quality
        if ebitda_quality < 1.0:
            logger.info(
                f"Quality-adjusted EBITDA: ${adjusted_ebitda/1e6:.0f}M "
                f"(raw ${ebitda/1e6:.0f}M × quality={ebitda_quality:.2f})"
            )

        # Implied EV at sector multiple, back-calculate to equity per share
        implied_ev_millions = (adjusted_ebitda / 1_000_000) * sector_ev_ebitda
        equity_value_millions = implied_ev_millions - (total_debt / 1_000_000) + (cash / 1_000_000)
        fair_value_per_share = (equity_value_millions * 1_000_000) / shares_outstanding

        logger.info(
            f"EV/EBITDA fair value: ${fair_value_per_share:.2f} "
            f"(adj. EBITDA ${adjusted_ebitda/1e6:.0f}M × {sector_ev_ebitda:.1f}x, quality={ebitda_quality:.2f})"
        )
        return fair_value_per_share

    def _calculate_dcf_fair_value(
        self,
        dcf_inputs: DCFInputs,
        current_price: float
    ) -> Optional[float]:
        """Calculate DCF-based fair value."""
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
        fv_dcf: Optional[float],
        pe_weight: float = 0.50,
        ev_weight: float = 0.30,
        dcf_weight: float = 0.20,
    ) -> Optional[float]:
        """
        Blend fair value estimates using dynamic weighted average.
        Renormalizes weights when some methods are unavailable.
        """
        estimates = []
        weights = []

        if fv_pe is not None and fv_pe > 0:
            estimates.append(fv_pe)
            weights.append(pe_weight)

        if fv_ev_ebitda is not None and fv_ev_ebitda > 0:
            estimates.append(fv_ev_ebitda)
            weights.append(ev_weight)

        if fv_dcf is not None and fv_dcf > 0:
            estimates.append(fv_dcf)
            weights.append(dcf_weight)

        if not estimates:
            return None

        total_weight = sum(weights)
        normalized_weights = [w / total_weight for w in weights]
        blended = sum(est * wgt for est, wgt in zip(estimates, normalized_weights))

        methods = []
        if fv_pe: methods.append("P/E")
        if fv_ev_ebitda: methods.append("EV/EBITDA")
        if fv_dcf: methods.append("DCF")

        logger.info(f"Blended fair value: ${blended:.2f} ({', '.join(methods)})")
        return blended

    def _create_scenarios(
        self,
        base_target: float,
        current_price: float,
        sector_pe: float,
        normalized_eps: Optional[float],
        ttm_eps: Optional[float],
        spread_factor: float,
        model_confidence: float,
        deviation_pct: float,
        methodology_used: str,
    ) -> PriceTargetScenarios:
        """Create bull/base/bear scenarios with dynamic spread tied to uncertainty."""
        bull_target = base_target * (1 + spread_factor)
        bear_target = base_target * (1 - spread_factor)

        # Ensure proper ordering with minimum buffer
        bull_target = max(bull_target, base_target * 1.05)
        bear_target = min(bear_target, base_target * 0.95)

        spread_pct = f"{spread_factor:.0%}"

        # EPS note for transparency
        eps_note = ""
        if normalized_eps and ttm_eps and abs(normalized_eps - ttm_eps) > 0.10 * abs(ttm_eps):
            eps_note = f" (normalized EPS ${normalized_eps:.2f} vs TTM ${ttm_eps:.2f})"
        elif normalized_eps:
            eps_note = f", normalized EPS=${normalized_eps:.2f}"

        confidence_note = f"Model confidence: {model_confidence:.0%}"
        if deviation_pct > 0.25:
            confidence_note += f" (model deviated {deviation_pct:.0%} from market price — signal preserved)"

        base_assumptions = (
            f"Fair value ${base_target:.2f} using {sector_pe:.1f}x sector P/E{eps_note}. "
            f"{methodology_used}. {confidence_note}."
        )
        bull_assumptions = (
            f"Bull case +{spread_pct}: {sector_pe*1.1:.1f}x P/E with margin improvement and market share gains."
        )
        bear_assumptions = (
            f"Bear case −{spread_pct}: {sector_pe*0.9:.1f}x P/E with competitive pressure or margin headwinds."
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
            methodology=methodology_used,
        )

    def _create_uncertainty_scenarios(self, current_price: float) -> PriceTargetScenarios:
        """Create scenarios when valuation uncertainty is too high to model reliably."""
        return PriceTargetScenarios(
            base_target=round(current_price, 2),
            base_assumptions=(
                "High Valuation Uncertainty — calculated fair value deviated >45% from market price. "
                "Using market price as base case."
            ),
            base_probability=0.50,
            bull_target=round(current_price * 1.10, 2),
            bull_assumptions="Bull case: +10% from current price",
            bull_probability=0.25,
            bear_target=round(current_price * 0.90, 2),
            bear_assumptions="Bear case: −10% from current price",
            bear_probability=0.25,
            methodology="Market Price (High Uncertainty)",
        )

    def _get_methodology_description(
        self,
        fv_pe: Optional[float],
        fv_ev_ebitda: Optional[float],
        fv_dcf: Optional[float],
        pe_weight: float = 0.50,
        ev_weight: float = 0.30,
        dcf_weight: float = 0.20,
    ) -> str:
        """Generate description of methodology and actual weights used."""
        methods = []
        if fv_pe:
            methods.append(f"Normalized P/E ({pe_weight:.0%})")
        if fv_ev_ebitda:
            methods.append(f"Quality-adj. EV/EBITDA ({ev_weight:.0%})")
        if fv_dcf:
            methods.append(f"DCF ({dcf_weight:.0%})")

        if len(methods) >= 2:
            return "Blended: " + ", ".join(methods)
        elif len(methods) == 1:
            return methods[0] + " only"
        return "Insufficient data"

    # ============================================================
    # Sector defaults (used as fallback when no data available)
    # ============================================================

    def _get_default_sector_pe(self, sector: str) -> float:
        defaults = {
            "technology": 22.0, "industrials": 18.0, "financials": 15.0,
            "energy": 16.0, "healthcare": 20.0, "consumer": 19.0,
            "utilities": 17.0, "real estate": 19.0, "materials": 16.0,
            "communication": 21.0,
        }
        for key, pe in defaults.items():
            if key in sector.lower():
                return pe
        return 18.0

    def _get_default_sector_ev_ebitda(self, sector: str) -> float:
        defaults = {
            "technology": 15.0, "industrials": 11.0, "financials": 10.0,
            "energy": 9.0, "healthcare": 13.0, "consumer": 12.0,
            "utilities": 10.0, "real estate": 14.0, "materials": 10.0,
            "communication": 13.0,
        }
        for key, ev_ebitda in defaults.items():
            if key in sector.lower():
                return ev_ebitda
        return 12.0


# Global instance
blended_valuation_calculator = BlendedValuationCalculator()
