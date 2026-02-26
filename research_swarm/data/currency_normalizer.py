"""
Currency normalization layer for ADR and foreign-listed securities.

Ensures all monetary financial metrics are converted to USD before any
valuation, scoring, or ratio calculations. This prevents silent currency
mixing (e.g. TWD EBITDA vs USD market cap) in EV and P/E formulas.

Usage:
    currency_info = detect_currency_info(ticker, stock_info)
    stock_info    = normalize_stock_info_to_usd(stock_info, currency_info)
    historical_eps = normalize_eps_series_to_usd(historical_eps, currency_info)
    fcf_history   = normalize_series_to_usd(fcf_history, currency_info)

    # In report metadata:
    meta = currency_info.as_report_meta()
    # → {"reporting_currency": "TWD", "converted_to": "USD", "fx_rate_used": 0.031, ...}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

import yfinance as yf

from research_swarm.logger import logger

# ---------------------------------------------------------------------------
# Field lists
# ---------------------------------------------------------------------------

# Monetary fields in yfinance stock.info that are denominated in
# financialCurrency (the company's reporting currency), NOT the trading
# currency.  These must be converted to USD before entering any valuation
# formula that also uses USD-denominated inputs (price, market cap, EV).
MONETARY_STOCK_INFO_FIELDS: List[str] = [
    "ebitda",
    "totalDebt",
    "cash",
    "totalCash",
    "freeCashflow",
    "operatingCashflow",
    "capitalExpenditures",
    "totalRevenue",
    "grossProfits",
    "operatingIncome",
    "netIncome",
    "trailingEps",   # per-share in financialCurrency — must match USD price
    "forwardEps",    # same
]

# Dimensionless / percentage fields — leave untouched.
_RATIO_FIELDS: frozenset = frozenset({
    "trailingPE", "forwardPE", "priceToBook", "priceToSalesTrailing12Months",
    "enterpriseToEbitda", "enterpriseToRevenue",
    "grossMargins", "operatingMargins", "profitMargins", "ebitdaMargins",
    "revenueGrowth", "earningsGrowth", "earningsQuarterlyGrowth",
    "returnOnEquity", "returnOnAssets",
    "beta", "dividendYield", "payoutRatio", "pegRatio",
})

# ---------------------------------------------------------------------------
# In-process FX cache (lives for the duration of this Python process /
# Vercel function invocation — fresh rate per report run).
# ---------------------------------------------------------------------------
_fx_cache: Dict[str, float] = {}


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class CurrencyInfo:
    """
    Currency metadata for a single security.

    trading_currency  — currency the security trades in (USD for ADRs on NYSE)
    reporting_currency — currency of financial statements (TWD for TSM, EUR for ASML)
    fx_rate           — spot rate: 1 reporting_currency = fx_rate USD
    conversion_date   — ISO date when rate was fetched
    is_converted      — True if a conversion was applied (or will be applied)
    adr_ratio         — shares per ADR if known (e.g. 5.0 for some ADRs); None if 1:1 or unknown
    """
    trading_currency: str
    reporting_currency: str
    fx_rate: float
    conversion_date: str
    is_converted: bool
    adr_ratio: Optional[float] = field(default=None)

    def as_report_meta(self) -> Dict[str, Any]:
        """Return a transparency dict suitable for embedding in the report metadata."""
        if not self.is_converted:
            return {
                "reporting_currency": self.reporting_currency,
                "converted_to": "USD",
                "fx_rate_used": 1.0,
                "conversion_date": self.conversion_date,
                "note": "No conversion required — financials already denominated in USD",
            }
        out: Dict[str, Any] = {
            "reporting_currency": self.reporting_currency,
            "converted_to": "USD",
            "fx_rate_used": round(self.fx_rate, 6),
            "conversion_date": self.conversion_date,
        }
        if self.adr_ratio is not None:
            out["adr_ratio"] = self.adr_ratio
        return out


# ---------------------------------------------------------------------------
# FX rate fetching
# ---------------------------------------------------------------------------

def _get_fx_rate(from_currency: str, to_currency: str = "USD") -> Optional[float]:
    """
    Fetch spot FX rate via yfinance currency pair.  Results are cached
    for the lifetime of the process (one rate per analysis run).

    Example:
        _get_fx_rate("TWD")  → 0.031   (1 TWD ≈ 0.031 USD)
        _get_fx_rate("EUR")  → 1.08    (1 EUR ≈ 1.08 USD)

    Returns None if the rate cannot be fetched (caller should decide
    whether to default to 1.0 or abort).
    """
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()

    if from_currency == to_currency:
        return 1.0

    cache_key = f"{from_currency}{to_currency}"
    if cache_key in _fx_cache:
        return _fx_cache[cache_key]

    # yfinance FX ticker format: "EURUSD=X", "TWDUSD=X", "GBPUSD=X"
    yf_ticker = f"{from_currency}{to_currency}=X"
    try:
        fx = yf.Ticker(yf_ticker)
        info = fx.info
        rate = (
            info.get("regularMarketPrice")
            or info.get("bid")
            or info.get("ask")
        )
        if rate and float(rate) > 0:
            _fx_cache[cache_key] = float(rate)
            logger.info(
                f"[CurrencyNormalizer] FX fetched: 1 {from_currency} = {rate:.6f} {to_currency} "
                f"(via {yf_ticker})"
            )
            return float(rate)
    except Exception as exc:
        logger.warning(f"[CurrencyNormalizer] FX fetch failed for {yf_ticker}: {exc}")

    return None


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def detect_currency_info(ticker: str, stock_info: Dict[str, Any]) -> CurrencyInfo:
    """
    Detect trading and reporting currencies from a yfinance stock.info dict.

    yfinance fields used:
      - ``currency``          trading currency  ("USD" for NYSE ADR)
      - ``financialCurrency`` reporting currency ("TWD" for TSM, "EUR" for ASML)

    When reporting_currency != "USD" a spot FX rate is fetched from yfinance.
    If the rate cannot be fetched, is_converted is set to False and a warning
    is logged — downstream callers should treat results with reduced confidence.

    Returns:
        CurrencyInfo — always succeeds; may carry fx_rate=1.0 + is_converted=False
        on failure.
    """
    trading_currency = (stock_info.get("currency") or "USD").upper()
    # financialCurrency is the authoritative field for what units the balance
    # sheet / income statement figures are in.
    reporting_currency = (
        stock_info.get("financialCurrency") or trading_currency
    ).upper()

    today = str(date.today())

    if reporting_currency == "USD":
        return CurrencyInfo(
            trading_currency=trading_currency,
            reporting_currency=reporting_currency,
            fx_rate=1.0,
            conversion_date=today,
            is_converted=False,
        )

    fx_rate = _get_fx_rate(reporting_currency, "USD")
    if fx_rate is None:
        logger.warning(
            f"[CurrencyNormalizer] {ticker}: Could not fetch {reporting_currency}/USD rate. "
            "Financial figures will remain in reporting currency — "
            "valuation output may be unreliable for this ticker."
        )
        return CurrencyInfo(
            trading_currency=trading_currency,
            reporting_currency=reporting_currency,
            fx_rate=1.0,
            conversion_date=today,
            is_converted=False,  # mark as NOT converted since we have no valid rate
        )

    return CurrencyInfo(
        trading_currency=trading_currency,
        reporting_currency=reporting_currency,
        fx_rate=fx_rate,
        conversion_date=today,
        is_converted=True,
    )


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def normalize_stock_info_to_usd(
    stock_info: Dict[str, Any],
    currency_info: CurrencyInfo,
) -> Dict[str, Any]:
    """
    Return a new stock_info dict with monetary fields converted to USD.

    For each field in MONETARY_STOCK_INFO_FIELDS:
      - The original value is stored as  ``<field>_original``
      - The converted value replaces      ``<field>``

    Dimensionless fields (ratios, margins, growth rates, beta) are left as-is.

    Sentinel keys added to the returned dict:
      ``_currency_normalized``   bool  True
      ``_reporting_currency``    str   e.g. "TWD"
      ``_fx_rate``               float e.g. 0.031

    Pass-through (no copy) if is_converted is False.
    """
    if not currency_info.is_converted:
        return stock_info

    normalized = dict(stock_info)          # shallow copy
    rate = currency_info.fx_rate
    converted_fields: List[str] = []

    for field_name in MONETARY_STOCK_INFO_FIELDS:
        val = stock_info.get(field_name)
        if val is not None and isinstance(val, (int, float)) and val != 0:
            normalized[f"{field_name}_original"] = val
            normalized[field_name] = val * rate
            converted_fields.append(field_name)

    # Sentinels — used by validate_usd_normalized()
    normalized["_currency_normalized"] = True
    normalized["_reporting_currency"] = currency_info.reporting_currency
    normalized["_fx_rate"] = rate

    if converted_fields:
        logger.info(
            f"[CurrencyNormalizer] {currency_info.reporting_currency} → USD "
            f"(rate={rate:.6f}). Converted: {', '.join(converted_fields)}"
        )

    return normalized


def normalize_series_to_usd(
    values: List[Optional[float]],
    currency_info: CurrencyInfo,
) -> List[Optional[float]]:
    """
    Convert a list of monetary values (e.g., FCF history, revenue series)
    from reporting_currency to USD.  None elements are preserved as None.

    Pass-through if no conversion is needed.
    """
    if not currency_info.is_converted or not values:
        return values
    rate = currency_info.fx_rate
    return [v * rate if v is not None else None for v in values]


def normalize_eps_series_to_usd(
    eps_values: List[Optional[float]],
    currency_info: CurrencyInfo,
) -> List[Optional[float]]:
    """
    Convert per-share EPS values from reporting_currency to USD.

    EPS is denominated in reporting_currency per share.  Multiplying by the
    FX rate gives USD per share, which is consistent with the USD stock price
    used in P/E calculations.

    This assumes yfinance sharesOutstanding reflects ADR share count for
    US-listed ADRs (which is the standard yfinance behaviour for the US ticker).
    """
    return normalize_series_to_usd(eps_values, currency_info)


def normalize_scalar_to_usd(
    value: Optional[float],
    currency_info: CurrencyInfo,
) -> Optional[float]:
    """Convert a single monetary scalar from reporting_currency to USD."""
    if value is None or not currency_info.is_converted:
        return value
    return value * currency_info.fx_rate


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_usd_normalized(
    stock_info: Dict[str, Any],
    ticker: str,
    raise_on_fail: bool = False,
) -> bool:
    """
    Verify that stock_info monetary fields are USD-normalized.

    Passes if:
      - financialCurrency is "USD" (or absent), OR
      - _currency_normalized sentinel is True (normalizer was run)

    Args:
        raise_on_fail: If True, raises ValueError on failure.
                       If False (default), logs an error and returns False.

    Returns:
        True if validation passes, False otherwise.
    """
    reporting_currency = (stock_info.get("financialCurrency") or "USD").upper()
    already_usd = reporting_currency == "USD"
    is_normalized = bool(stock_info.get("_currency_normalized", False))

    if already_usd or is_normalized:
        return True

    msg = (
        f"[CurrencyNormalizer] VALIDATION FAILED — {ticker}: "
        f"monetary valuation inputs are NOT USD-normalized "
        f"(financialCurrency='{reporting_currency}'). "
        "All monetary inputs must be USD before running valuation."
    )
    if raise_on_fail:
        raise ValueError(msg)
    logger.error(msg)
    return False
