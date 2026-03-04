"""
PIT Inputs Builder
==================

Converts PITFundamentals into the data structures expected by the DVRG
production signal pipeline (BlendedValuationCalculator, DCFInputs, etc.).

Currency handling
─────────────────
The ``_currency_normalized`` sentinel in ``stock_info`` is set **only** when
monetary values are confirmed to be in USD:

  • ``fund.reporting_currency == "USD"``
    → set ``financialCurrency="USD"`` (passes the blended_valuation USD guard
      via the ``already_usd`` branch — no sentinel needed)

  • ``fund.reporting_currency != "USD"`` AND ``fund.currency_converted == True``
    → FX conversion was already applied in ``_build_fundamentals()``; set
      ``_currency_normalized=True`` to confirm to the guard.

  • ``fund.reporting_currency != "USD"`` AND ``fund.currency_converted == False``
    → FX conversion FAILED (no rate available); monetary fields are still in
      native currency.  In this case we do NOT set the sentinel or USD flag,
      which causes ``validate_usd_normalized()`` to log a warning.  The
      valuation engine will still run but results are unreliable for that ticker.

No network calls.  No randomness.  Pure transformation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from scripts.backtest.data.fundamentals import PITFundamentals


# ── Public API ─────────────────────────────────────────────────────────────────


def build_stock_info(
    fund: PITFundamentals,
    current_price: float,
    beta: float,
) -> Dict[str, Any]:
    """
    Build a yfinance-compatible ``stock_info`` dict from PITFundamentals.

    Keys match what ``BlendedValuationCalculator.calculate_fair_value()``
    reads from ``stock_info``:
        trailingEps, ebitda, sharesOutstanding, totalDebt, cash,
        capitalExpenditures, revenueGrowth, beta, totalRevenue,
        sector, returnOnEquity, freeCashflow

    Notes:
    - ``ebitda`` is left as None because PITFundamentals stores only
      operating cash flow, not EBITDA.  The production engine skips the
      EV/EBITDA method gracefully when ebitda is None.
    - Currency sentinels are set based on ``fund.reporting_currency`` and
      ``fund.currency_converted`` — never hardcoded True.
    """
    roe_decimal = (fund.roe / 100.0) if fund.roe is not None else None
    rev_growth_decimal = (
        fund.revenue_growth_yoy / 100.0 if fund.revenue_growth_yoy is not None else None
    )

    # ── Currency sentinel logic ───────────────────────────────────────────────
    # Case 1: USD reporter → financialCurrency="USD" is sufficient
    # Case 2: Non-USD + converted → _currency_normalized=True confirms conversion
    # Case 3: Non-USD + NOT converted → no sentinel (guard will warn)
    reporting_ccy = (fund.reporting_currency or "USD").upper()
    if reporting_ccy == "USD":
        currency_guard = {"financialCurrency": "USD"}
    elif fund.currency_converted:
        # Conversion was applied; monetary fields are now in USD
        currency_guard = {"financialCurrency": "USD", "_currency_normalized": True}
    else:
        # Conversion failed; fields remain in native currency — warn but proceed
        currency_guard = {"financialCurrency": reporting_ccy}

    return {
        # ── Currency guard sentinels ──────────────────────────────────────────
        **currency_guard,
        # ── Per-share / TTM earnings ──────────────────────────────────────────
        "trailingEps": fund.eps_ttm,
        # ── EBITDA — not computable from quarterly income statement alone ─────
        "ebitda": None,
        # ── Capital structure ─────────────────────────────────────────────────
        "sharesOutstanding": fund.shares_raw,
        "totalDebt": fund.total_debt_raw,
        "cash": fund.cash_raw,
        # ── Cash flows ────────────────────────────────────────────────────────
        "freeCashflow": fund.fcf_ttm_raw,
        "capitalExpenditures": None,   # not tracked per-quarter in PITFundamentals
        # ── Revenue & growth ──────────────────────────────────────────────────
        "totalRevenue": fund.revenue_ttm_raw,
        "revenueGrowth": rev_growth_decimal,
        # ── Return metrics ────────────────────────────────────────────────────
        "returnOnEquity": roe_decimal,
        # ── Market / technical ────────────────────────────────────────────────
        "beta": beta,
        # ── Sector (unknown for historical; production engine defaults to non-financial)
        "sector": "Unknown",
    }


def build_valuation_metrics(
    fund: PITFundamentals,
    current_price: float,
) -> Dict[str, Any]:
    """
    Build the ``valuation_metrics`` dict for ``BlendedValuationCalculator``.

    Required keys: market_cap_millions, enterprise_value_millions,
                   pe_ratio, sector_avg_pe, sector_avg_ev_ebitda.

    Sector-average multiples use long-run S&P 500 medians (18× P/E,
    12× EV/EBITDA) since historical sector-level data is not available.
    """
    pe_ratio: Optional[float] = None
    if fund.eps_ttm is not None and fund.eps_ttm > 0 and current_price > 0:
        pe_ratio = current_price / fund.eps_ttm

    market_cap_millions: Optional[float] = None
    if fund.shares_raw and fund.shares_raw > 0 and current_price > 0:
        market_cap_millions = (fund.shares_raw * current_price) / 1_000_000

    # EV = market_cap + total_debt - cash  (if balance-sheet data available)
    ev_millions: Optional[float] = None
    if (
        market_cap_millions is not None
        and fund.total_debt_raw is not None
        and fund.cash_raw is not None
    ):
        ev_millions = (
            market_cap_millions
            + fund.total_debt_raw / 1_000_000
            - fund.cash_raw / 1_000_000
        )

    return {
        "current_price": current_price,
        "market_cap_millions": market_cap_millions,
        "enterprise_value_millions": ev_millions,
        "pe_ratio": pe_ratio,
        # Long-run S&P 500 median sector multiples (conservative defaults)
        "sector_avg_pe": 18.0,
        "sector_avg_ev_ebitda": 12.0,
        # valuation_category for DI risk-level fallback
        "valuation_category": _valuation_category(pe_ratio),
    }


def build_dcf_inputs(fund: PITFundamentals, current_price: Optional[float] = None):
    """
    Build a ``DCFInputs`` Pydantic model from PITFundamentals.

    ``fcf_history`` is a single-year estimate (TTM FCF in millions) since we
    only have one TTM snapshot.  The production DCF engine seeds the
    projection from this value.

    ``current_price`` is optional but recommended — used to populate
    ``market_cap_millions`` so the DCF sanity check can detect implausibly
    low per-share values for large-caps (unit mismatch / negative equity).

    Returns None if FCF data is entirely missing (engine will skip DCF method).
    """
    # Lazy import to avoid circular dependency at module load
    from research_swarm.agents.fundamentalist.models import DCFInputs

    if fund.fcf_ttm_raw is None and fund.fcf_per_share is None:
        return None

    # Prefer raw dollar FCF; fall back to per-share × shares — both converted to millions
    fcf_millions: Optional[float] = None
    if fund.fcf_ttm_raw is not None:
        fcf_millions = fund.fcf_ttm_raw / 1_000_000
    elif fund.fcf_per_share is not None and fund.shares_raw:
        fcf_millions = (fund.fcf_per_share * fund.shares_raw) / 1_000_000

    fcf_history: List[float] = [fcf_millions] if fcf_millions is not None else []

    margin_trend: Optional[str] = _margin_trend(fund)

    shares_millions: Optional[float] = (
        fund.shares_raw / 1_000_000 if fund.shares_raw else None
    )
    total_debt_millions: Optional[float] = (
        fund.total_debt_raw / 1_000_000 if fund.total_debt_raw is not None else None
    )
    cash_millions: Optional[float] = (
        fund.cash_raw / 1_000_000 if fund.cash_raw is not None else None
    )

    # Market cap in millions — used by DCF sanity check to detect nonsensical outputs
    market_cap_millions: Optional[float] = None
    if current_price is not None and current_price > 0 and fund.shares_raw:
        market_cap_millions = (fund.shares_raw * current_price) / 1_000_000

    return DCFInputs(
        fcf_history=fcf_history,
        revenue_growth_rate=fund.revenue_growth_yoy,
        operating_margin_trend=margin_trend,
        total_debt=total_debt_millions,
        cash_and_equivalents=cash_millions,
        shares_outstanding=shares_millions,
        market_cap_millions=market_cap_millions,
    )


def build_historical_eps(fund: PITFundamentals) -> Optional[List[float]]:
    """
    Convert the quarterly ``eps_series`` (newest first) into annual EPS
    values that ``BlendedValuationCalculator._normalize_eps()`` expects.

    Groups quarters in sets of 4 to form annual sums; returns newest-first.
    Returns None if fewer than 4 quarters are available.
    """
    if not fund.eps_series or len(fund.eps_series) < 4:
        return None
    annual: List[float] = []
    qs = fund.eps_series
    for i in range(0, len(qs) - 3, 4):
        annual.append(sum(qs[i : i + 4]))
    return annual if annual else None


def compute_quarterly_margin_std(fund: PITFundamentals) -> Optional[float]:
    """
    Estimate quarterly operating-margin standard deviation from net margins.

    Used as the ``quarterly_margin_std`` input in blended_valuation (Part 4
    confidence filter).  Net margin is a proxy for operating margin; the
    absolute value is less important than the variability signal.

    Returns None if fewer than 4 quarters of margin data are available.
    """
    if fund.net_margin is None or fund.revenue_ttm_raw is None:
        return None
    if not fund.eps_series or len(fund.eps_series) < 4:
        return None

    # Reconstruct approximate quarterly net margins from quarterly net income.
    # We only have EPS per quarter (no per-quarter revenue), so this is a rough
    # proxy: use EPS spread as a margin-volatility proxy (not a true % margin).
    eps_vals = fund.eps_series[:8]
    if len(eps_vals) < 4:
        return None

    mean_eps = sum(eps_vals) / len(eps_vals)
    if mean_eps == 0:
        return None

    variance = sum((e - mean_eps) ** 2 for e in eps_vals) / len(eps_vals)
    std_eps = variance ** 0.5
    # Return as a percentage of mean (coefficient of variation × net_margin)
    cv = std_eps / abs(mean_eps)
    return round(abs(fund.net_margin) * cv, 2) if fund.net_margin else None


# ── Internal helpers ───────────────────────────────────────────────────────────


def _valuation_category(pe_ratio: Optional[float]) -> str:
    """Map trailing P/E to a rough valuation category label."""
    if pe_ratio is None:
        return "Unknown"
    if pe_ratio > 40:
        return "Extreme Premium"
    if pe_ratio > 25:
        return "Premium"
    if pe_ratio > 12:
        return "Fair"
    return "Discount"


def _margin_trend(fund: PITFundamentals) -> Optional[str]:
    """Infer margin trend from FCF margin level."""
    if fund.fcf_margin is None:
        return None
    if fund.fcf_margin > 15:
        return "expanding"
    if fund.fcf_margin < 3:
        return "contracting"
    return "stable"
