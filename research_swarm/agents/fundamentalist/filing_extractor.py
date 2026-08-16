"""Per-filing structured extraction, cached by SEC accession number (Phase B).

Replaces the single mega-prompt that sent all four quarters' filing sections
to Haiku on every analysis. Each filing is extracted exactly once — a filing
is immutable, so its extraction is keyed by accession number and cached for a
year in Neon (shared across users) plus local SQLite. A warm analysis of a
ticker performs ZERO filing-extraction LLM calls until a new filing lands.

Design differences vs the old mega-call, both accuracy wins:
- The old prompt labeled a 10-K's sections "Q4" and asked the model for
  quarterly figures, so full-year totals could silently masquerade as Q4.
  Here the annual filing is extracted as fiscal-year totals (plus explicit
  Q4 figures only when the filing presents them), and Q4 is DERIVED in
  Python: FY minus the prior-year comparative quarters that each 10-Q
  reports (see ttm_aggregator).
- TTM sums, margins, and trends are computed in Python, not by the model.

The extraction also carries risk factors, growth drivers, management outlook,
and DCF inputs, so the DCF stage reads the same cached extraction instead of
making its own Haiku call.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from research_swarm.logger import logger
from research_swarm.config import settings
from research_swarm.utils import extract_token_usage
from research_swarm.data.cache import cache
from research_swarm.data.data_cache_service import data_cache

MAX_FILING_CHARS = 30000
_SQLITE_NAMESPACE = "filing_extraction_v1"

_EXTRACTION_SYSTEM = (
    "You are extracting structured data from a single SEC filing. "
    "All monetary figures are in millions of USD. Use null for anything the "
    "filing does not state. Return ONLY a valid JSON object:\n\n"
    "{\n"
    '  "period_type": "quarter" | "fiscal_year",\n'
    '  "metrics": {\n'
    '    "revenue": <float or null>,\n'
    '    "gross_profit": <float or null>,\n'
    '    "operating_income": <float or null>,\n'
    '    "net_income": <float or null>,\n'
    '    "operating_cash_flow": <float or null>,\n'
    '    "free_cash_flow": <float or null>\n'
    "  },\n"
    '  "prior_year_metrics": {"revenue": <float or null>, "net_income": <float or null>},\n'
    '  "q4_metrics": {<same keys as metrics>} | null,\n'
    '  "risk_factors": ["<top risk 1>", ..., "<top risk 5>"],\n'
    '  "growth_drivers": ["<driver 1>", "<driver 2>", "<driver 3>"],\n'
    '  "management_outlook": "<summary of forward guidance>",\n'
    '  "dcf": {\n'
    '    "fcf_history": [<annual FCF in millions, oldest to newest, 3-5 years>],\n'
    '    "revenue_growth_rate": <most recent YoY revenue growth %>,\n'
    '    "operating_margin_trend": "<expanding|stable|contracting>",\n'
    '    "capex_as_pct_revenue": <float>,\n'
    '    "effective_tax_rate": <float>,\n'
    '    "total_debt": <float millions>,\n'
    '    "cash_and_equivalents": <float millions>,\n'
    '    "shares_outstanding": <diluted shares, millions>\n'
    "  } | null\n"
    "}\n\n"
    "Rules:\n"
    "- QUARTERLY filings (10-Q, 6-K): period_type=\"quarter\". `metrics` are the "
    "THREE-MONTH figures for the quarter just ended (not year-to-date). "
    "`prior_year_metrics` are the comparative three-month figures for the same "
    "quarter one year earlier, as shown in the filing's comparative statements. "
    "`q4_metrics` is null. `dcf` is null.\n"
    "- ANNUAL filings (10-K, 20-F): period_type=\"fiscal_year\". `metrics` are the "
    "FULL fiscal-year totals. `prior_year_metrics` are the prior fiscal year's "
    "totals. `q4_metrics` holds fourth-quarter THREE-MONTH figures ONLY if the "
    "filing explicitly presents quarterly data; otherwise null — never derive "
    "them yourself. Fill `dcf` from the multi-year statements.\n"
    "- Never mix year-to-date and three-month figures.\n"
)


class FilingExtractor:
    """One Haiku call per filing, cached forever by accession number."""

    def __init__(self):
        self.haiku = ChatAnthropic(
            model="claude-haiku-4-5-20251001",
            api_key=settings.anthropic_api_key,
            temperature=0.0,
            max_tokens=8192,
        )
        logger.info("FilingExtractor initialized")

    def extract(
        self,
        ticker: str,
        quarter_label: str,
        filing: Dict[str, Any],
        parsed_sections: Dict[str, str],
    ) -> Tuple[Optional[Dict[str, Any]], int]:
        """Extract one filing. Returns (extraction dict, tokens_used).

        Cache order: local SQLite → shared Neon → LLM. Tokens are 0 on any
        cache hit. Returns (None, tokens) when extraction fails.
        """
        accession = filing.get("accession_number")
        filing_type = filing.get("filing_type", "10-K")

        if accession:
            cached = cache.get(_SQLITE_NAMESPACE, accession)
            if cached:
                logger.debug(f"[FilingExtract] SQLite HIT {accession}")
                return cached, 0
            cached = data_cache.get_filing_extraction(accession)
            if cached:
                logger.debug(f"[FilingExtract] Neon HIT {accession}")
                cache.set(_SQLITE_NAMESPACE, accession, cached, ttl_days=365)
                return cached, 0
        else:
            logger.warning(
                f"[FilingExtract] No accession number for {ticker} {quarter_label} — "
                "extraction will not be cached"
            )

        section_text = "\n\n".join(
            f"**{name}**\n{text}" for name, text in parsed_sections.items()
        )[:MAX_FILING_CHARS]

        messages = [
            SystemMessage(content=[{
                "type": "text",
                "text": _EXTRACTION_SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }]),
            HumanMessage(content=[{
                "type": "text",
                "text": (
                    f"Company: {ticker}\n"
                    f"Filing Type: {filing_type}\n"
                    f"Period Label: {quarter_label}\n\n"
                    f"Filing Sections (truncated):\n{section_text}"
                ),
                "cache_control": {"type": "ephemeral"},
            }]),
        ]

        tokens_used = 0
        try:
            response = self.haiku.invoke(messages)
            tokens_used = extract_token_usage(response.response_metadata)
            extraction = json.loads(_extract_json(response.content.strip()))
            extraction["accession_number"] = accession
            extraction["filing_type"] = filing_type
            extraction["quarter_label"] = quarter_label

            if accession:
                cache.set(_SQLITE_NAMESPACE, accession, extraction, ttl_days=365)
                data_cache.set_filing_extraction(accession, extraction)

            logger.success(
                f"✓ Extracted filing {quarter_label} ({filing_type}, {tokens_used} tokens)"
            )
            return extraction, tokens_used

        except json.JSONDecodeError as e:
            logger.error(f"[FilingExtract] JSON parse failed for {ticker} {quarter_label}: {e}")
            return None, tokens_used
        except Exception as e:
            logger.error(f"[FilingExtract] Extraction failed for {ticker} {quarter_label}: {e}")
            return None, tokens_used


def _extract_json(text: str) -> str:
    """Pull the JSON object out of a response that may carry fences/preamble."""
    text = text.strip()
    if text.startswith("```"):
        # strip markdown fences
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise json.JSONDecodeError("no JSON object found", text, 0)
    return text[start : end + 1]


filing_extractor = FilingExtractor()
