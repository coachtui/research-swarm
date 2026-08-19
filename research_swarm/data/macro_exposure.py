"""
Macro exposure resolution — which shared themes actually reach THIS company.

The macro brief is deliberately company-neutral so it can be computed once and
shared. This module is the join: given a company's sector, region, and supply
chain, it decides which themes are materially relevant and how strong the link
is. Everything here is deterministic — no LLM — so the same company and the
same brief always resolve to the same exposure set.

Filtering matters as much as the brief itself. If every report recited every
theme, the macro section would read as boilerplate and readers would learn to
skip it. A theme earns its place in a report only when there is a concrete
channel connecting it to the company.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from research_swarm.logger import logger

# Map a company's yfinance country onto the brief's region vocabulary.
_COUNTRY_TO_REGION = {
    "United States": "United States",
    "Canada": "United States",      # North American macro bloc
    "Japan": "Japan",
    "China": "China",
    "Hong Kong": "China",
    "South Korea": "South Korea",
    "Taiwan": "Taiwan",
    "Germany": "Europe", "France": "Europe", "United Kingdom": "Europe",
    "Netherlands": "Europe", "Switzerland": "Europe", "Ireland": "Europe",
    "Spain": "Europe", "Italy": "Europe", "Sweden": "Europe", "Denmark": "Europe",
    "Israel": "Middle East", "Saudi Arabia": "Middle East",
    "India": "Emerging Markets", "Brazil": "Emerging Markets",
    "Mexico": "Emerging Markets", "South Africa": "Emerging Markets",
}

# Industries with structurally heavy exposure to a given transmission channel,
# regardless of sector label. Keyword-matched against the yfinance industry.
_INDUSTRY_CHANNELS = {
    "energy_input": ("airline", "chemical", "shipping", "marine", "trucking",
                     "steel", "aluminum", "cement", "utilities", "packaging"),
    "rates": ("bank", "insurance", "reit", "real estate", "mortgage",
              "capital markets", "asset management", "credit"),
    "trade_supply": ("semiconductor", "electronic", "hardware", "auto",
                     "machinery", "aerospace", "apparel", "retail"),
    "currency": ("semiconductor", "luxury", "pharmaceutical", "consumer electronics"),
}


def _region_for_country(country: Optional[str]) -> Optional[str]:
    if not country:
        return None
    return _COUNTRY_TO_REGION.get(country.strip())


def _industry_channels(industry: Optional[str]) -> List[str]:
    if not industry:
        return []
    lowered = industry.lower()
    return [
        channel
        for channel, keywords in _INDUSTRY_CHANNELS.items()
        if any(kw in lowered for kw in keywords)
    ]


def _theme_channels(theme: Dict[str, Any]) -> List[str]:
    """Infer which transmission channels a theme runs through, from its text."""
    text = f"{theme.get('name', '')} {theme.get('transmission', '')} {theme.get('summary', '')}".lower()
    channels = []
    if any(k in text for k in ("oil", "energy price", "gas", "fuel", "opec", "electricity", "power")):
        channels.append("energy_input")
    if any(k in text for k in ("rate", "yield", "monetary", "central bank", "inflation", "credit", "financing")):
        channels.append("rates")
    if any(k in text for k in ("tariff", "trade", "sanction", "export control", "supply chain",
                               "shipping", "strait", "blockade", "port")):
        channels.append("trade_supply")
    if any(k in text for k in ("currency", "dollar", "yen", "fx", "exchange rate", "devalu")):
        channels.append("currency")
    return channels


def resolve_exposure(
    macro_context: Dict[str, Any],
    sector: Optional[str],
    industry: Optional[str] = None,
    country: Optional[str] = None,
    supply_chain_regions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Select the themes that materially reach this company.

    Returns the relevant themes annotated with WHY each one applies, plus the
    market state (which always applies — every equity has beta).
    """
    brief = (macro_context or {}).get("brief") or {}
    themes = brief.get("themes") or []

    company_region = _region_for_country(country)
    company_channels = _industry_channels(industry)
    supply_regions = set(supply_chain_regions or [])

    relevant: List[Dict[str, Any]] = []
    for theme in themes:
        links: List[str] = []
        strength = 0.0

        theme_sectors = theme.get("affected_sectors") or []
        theme_regions = theme.get("affected_regions") or []

        # Specificity weighting. A theme touching nine sectors says far less
        # about any one company than a theme touching one. Without this, broad
        # themes attach to every ticker and the macro section becomes the same
        # paragraph in every report.
        def _specificity(items: List[str]) -> float:
            n = len([i for i in items if i != "Global"])
            if n <= 0:
                return 0.3
            if n <= 2:
                return 1.0
            if n <= 4:
                return 0.6
            return 0.3

        # Sector link — the most reliable signal we have.
        if sector and sector in theme_sectors:
            weight = 2.0 * _specificity(theme_sectors)
            links.append(f"names the {sector} sector ({len(theme_sectors)} sectors affected)")
            strength += weight

        # Region link. Only counts when the theme's regional scope is actually
        # discriminating — "affects the United States" plus "is a US company"
        # is true of most themes and most companies, so it earns nothing.
        specific_regions = [r for r in theme_regions if r != "Global"]
        if company_region and company_region in specific_regions and len(specific_regions) <= 3:
            weight = 2.0 * _specificity(theme_regions)
            links.append(f"company is domiciled in {company_region}")
            strength += weight
        elif "Global" in theme_regions:
            links.append("global in scope")
            strength += 0.5

        overlapping_supply = supply_regions & set(theme_regions)
        if overlapping_supply:
            links.append(f"supply chain runs through {', '.join(sorted(overlapping_supply))}")
            strength += 2.0

        # Channel link — structural industry sensitivity. Specific and earned,
        # so it is weighted close to a sector match.
        shared_channels = set(company_channels) & set(_theme_channels(theme))
        if shared_channels:
            readable = {
                "energy_input": "energy input costs",
                "rates": "interest rates / financing",
                "trade_supply": "trade and supply availability",
                "currency": "currency translation",
            }
            named = ", ".join(readable[c] for c in sorted(shared_channels))
            links.append(f"industry is structurally sensitive to {named}")
            strength += 1.5

        # Geography alone is not a transmission channel. Being a US company
        # does not mean every theme touching the US reaches your P&L — that
        # reasoning attaches "AI capex financing scrutiny" to a beverage maker.
        # A theme must connect through the company's SECTOR, its structural
        # industry sensitivity, or its supply chain; region and global scope
        # only modulate the strength of a link that already exists.
        has_real_channel = bool(
            (sector and sector in theme_sectors)
            or shared_channels
            or overlapping_supply
        )
        if not has_real_channel:
            continue

        # A theme with no concrete channel to this company is dropped. Reciting
        # every theme in every report is what makes a macro section boilerplate.
        if strength < 2.0 or not links:
            continue

        annotated = dict(theme)
        annotated["relevance"] = "high" if strength >= 3.5 else "moderate"
        annotated["why_relevant"] = "; ".join(links)
        annotated["_strength"] = round(strength, 2)
        relevant.append(annotated)

    relevant.sort(key=lambda t: t.get("_strength", 0), reverse=True)
    for t in relevant:
        t.pop("_strength", None)
    relevant = relevant[:3]

    logger.info(
        f"[Macro] Exposure resolved: {len(relevant)}/{len(themes)} themes relevant "
        f"(sector={sector}, region={company_region}, channels={company_channels})"
    )

    return {
        "market": (macro_context or {}).get("market"),
        "themes": relevant,
        "backdrop": brief.get("summary", ""),
        "themes_considered": len(themes),
        "company_region": company_region,
    }


def format_macro_block(exposure: Dict[str, Any]) -> str:
    """Render the exposure for the manager's synthesis prompt."""
    if not exposure:
        return "Macro context unavailable for this run."

    market = exposure.get("market") or {}
    lines: List[str] = []

    regime = market.get("regime")
    if regime:
        lines.append(f"**Market regime**: {regime} — {market.get('regime_rationale', '')}")

    idx = market.get("indices") or {}
    idx_parts = [
        f"{m['label']} {m['return_1m']:+.1f}% 1M / {m['return_3m']:+.1f}% 3M"
        for m in idx.values()
        if m.get("return_1m") is not None and m.get("return_3m") is not None
    ]
    if idx_parts:
        lines.append("**Index moves**: " + " | ".join(idx_parts))

    risk = market.get("risk") or {}
    risk_parts = []
    for sym in ("^VIX", "^TNX", "DX-Y.NYB", "JPY=X", "CL=F", "GC=F"):
        m = risk.get(sym)
        if m and m.get("last") is not None:
            chg = f" ({m['return_1m']:+.1f}% 1M)" if m.get("return_1m") is not None else ""
            risk_parts.append(f"{m['label']} {m['last']}{chg}")
    if risk_parts:
        lines.append("**Rates / FX / commodities**: " + " | ".join(risk_parts))

    if market.get("yield_curve_slope") is not None:
        slope = market["yield_curve_slope"]
        shape = "inverted" if slope < 0 else "positively sloped"
        lines.append(f"**Yield curve (10Y−3M)**: {slope:+.2f}pp, {shape}")

    if market.get("sector_leaders"):
        lines.append(
            f"**Sector rotation (1M)**: leading — {', '.join(market['sector_leaders'])}; "
            f"lagging — {', '.join(market.get('sector_laggards') or [])}"
        )
    if market.get("region_leaders"):
        lines.append(
            f"**Regional performance (1M)**: leading — {', '.join(market['region_leaders'])}; "
            f"lagging — {', '.join(market.get('region_laggards') or [])}"
        )

    if exposure.get("backdrop"):
        lines.append(f"**Macro backdrop**: {exposure['backdrop']}")

    themes = exposure.get("themes") or []
    if themes:
        lines.append("")
        lines.append(
            f"**Live macro/geopolitical themes with a concrete channel to THIS company** "
            f"({len(themes)} of {exposure.get('themes_considered', 0)} screened):"
        )
        for t in themes:
            lines.append(
                f"- **{t['name']}** [{t['status']}, {t['direction']}, {t['relevance']} relevance, "
                f"confidence {t['confidence']}]\n"
                f"    What: {t.get('summary', '')}\n"
                f"    Transmission: {t.get('transmission', '')}\n"
                f"    Why it reaches this company: {t.get('why_relevant', '')}\n"
                f"    Evidence: {t.get('evidence', '')}"
            )
    else:
        lines.append("")
        lines.append(
            f"**Live macro/geopolitical themes**: none of the "
            f"{exposure.get('themes_considered', 0)} themes screened have a concrete channel to "
            "this company. Do not manufacture a macro angle."
        )

    return "\n".join(lines)
