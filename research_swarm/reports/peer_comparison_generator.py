"""
Peer comparison generator for stock analysis reports.

Uses yfinance sector/industry data + curated peer maps
to generate competitive positioning analysis.
"""
from typing import Dict, Any, Optional, List
from research_swarm.logger import logger
from research_swarm.data.cache import cache


# Curated peer maps for major companies by industry niche
PEER_MAP = {
    # Mega-cap tech
    "AAPL": ["MSFT", "GOOGL", "AMZN", "META"],
    "MSFT": ["AAPL", "GOOGL", "AMZN", "ORCL"],
    "GOOGL": ["META", "MSFT", "AMZN", "SNAP"],
    "AMZN": ["MSFT", "GOOGL", "WMT", "SHOP"],
    "META": ["GOOGL", "SNAP", "PINS", "MSFT"],
    # Semiconductors
    "NVDA": ["AMD", "INTC", "AVGO", "QCOM"],
    "AMD": ["NVDA", "INTC", "QCOM", "MRVL"],
    "INTC": ["AMD", "NVDA", "TXN", "QCOM"],
    "AVGO": ["QCOM", "TXN", "MRVL", "NVDA"],
    "QCOM": ["AVGO", "MRVL", "AMD", "TXN"],
    "TSM": ["INTC", "NVDA", "ASML", "UMC"],
    # Software
    "CRM": ["ORCL", "SAP", "NOW", "WDAY"],
    "ORCL": ["CRM", "SAP", "MSFT", "IBM"],
    "NOW": ["CRM", "WDAY", "SNOW", "DDOG"],
    # EV / Auto
    "TSLA": ["GM", "F", "RIVN", "NIO"],
    # Financials
    "JPM": ["BAC", "GS", "MS", "WFC"],
    "BAC": ["JPM", "WFC", "C", "USB"],
    "GS": ["MS", "JPM", "BAC", "SCHW"],
    "V": ["MA", "PYPL", "AXP", "SQ"],
    "MA": ["V", "PYPL", "AXP", "FIS"],
    # Healthcare
    "JNJ": ["PFE", "ABBV", "MRK", "LLY"],
    "UNH": ["CVS", "CI", "ELV", "HUM"],
    "LLY": ["NVO", "MRK", "ABBV", "PFE"],
    # Energy
    "XOM": ["CVX", "COP", "SLB", "EOG"],
    "CVX": ["XOM", "COP", "SLB", "OXY"],
    # Consumer
    "KO": ["PEP", "MNST", "STZ", "KDP"],
    "PEP": ["KO", "MNST", "STZ", "KDP"],
    "WMT": ["COST", "TGT", "AMZN", "KR"],
    "COST": ["WMT", "TGT", "BJ", "KR"],
    # Industrials
    "CAT": ["DE", "CMI", "PCAR", "EMR"],
    "BA": ["LMT", "RTX", "GD", "NOC"],
    # Specialty
    "GLW": ["II-VI", "COHR", "LITE", "KEYS"],
    "DIS": ["NFLX", "CMCSA", "WBD", "PARA"],
    "NFLX": ["DIS", "CMCSA", "WBD", "ROKU"],
}

# Competitive position heuristics by market cap rank within peers
POSITION_MAP = {
    0: "Market Leader",
    1: "Strong #2",
    2: "Challenger",
    3: "Challenger",
}


class PeerComparisonGenerator:
    """Generates peer comparison data for stock reports."""

    def generate(
        self,
        ticker: str,
        moat_score: float,
        enhanced_moat: Optional[Dict[str, Any]] = None,
        valuation_metrics: Optional[Dict[str, Any]] = None,
        vgm_scores: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate peer comparison for a ticker.

        Args:
            ticker: Stock ticker
            moat_score: Overall moat score
            enhanced_moat: Enhanced moat breakdown
            valuation_metrics: Valuation metrics dict
            vgm_scores: VGM scores dict

        Returns:
            Dict matching PeerComparison model fields, or None
        """
        ticker = ticker.upper()
        cache_key = f"{ticker}_peer_comparison"

        cached = cache.get("peer_comparison", cache_key)
        if cached:
            return cached

        try:
            from research_swarm.data.market_data_client import market_data_client

            # Get company info for sector/industry
            info = market_data_client.get_company_info(ticker)
            if not info:
                logger.warning(f"No company info for {ticker}, skipping peer comparison")
                return None

            sector = info.get("sector", "Unknown")
            industry = info.get("industry", "Unknown")

            # Get peers from curated map or sector lookup
            peers = self._get_peers(ticker, sector, industry)
            if not peers:
                logger.warning(f"No peers found for {ticker}")
                return None

            # Determine competitive position
            competitive_position = self._assess_position(ticker, peers, info)

            # Determine moat direction from enhanced moat
            moat_direction = "Stable"
            if enhanced_moat:
                durability = enhanced_moat.get("moat_durability", "medium")
                width = enhanced_moat.get("moat_width", "narrow")
                if durability == "high" and width in ("wide", "Wide"):
                    moat_direction = "Widening"
                elif durability == "low" or width in ("none", "None"):
                    moat_direction = "Narrowing"

            # Estimate competitive intensity from sector
            competitive_intensity = self._estimate_intensity(sector, industry)

            # Derive pricing power evidence from moat
            pricing_power = self._derive_pricing_power(enhanced_moat, moat_score)

            # Key threats from risk assessment
            key_threats = self._derive_threats(sector, industry, competitive_intensity)

            result = {
                "sector": sector,
                "industry": industry,
                "peers": peers[:4],
                "competitive_position": competitive_position,
                "market_share_estimate": None,  # Would need external data
                "competitive_intensity": competitive_intensity,
                "moat_direction": moat_direction,
                "pricing_power_evidence": pricing_power,
                "key_threats": key_threats,
                "top_competitor": peers[0] if peers else None,
                "market_share_rank": None,
                # Ranks would require fetching peer financials — skip for now
                "revenue_growth_rank": None,
                "profit_margin_rank": None,
                "roic_rank": None,
                "valuation_rank": None,
            }

            cache.set("peer_comparison", cache_key, result, ttl_days=7)
            logger.info(f"Generated peer comparison for {ticker}: {peers[:4]}, {competitive_position}")
            return result

        except Exception as e:
            logger.warning(f"Peer comparison generation failed for {ticker}: {e}")
            return None

    def _get_peers(self, ticker: str, sector: str, industry: str) -> List[str]:
        """Get peer tickers from curated map or sector fallback."""
        # Try curated map first
        if ticker in PEER_MAP:
            return PEER_MAP[ticker]

        # Fallback: use sector ETF constituents (simplified)
        sector_peers = {
            "Technology": ["AAPL", "MSFT", "GOOGL", "NVDA"],
            "Healthcare": ["JNJ", "UNH", "PFE", "ABBV"],
            "Financials": ["JPM", "BAC", "GS", "V"],
            "Consumer Discretionary": ["AMZN", "TSLA", "HD", "NKE"],
            "Consumer Staples": ["PG", "KO", "PEP", "COST"],
            "Energy": ["XOM", "CVX", "COP", "SLB"],
            "Industrials": ["CAT", "HON", "UPS", "BA"],
            "Materials": ["LIN", "APD", "SHW", "FCX"],
            "Utilities": ["NEE", "DUK", "SO", "D"],
            "Real Estate": ["PLD", "AMT", "CCI", "EQIX"],
            "Communication Services": ["META", "GOOGL", "DIS", "NFLX"],
        }

        peers = sector_peers.get(sector, [])
        # Remove self from peers
        peers = [p for p in peers if p != ticker]
        return peers[:4]

    def _assess_position(
        self, ticker: str, peers: List[str], info: Dict[str, Any]
    ) -> str:
        """Assess competitive position based on market cap rank."""
        our_cap = info.get("market_cap", 0) or 0

        if not our_cap:
            return "Challenger"

        try:
            from research_swarm.data.market_data_client import market_data_client

            # Get peer market caps
            all_caps = [(ticker, our_cap)]
            for peer in peers[:3]:  # Limit API calls
                peer_info = market_data_client.get_company_info(peer)
                if peer_info:
                    all_caps.append((peer, peer_info.get("market_cap", 0) or 0))

            # Sort by market cap descending
            all_caps.sort(key=lambda x: x[1], reverse=True)

            # Find our rank
            our_rank = next(
                i for i, (t, _) in enumerate(all_caps) if t == ticker
            )

            return POSITION_MAP.get(our_rank, "Challenger")

        except Exception:
            return "Challenger"

    def _estimate_intensity(self, sector: str, industry: str) -> str:
        """Estimate competitive intensity from sector/industry."""
        high_intensity = [
            "Consumer Electronics", "Semiconductors", "Internet Retail",
            "Software—Application", "Telecom", "Airlines",
        ]
        low_intensity = [
            "Utilities", "Water Utilities", "Drug Manufacturers",
            "Insurance—Diversified", "Railroads",
        ]

        industry_lower = industry.lower()
        for h in high_intensity:
            if h.lower() in industry_lower:
                return "High"
        for l in low_intensity:
            if l.lower() in industry_lower:
                return "Low"
        return "Moderate"

    def _derive_pricing_power(
        self, enhanced_moat: Optional[Dict[str, Any]], moat_score: float
    ) -> List[str]:
        """Derive pricing power evidence from moat analysis."""
        evidence = []
        if not enhanced_moat:
            if moat_score >= 7.0:
                evidence.append("Strong overall moat suggests pricing power")
            return evidence or ["Limited pricing power evidence"]

        if enhanced_moat.get("brand_power", 0) >= 7:
            evidence.append("Strong brand enables premium pricing")
        if enhanced_moat.get("switching_costs", 0) >= 7:
            evidence.append("High switching costs reduce price sensitivity")
        if enhanced_moat.get("network_effects", 0) >= 7:
            evidence.append("Network effects create pricing leverage")
        if enhanced_moat.get("regulatory_barriers", 0) >= 7:
            evidence.append("Regulatory barriers limit competitive pricing pressure")

        return evidence or ["Moderate pricing power based on competitive position"]

    def _derive_threats(
        self, sector: str, industry: str, intensity: str
    ) -> List[str]:
        """Derive key competitive threats."""
        threats = []

        if intensity in ("High", "Extreme"):
            threats.append("Intense competition could compress margins")

        sector_threats = {
            "Technology": "Rapid technological disruption and shorter product cycles",
            "Healthcare": "Regulatory and reimbursement risks",
            "Financials": "Interest rate sensitivity and credit cycle exposure",
            "Energy": "Energy transition and commodity price volatility",
            "Consumer Discretionary": "Consumer spending sensitivity to macro conditions",
            "Consumer Staples": "Private label competition and input cost inflation",
            "Industrials": "Cyclical demand and supply chain disruptions",
        }
        if sector in sector_threats:
            threats.append(sector_threats[sector])

        threats.append("New market entrants with disruptive business models")

        return threats[:3]


# Global instance
peer_comparison_generator = PeerComparisonGenerator()
