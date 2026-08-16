"""
Return on invested capital.

Owned by its own module because two callers need it — the quality score inside
the blended valuation, and the ROIC-vs-WACC spread score in the fundamentalist
graph — and those two modules already import each other in one direction.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from research_swarm.logger import logger


def quarterly_to_annual_fcf(quarterly_asc: List[float]) -> List[float]:
    """Fold a quarterly FCF series into non-overlapping annual totals.

    `DCFInputs.fcf_history` is defined as ANNUAL free cash flow in millions,
    and `DCFCalculator` takes `fcf_history[-1]` as the base cash flow it grows
    and discounts for five years. When the LLM extraction missed, the fallback
    filled that field straight from `get_quarterly_financials()` — QUARTERLY
    rows — so a single quarter was projected as if it were a full year,
    understating the DCF leg by roughly 4x. The result still cleared the
    calculator's own sanity floor, so it silently dragged fair value down at
    15-50% weight while the run reported "DCF supported by real FCF history".

    Args:
        quarterly_asc: quarterly FCF, oldest first.

    Returns:
        Annual totals, oldest first. Groups of four are taken from the MOST
        RECENT quarter backwards, so the newest entry is a true trailing-twelve-
        month figure and any remainder is dropped from the oldest end rather
        than corrupting the base year. Fewer than four quarters returns [].
    """
    if not quarterly_asc or len(quarterly_asc) < 4:
        return []

    annuals: List[float] = []
    end = len(quarterly_asc)
    while end - 4 >= 0:
        annuals.append(round(sum(quarterly_asc[end - 4:end]), 2))
        end -= 4
    return list(reversed(annuals))

# Cash beyond this share of revenue is treated as excess rather than as
# working capital financing the business.
OPERATING_CASH_PCT_OF_REVENUE = 0.02

DEFAULT_TAX_RATE = 0.21


def compute_roic(
    stock_info: Dict[str, Any],
    tax_rate: float = DEFAULT_TAX_RATE,
) -> Tuple[Optional[float], Optional[str]]:
    """Return (ROIC as a decimal, method label), or (None, None).

        NOPAT            = revenue x operating margin x (1 - tax rate)
        invested capital = total debt + book equity - excess cash
        ROIC             = NOPAT / invested capital

    This replaces `returnOnEquity`, which the codebase previously used as a
    "ROIC proxy". ROE is a LEVERED return measured over BOOK equity, and book
    equity is an accounting residual that sustained buybacks drive toward — or
    below — zero. Live data shows exactly what that does: Home Depot posts a
    128% ROE on $13.9B of book equity against $63.7B of debt, while Texas
    Instruments, a genuinely high-return business, posts 35%. Both mapped to
    the same 9.5/10 "clear structural moat". McDonald's, with negative book
    equity, yielded no score at all.

    Putting debt in the denominator means leverage no longer flatters the
    return, and a company with negative book equity still has a positive
    capital base — so the metric can finally separate financial engineering
    from an economic moat, which is the only thing it exists to measure.

    Returns None when any input is missing. Callers must NOT fall back to ROE:
    substituting a levered return against a WACC hurdle is the original bug.
    """
    revenue = stock_info.get("totalRevenue")
    op_margin = stock_info.get("operatingMargins")
    if not revenue or revenue <= 0 or op_margin is None:
        return None, None

    nopat = revenue * op_margin * (1 - tax_rate)

    book_value_per_share = stock_info.get("bookValue")
    shares = stock_info.get("sharesOutstanding")
    if book_value_per_share is None or not shares:
        return None, None
    equity = book_value_per_share * shares

    total_debt = stock_info.get("totalDebt") or 0
    cash = stock_info.get("totalCash") or 0
    excess_cash = max(0.0, cash - OPERATING_CASH_PCT_OF_REVENUE * revenue)

    invested_capital = total_debt + equity - excess_cash
    if invested_capital <= 0:
        logger.debug(
            f"Invested capital non-positive (debt={total_debt}, equity={equity}, "
            f"excess_cash={excess_cash}) — ROIC not computable"
        )
        return None, None

    return nopat / invested_capital, "NOPAT / invested capital"
