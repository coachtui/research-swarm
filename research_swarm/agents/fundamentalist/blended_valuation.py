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
            PriceTargetScenarios with fair value range, confidence, and scenario targets.
            None if insufficient data to produce any estimate.
        """
        if not valuation_metrics:
            logger.warning(f"No valuation metrics available for {ticker}")
            return None

        # Market cap and mega-cap flag
        market_cap_millions = valuation_metrics.get("market_cap_millions", 0)
        market_cap = market_cap_millions * 1_000_000 if market_cap_millions else 0
        is_mega_cap = market_cap > 50_000_000_000

        # Sector multiples — track whether they were defaulted
        sector_pe = valuation_metrics.get("sector_avg_pe", 18.0)
        sector_ev_ebitda = valuation_metrics.get("sector_avg_ev_ebitda", 12.0)
        enterprise_value_millions = valuation_metrics.get("enterprise_value_millions")
        sector_multiples_defaulted = not valuation_metrics.get("sector_avg_pe")

        # Raw data from stock_info
        ttm_eps = None
        ttm_eps_from_stock = False
        ebitda = None
        shares_outstanding = None
        total_debt = 0
        cash = 0
        capex = None
        revenue_growth = None
        beta = None

        if stock_info:
            ttm_eps = stock_info.get("trailingEps")
            if ttm_eps:
                ttm_eps_from_stock = True
            ebitda = stock_info.get("ebitda")
            shares_outstanding = stock_info.get("sharesOutstanding")
            total_debt = stock_info.get("totalDebt", 0) or 0
            cash = stock_info.get("cash", 0) or 0
            capex = stock_info.get("capitalExpenditures")
            revenue_growth = stock_info.get("revenueGrowth")
            beta = stock_info.get("beta")

        # Fallback EPS from P/E ratio — track this as a synthetic fallback
        eps_from_fallback = False
        if not ttm_eps and valuation_metrics.get("pe_ratio") and current_price:
            pe = valuation_metrics.get("pe_ratio")
            ttm_eps = current_price / pe if pe and pe > 0 else None
            if ttm_eps:
                eps_from_fallback = True

        # Revenue growth fallback from dcf_inputs
        if revenue_growth is None and dcf_inputs:
            revenue_growth = (dcf_inputs.revenue_growth_rate or 10.0) / 100.0

        # Debt/cash validity
        debt_cash_valid = (total_debt is not None) and (cash is not None)

        # Debt ratio for archetype detection
        debt_ratio = (total_debt / market_cap) if market_cap > 0 and total_debt else 0.0

        # Operating margin trend (for archetype + spread)
        margin_trend = dcf_inputs.operating_margin_trend if dcf_inputs else None

        # DCF data quality: real FCF inputs present
        dcf_has_real_fcf = bool(dcf_inputs and dcf_inputs.fcf_history and len(dcf_inputs.fcf_history) >= 2)
        dcf_mostly_defaults = not dcf_has_real_fcf

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

        # --- 4. Calculate three fair value point estimates ---
        fv_pe = self._calculate_pe_fair_value(normalized_eps, sector_pe)
        fv_ev_ebitda = self._calculate_ev_ebitda_fair_value(
            ebitda, enterprise_value_millions, sector_ev_ebitda,
            total_debt, cash, shares_outstanding, ebitda_quality
        )
        fv_dcf = self._calculate_dcf_fair_value(dcf_inputs, current_price) if dcf_inputs else None

        # --- 5. Blend midpoints ---
        fair_value_mid = self._blend_estimates(fv_pe, fv_ev_ebitda, fv_dcf, pe_weight, ev_weight, dcf_weight)

        if fair_value_mid is None:
            logger.warning(f"Insufficient data for blended valuation of {ticker}")
            return None

        deviation = abs(fair_value_mid - current_price) / current_price

        # Hard gate: deviation > 100% is almost certainly a calculation error
        if deviation > 1.0:
            logger.warning(
                f"Extreme deviation ({deviation:.0%}) for {ticker} — calculation error suspected, "
                f"returning uncertainty scenarios"
            )
            return self._create_uncertainty_scenarios(current_price)

        # --- 6. Confidence scoring (0–100) ---
        confidence_score, confidence_label, uncertainty_drivers = self._calculate_confidence_score(
            fv_pe=fv_pe,
            fv_ev_ebitda=fv_ev_ebitda,
            fv_dcf=fv_dcf,
            fair_value_mid=fair_value_mid,
            current_price=current_price,
            is_mega_cap=is_mega_cap,
            eps_from_fallback=eps_from_fallback,
            sector_multiples_defaulted=sector_multiples_defaulted,
            missing_ebitda=(ebitda is None or ebitda <= 0),
            missing_shares=(shares_outstanding is None or shares_outstanding <= 0),
            debt_cash_valid=debt_cash_valid,
            dcf_mostly_defaults=dcf_mostly_defaults,
            ttm_eps_direct=ttm_eps_from_stock,
        )

        # Mega-cap with large deviation: do not error out — widen the band instead
        # (deviation ≠ error; market may be pricing in factors the model doesn't capture)
        if is_mega_cap and deviation > 0.45:
            logger.warning(
                f"High deviation ({deviation:.0%}) for mega-cap {ticker} — widening band, not discarding model signal"
            )
            # Confidence already penalised by deviation; proceed to band construction

        # --- 7. Fair value band construction ---
        fair_value_low, fair_value_high = self._calculate_fair_value_band(
            fair_value_mid=fair_value_mid,
            confidence_score=confidence_score,
            fv_pe=fv_pe,
            fv_ev_ebitda=fv_ev_ebitda,
            fv_dcf=fv_dcf,
        )

        # --- 8. Dynamic bull/bear scenario spread (macro uncertainty) ---
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
            fair_value_mid=fair_value_mid,
            fair_value_low=fair_value_low,
            fair_value_high=fair_value_high,
            current_price=current_price,
            sector_pe=sector_pe,
            normalized_eps=normalized_eps,
            ttm_eps=ttm_eps,
            spread_factor=spread_factor,
            confidence_score=confidence_score,
            confidence_label=confidence_label,
            uncertainty_drivers=uncertainty_drivers,
            deviation_pct=deviation,
            methodology_used=methodology,
            fv_pe=fv_pe,
            fv_ev_ebitda=fv_ev_ebitda,
            fv_dcf=fv_dcf,
            revenue_growth=revenue_growth,
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
                raw_avg = sum(positive_eps) / len(positive_eps)

                # Growth company bypass: if earnings are consistently rising (newest > oldest)
                # the historical average understates current earnings power. For these companies
                # the normalization goal (smoothing cyclical noise) doesn't apply — fall through
                # to TTM+Forward blend which is more representative of ongoing run-rate.
                is_upward_trend = all(
                    positive_eps[i] > positive_eps[i + 1]
                    for i in range(len(positive_eps) - 1)
                )
                if is_upward_trend and raw_avg < ttm_eps * 0.80:
                    # Historical average is depressed relative to TTM due to growth, not noise.
                    # Skip backward averaging and use the forward-looking blend below.
                    logger.info(
                        f"EPS normalization bypassed (consistent growth trend): "
                        f"hist avg ${raw_avg:.2f} vs TTM ${ttm_eps:.2f} — using TTM+Fwd blend"
                    )
                else:
                    # Cyclical or no clear trend: historical average smooths out noise correctly
                    normalized = max(ttm_eps * 0.4, min(raw_avg, ttm_eps * 2.0))
                    logger.info(
                        f"EPS normalized: ${normalized:.2f} (3-5yr avg=${raw_avg:.2f}, "
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
    # Improvement 4: Confidence Scoring (0–100)
    # ============================================================

    def _calculate_confidence_score(
        self,
        fv_pe: Optional[float],
        fv_ev_ebitda: Optional[float],
        fv_dcf: Optional[float],
        fair_value_mid: float,
        current_price: float,
        is_mega_cap: bool,
        eps_from_fallback: bool,
        sector_multiples_defaulted: bool,
        missing_ebitda: bool,
        missing_shares: bool,
        debt_cash_valid: bool,
        dcf_mostly_defaults: bool,
        ttm_eps_direct: bool,
    ) -> Tuple[int, str, List[str]]:
        """
        Score valuation reliability on a 0–100 scale.

        Starts at 100, adds bonuses for high-quality inputs and available methods,
        then subtracts penalties for missing data, fallbacks, divergence, and
        extreme price deviation.

        Returns:
            (confidence_score: int, confidence_label: str, uncertainty_drivers: List[str])
        """
        score = 100
        drivers: List[str] = []

        # ── Method availability bonuses (+10 per valid method, max +30) ──────────
        methods_available = sum(1 for fv in [fv_pe, fv_ev_ebitda, fv_dcf] if fv is not None)
        score += methods_available * 10

        # ── Input quality bonuses (+5 per condition, max +25) ────────────────────
        if ttm_eps_direct:
            score += 5   # EPS from filing/yfinance directly
        if not missing_ebitda:
            score += 5   # EBITDA positive and present
        if not missing_shares:
            score += 5   # Shares outstanding valid
        if debt_cash_valid:
            score += 5   # Debt and cash figures present
        if not dcf_mostly_defaults:
            score += 5   # DCF uses real FCF history

        # ── Missing method penalties ──────────────────────────────────────────────
        missing_methods = 3 - methods_available
        if missing_methods == 1:
            score -= 10
            drivers.append("One valuation method unavailable (limited data coverage)")
        elif missing_methods == 2:
            score -= 25
            drivers.append("Two of three valuation methods unavailable — single-method estimate")
        elif missing_methods == 3:
            score -= 50
            drivers.append("No valid valuation methods computed")

        # ── Fallback / synthetic data penalties (-8 per condition) ───────────────
        if eps_from_fallback:
            score -= 8
            drivers.append("EPS derived from P/E ratio (direct earnings figure unavailable)")
        if sector_multiples_defaulted:
            score -= 8
            drivers.append("Sector multiples defaulted — no peer data to calibrate multiples")
        if missing_shares:
            score -= 8
            drivers.append("Shares outstanding unavailable — equity value per share is estimated")
        if missing_ebitda:
            score -= 8
            drivers.append("EBITDA unavailable — EV/EBITDA method excluded")
        if dcf_mostly_defaults:
            score -= 8
            drivers.append("DCF inputs largely defaulted — limited FCF history from filings")

        # ── Cross-method dispersion penalty ──────────────────────────────────────
        valid_fvs = [fv for fv in [fv_pe, fv_ev_ebitda, fv_dcf] if fv is not None]
        if len(valid_fvs) >= 2 and fair_value_mid > 0:
            dispersion = (max(valid_fvs) - min(valid_fvs)) / fair_value_mid
            if dispersion >= 0.70:
                score -= 35
                drivers.append(
                    f"High cross-method dispersion ({dispersion:.0%}) — methods disagree significantly on intrinsic value"
                )
            elif dispersion >= 0.40:
                score -= 20
                drivers.append(
                    f"Moderate cross-method dispersion ({dispersion:.0%}) — some disagreement between valuation methods"
                )
            elif dispersion >= 0.20:
                score -= 10
                drivers.append(
                    f"Minor cross-method dispersion ({dispersion:.0%}) — methods broadly aligned"
                )
            # dispersion < 0.20 → no penalty (methods converge)

        # ── Extreme price deviation penalty ──────────────────────────────────────
        deviation = abs(current_price - fair_value_mid) / current_price if current_price > 0 else 0.0
        threshold = 0.35 if is_mega_cap else 0.50
        if deviation >= threshold * 2:
            score -= 20
            drivers.append(
                f"Price deviates {deviation:.0%} from intrinsic midpoint — market may be pricing in factors not captured by the model"
            )
        elif deviation >= threshold:
            score -= 10
            drivers.append(
                f"Price deviates {deviation:.0%} from intrinsic midpoint — model and market diverge"
            )

        # Mega-cap note (not a penalty — informational)
        if is_mega_cap:
            drivers.append("Large-cap with highly liquid market — model estimates carry wider uncertainty vs. smaller companies")

        # ── Clamp and label ───────────────────────────────────────────────────────
        score = max(5, min(100, score))

        if score >= 75:
            label = "High"
        elif score >= 45:
            label = "Moderate"
        else:
            label = "Low"

        # Ensure 3–6 drivers (pad with a generic note if needed)
        if len(drivers) < 3:
            if methods_available == 3 and len(drivers) < 3:
                drivers.append("All three valuation methods produced estimates — blended result is well-supported")
            if not eps_from_fallback and len(drivers) < 3:
                drivers.append("EPS sourced directly — earnings-based valuation is well-grounded")
            if not dcf_mostly_defaults and len(drivers) < 3:
                drivers.append("DCF supported by real FCF history from SEC filings")

        logger.info(
            f"Confidence score: {score}/100 ({label}) — "
            f"methods={methods_available}/3, eps_fallback={eps_from_fallback}, "
            f"missing_ebitda={missing_ebitda}, deviation={deviation:.0%}"
        )
        return score, label, drivers[:6]  # cap at 6 drivers

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
    # Fair Value Band Construction
    # ============================================================

    def _calculate_fair_value_band(
        self,
        fair_value_mid: float,
        confidence_score: int,
        fv_pe: Optional[float],
        fv_ev_ebitda: Optional[float],
        fv_dcf: Optional[float],
    ) -> Tuple[float, float]:
        """
        Build an intrinsic value range (low, high) around the blended midpoint.

        Band width is driven by:
        1. Confidence score → base band (high=±15%, moderate=±25%, low=±40%)
        2. Cross-method dispersion → additional widening

        This is distinct from the bull/bear scenario spread, which reflects
        macro/business uncertainty. The fair value band reflects valuation
        model uncertainty.

        Returns: (fair_value_low, fair_value_high)
        """
        # Base band width from confidence tier
        if confidence_score >= 75:
            base_half_width = 0.15
        elif confidence_score >= 45:
            base_half_width = 0.25
        else:
            base_half_width = 0.40

        # Additional widening from cross-method dispersion
        valid_fvs = [fv for fv in [fv_pe, fv_ev_ebitda, fv_dcf] if fv is not None]
        dispersion_extra = 0.0
        if len(valid_fvs) >= 2 and fair_value_mid > 0:
            dispersion = (max(valid_fvs) - min(valid_fvs)) / fair_value_mid
            if dispersion >= 0.70:
                dispersion_extra = 0.15
            elif dispersion >= 0.40:
                dispersion_extra = 0.10
            elif dispersion >= 0.20:
                dispersion_extra = 0.05

        half_width = base_half_width + dispersion_extra
        fair_value_low = round(fair_value_mid * (1.0 - half_width), 2)
        fair_value_high = round(fair_value_mid * (1.0 + half_width), 2)

        logger.info(
            f"Fair value band: ${fair_value_low:.2f}–${fair_value_mid:.2f}–${fair_value_high:.2f} "
            f"(±{half_width:.0%}, confidence={confidence_score})"
        )
        return fair_value_low, fair_value_high

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

    # ============================================================
    # Valuation chain validator (P0)
    # ============================================================

    def _validate_valuation_chain(
        self,
        fair_value_mid: float,
        bear_target: float,
        base_target: float,
        bull_target: float,
    ) -> tuple:
        """
        Enforce structural ordering: bear < FV ≈ base < bull.

        Returns:
            (bear_target, base_target, bull_target, violations: list[str])
        """
        violations: List[str] = []

        # Rule 1: bear must be strictly below fair value
        if bear_target >= fair_value_mid:
            bear_target = round(fair_value_mid * 0.85, 2)
            violations.append("Bear case anchored to FV −15% (constraint enforcement)")

        # Rule 2: bull must be strictly above fair value
        if bull_target <= fair_value_mid:
            bull_target = round(fair_value_mid * 1.20, 2)
            violations.append("Bull case anchored to FV +20% (constraint enforcement)")

        # Rule 3: base must not embed optimism bias — within ±8% of FV midpoint
        if fair_value_mid > 0:
            drift = abs(base_target - fair_value_mid) / fair_value_mid
            if drift > 0.08:
                violations.append(
                    f"Base case re-anchored to FV midpoint (drift was {drift:.1%})"
                )
                base_target = round(fair_value_mid, 2)

        # Rule 4: scenarios must be monotonically ordered
        if not (bear_target < base_target < bull_target):
            bear_target = round(min(bear_target, base_target * 0.88), 2)
            bull_target = round(max(bull_target, base_target * 1.15), 2)
            violations.append("Scenario monotonic ordering corrected (bear < base < bull)")

        return bear_target, base_target, bull_target, violations

    # ============================================================
    # Premium justification engine (P2)
    # ============================================================

    def _justify_premium(
        self,
        current_pe: Optional[float],
        sector_pe: float,
        revenue_growth: Optional[float],
    ) -> Optional[Dict]:
        """
        Classify P/E premium as Justified, Execution-Dependent, or Speculative.

        Uses an implied PEG ratio (P/E ÷ growth %) to differentiate premium quality.
        Returns None if current P/E unavailable.
        """
        if not current_pe or current_pe <= 0 or sector_pe <= 0:
            return None

        premium_pct = (current_pe - sector_pe) / sector_pe

        # No meaningful premium — skip classification
        if premium_pct <= 0.05:
            return {
                "classification": "NO_PREMIUM",
                "label": "At or Below Sector Multiple",
                "rationale": (
                    f"Current P/E ({current_pe:.1f}x) is at or below sector average "
                    f"({sector_pe:.1f}x). No premium discount to justify."
                ),
                "premium_pct_vs_sector": round(premium_pct, 4),
                "implied_peg": None,
            }

        # Use revenue growth as EPS growth proxy when direct EPS growth unavailable
        growth_pct = max((revenue_growth or 0.10) * 100, 1.0)  # floor at 1% to avoid div/0
        implied_peg = current_pe / growth_pct

        if implied_peg < 1.5 and premium_pct < 0.50:
            classification = "JUSTIFIED_PREMIUM"
            label = "Justified Premium"
            rationale = (
                f"Implied PEG of {implied_peg:.2f}x is within acceptable range for "
                f"{growth_pct:.0f}% growth. Premium of {premium_pct:.0%} to sector "
                f"({sector_pe:.1f}x) appears earnings-supported rather than speculative."
            )
        elif implied_peg < 2.5 and premium_pct < 0.80:
            classification = "EXECUTION_DEPENDENT_PREMIUM"
            label = "Execution-Dependent Premium"
            rationale = (
                f"Premium of {premium_pct:.0%} over sector P/E ({sector_pe:.1f}x) requires "
                f"sustained {growth_pct:.0f}% growth to remain justified "
                f"(implied PEG: {implied_peg:.2f}x). "
                "Deceleration in growth or margin compression would compress multiple."
            )
        else:
            classification = "SPECULATIVE_PREMIUM"
            label = "Speculative Premium"
            rationale = (
                f"Implied PEG of {implied_peg:.2f}x at {growth_pct:.0f}% growth implies "
                "premium is not fully supported by current fundamentals. "
                "Re-rating risk is elevated if growth disappoints."
            )

        return {
            "classification": classification,
            "label": label,
            "implied_peg": round(implied_peg, 2),
            "rationale": rationale,
            "premium_pct_vs_sector": round(premium_pct, 4),
        }

    def _create_scenarios(
        self,
        fair_value_mid: float,
        fair_value_low: float,
        fair_value_high: float,
        current_price: float,
        sector_pe: float,
        normalized_eps: Optional[float],
        ttm_eps: Optional[float],
        spread_factor: float,
        confidence_score: int,
        confidence_label: str,
        uncertainty_drivers: List[str],
        deviation_pct: float,
        methodology_used: str,
        fv_pe: Optional[float] = None,
        fv_ev_ebitda: Optional[float] = None,
        fv_dcf: Optional[float] = None,
        revenue_growth: Optional[float] = None,
    ) -> PriceTargetScenarios:
        """
        Build the final PriceTargetScenarios output.

        The intrinsic value band (fair_value_low/mid/high) represents where the
        model believes the stock is worth.  The scenario targets (bear/base/bull)
        reflect expected price outcomes under different macro / business conditions
        and are spread around the same midpoint using the dynamic spread_factor.
        """
        # Scenario targets (macro spread around fair value midpoint)
        bull_target = fair_value_mid * (1 + spread_factor)
        bear_target = fair_value_mid * (1 - spread_factor)
        bull_target = max(bull_target, fair_value_mid * 1.05)
        bear_target = min(bear_target, fair_value_mid * 0.95)

        # P0: Enforce structural ordering bear < base < bull
        bear_target, base_target_final, bull_target, chain_violations = self._validate_valuation_chain(
            fair_value_mid=fair_value_mid,
            bear_target=bear_target,
            base_target=fair_value_mid,
            bull_target=bull_target,
        )
        # Append any chain violations to uncertainty drivers
        if chain_violations:
            uncertainty_drivers = list(uncertainty_drivers) + chain_violations
            logger.warning(f"Valuation chain violations corrected: {chain_violations}")

        spread_pct = f"{spread_factor:.0%}"

        # P2: Compute cross-method dispersion
        valid_fvs = {k: v for k, v in [("pe", fv_pe), ("ev_ebitda", fv_ev_ebitda), ("dcf", fv_dcf)] if v is not None}
        valuation_dispersion_pct = None
        valuation_dispersion_label = None
        if len(valid_fvs) >= 2 and fair_value_mid > 0:
            vals = list(valid_fvs.values())
            valuation_dispersion_pct = round((max(vals) - min(vals)) / fair_value_mid, 4)
            if valuation_dispersion_pct < 0.15:
                valuation_dispersion_label = "Low"
            elif valuation_dispersion_pct < 0.35:
                valuation_dispersion_label = "Moderate"
            else:
                valuation_dispersion_label = "High"

        # P2: Compute premium justification (if we have EPS to derive current P/E)
        premium_justification = None
        if current_price and ttm_eps and ttm_eps > 0:
            current_pe = current_price / ttm_eps
            premium_justification = self._justify_premium(
                current_pe=current_pe,
                sector_pe=sector_pe,
                revenue_growth=revenue_growth,
            )

        # EPS transparency note
        eps_note = ""
        if normalized_eps and ttm_eps and abs(normalized_eps - ttm_eps) > 0.10 * abs(ttm_eps):
            eps_note = f" (normalized EPS ${normalized_eps:.2f} vs TTM ${ttm_eps:.2f})"
        elif normalized_eps:
            eps_note = f", normalized EPS=${normalized_eps:.2f}"

        # Probabilistic framing for assumptions (no deterministic language)
        premium_vs_mid = (current_price - fair_value_mid) / fair_value_mid if fair_value_mid else 0.0
        if current_price > fair_value_high:
            price_context = (
                f"Price Above Intrinsic Value Estimate Band (+{premium_vs_mid:.0%} vs midpoint) — "
                "Execution Discount Zone requires pullback to restore margin of safety"
            )
        elif current_price < fair_value_low:
            price_context = (
                f"Price Below Intrinsic Value Estimate Band ({premium_vs_mid:.0%} vs midpoint) — "
                "Execution Discount Zone active; current price within or near target accumulation range"
            )
        else:
            price_context = (
                f"Price Within Intrinsic Value Estimate Band ({premium_vs_mid:+.0%} vs midpoint) — "
                "Execution Discount Zone at or near current price; scale-in approach recommended"
            )

        base_assumptions = (
            f"Continuation Scenario: Intrinsic Value Estimate midpoint ${fair_value_mid:.2f} "
            f"using {sector_pe:.1f}x sector P/E{eps_note}. "
            f"{methodology_used}. Confidence: {confidence_score}/100 ({confidence_label}). "
            f"{price_context}. "
            "Represents the probability-weighted base path — business executes as modeled "
            "with no significant multiple expansion or contraction."
        )
        bull_assumptions = (
            f"Re-rating Scenario (+{spread_pct}): {sector_pe*1.1:.1f}x P/E with margin improvement and "
            "market share gains. Market recognizes fundamental value — multiple expansion from current levels. "
            "Represents a probabilistic outcome path, not a direct fair value forecast."
        )
        bear_assumptions = (
            f"Risk Scenario (−{spread_pct}): {sector_pe*0.9:.1f}x P/E with competitive pressure or "
            "margin headwinds. Represents the downside probabilistic outcome path — "
            "thesis partially invalidated; fundamental delivery falls short of the Continuation Scenario."
        )

        # Compute both deviation metrics
        deviation_vs_price = (current_price - fair_value_mid) / current_price if current_price else 0.0

        if current_price > fair_value_high:
            price_vs_zone = "Price Above Intrinsic Value Band"
        elif current_price < fair_value_low:
            price_vs_zone = "Price Below Intrinsic Value Band"
        else:
            price_vs_zone = "Within Intrinsic Value Band"

        prob_weighted_ev = round(
            bear_target * 0.25 + base_target_final * 0.50 + bull_target * 0.25, 2
        )

        return PriceTargetScenarios(
            # Intrinsic value range
            fair_value_low=fair_value_low,
            fair_value_mid=round(fair_value_mid, 2),
            fair_value_high=fair_value_high,
            fair_value_zone_label="Intrinsic Value Zone",
            # Confidence
            confidence_score=confidence_score,
            confidence=confidence_label,
            uncertainty_drivers=uncertainty_drivers[:6],
            # Price vs. zone
            premium_vs_mid=round(premium_vs_mid, 4),
            deviation_vs_price=round(deviation_vs_price, 4),
            price_vs_zone=price_vs_zone,
            # Scenario targets (validated chain: bear < base < bull)
            base_target=round(base_target_final, 2),
            base_assumptions=base_assumptions,
            base_probability=0.50,
            bull_target=round(bull_target, 2),
            bull_assumptions=bull_assumptions,
            bull_probability=0.25,
            bear_target=round(bear_target, 2),
            bear_assumptions=bear_assumptions,
            bear_probability=0.25,
            methodology=methodology_used,
            # P2: Cross-method dispersion
            valuation_dispersion_pct=valuation_dispersion_pct,
            valuation_dispersion_label=valuation_dispersion_label,
            method_values={k: round(v, 2) for k, v in valid_fvs.items()} if valid_fvs else None,
            # P2: Probability-weighted expected value
            probability_weighted_ev=prob_weighted_ev,
            # P2: Premium justification
            premium_justification=premium_justification,
            # P0: Chain validation notes
            chain_validation_notes=chain_violations if chain_violations else None,
        )

    def _create_uncertainty_scenarios(self, current_price: float) -> PriceTargetScenarios:
        """Create scenarios when valuation uncertainty is too high to model reliably."""
        # Band is wide (±40%) reflecting low confidence; midpoint anchored at current price
        # because the model deviation was too extreme to trust
        fv_mid = round(current_price, 2)
        fv_low = round(current_price * 0.60, 2)
        fv_high = round(current_price * 1.40, 2)
        return PriceTargetScenarios(
            fair_value_low=fv_low,
            fair_value_mid=fv_mid,
            fair_value_high=fv_high,
            fair_value_zone_label="Intrinsic Value Zone",
            confidence_score=10,
            confidence="Low",
            uncertainty_drivers=[
                "Calculated intrinsic value deviated more than 100% from market price — likely a data quality issue",
                "Model inputs may be missing or unreliable (EPS, EBITDA, FCF)",
                "Wide band (±40%) reflects near-complete valuation uncertainty",
                "Use analyst consensus or comparable company analysis as primary reference",
            ],
            premium_vs_mid=0.0,
            deviation_vs_price=0.0,
            price_vs_zone="Within Intrinsic Value Band",
            base_target=fv_mid,
            base_assumptions=(
                "High Valuation Uncertainty — model deviation exceeded reliability threshold. "
                "Intrinsic midpoint anchored to current price; wide band reflects model uncertainty."
            ),
            base_probability=0.50,
            bull_target=round(current_price * 1.10, 2),
            bull_assumptions="Re-rating Scenario: +10% from current price (probabilistic path, not a fair value forecast)",
            bull_probability=0.25,
            bear_target=round(current_price * 0.90, 2),
            bear_assumptions="Risk Scenario: −10% from current price (probabilistic path, not a fair value forecast)",
            bear_probability=0.25,
            methodology="Market Price (High Uncertainty — model unreliable)",
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
