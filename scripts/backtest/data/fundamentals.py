"""
Point-in-Time Fundamental Data Provider
========================================

Fetches quarterly financial data from yfinance and applies a publication-lag
filter so that only data that would have been *available* on a given as-of
date is returned.

PIT Enforcement
───────────────
SEC filing deadlines (approximate):
  • 10-Q (quarterly): 40–45 days after quarter-end for large accelerated filers
  • 10-K (annual):    60–75 days after fiscal year-end

We use FUND_LAG_DAYS=60 as a conservative proxy, meaning a quarter that
ended on 2020-03-31 is only usable from 2020-05-30 onwards.

Cache
─────
Per-ticker JSON.gz files in FUNDAMENTALS_CACHE_DIR:
    {ticker}_fundamentals.json.gz

The raw quarterly data is immutable once filed; the cache never needs
expiration for quarters > 90 days old.

Public API
──────────
    from scripts.backtest.data.fundamentals import get_fundamentals, PITFundamentals

    fund = get_fundamentals("AAPL", date(2020, 6, 30))
    if fund:
        print(fund.eps_ttm, fund.fcf_margin)
"""

from __future__ import annotations

import gzip
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import yfinance as yf

from scripts.backtest.config import FUND_LAG_DAYS

logger = logging.getLogger(__name__)


# ── Data model ────────────────────────────────────────────────────────────────


@dataclass
class PITFundamentals:
    """Fundamental metrics as of a specific point in time."""

    ticker: str
    reporting_period: date           # quarter-end date of the most recent usable quarter
    earliest_use_date: date          # reporting_period + FUND_LAG_DAYS
    quarters_available: int          # quarters used for TTM computation

    # Per-share (in reporting currency; no FX conversion for S&P 500 which is USD)
    eps_ttm: Optional[float]         # TTM net income / shares (USD/share)
    fcf_per_share: Optional[float]   # TTM (operating CF - capex) / shares

    # Dimensionless ratios / percentages
    revenue_growth_yoy: Optional[float]   # YoY % (e.g. 12.5 = +12.5%)
    fcf_margin: Optional[float]           # TTM FCF / TTM revenue %
    roe: Optional[float]                  # TTM net income / avg equity %
    de_ratio: Optional[float]             # total debt / total equity
    net_margin: Optional[float]           # TTM net income / TTM revenue %
    gross_margin: Optional[float]         # TTM gross profit / TTM revenue %

    # Earnings stability (for confidence penalty)
    eps_series: list[float] = field(default_factory=list)  # quarterly EPS, newest first

    # Quality indicator
    data_quality: str = "complete"   # "complete" | "partial" | "insufficient"

    # ── Raw dollar TTM amounts (for production valuation adapter) ─────────────
    # After FX conversion these are in USD.  Before conversion they are in
    # reporting_currency.  Check currency_converted to know which state applies.
    net_income_ttm_raw: Optional[float] = None   # TTM net income (USD after conversion)
    revenue_ttm_raw: Optional[float] = None      # TTM total revenue (USD after conversion)
    fcf_ttm_raw: Optional[float] = None          # TTM free cash flow (USD after conversion)
    total_debt_raw: Optional[float] = None       # Most recent quarter total debt (USD)
    cash_raw: Optional[float] = None             # Most recent quarter cash & equivalents (USD)
    shares_raw: Optional[int] = None             # Shares outstanding (count; not currency-sensitive)

    # ── Currency metadata ─────────────────────────────────────────────────────
    # reporting_currency: the company's financial statement currency (e.g. "EUR")
    # currency_converted: True when raw dollar fields above have been multiplied
    #                     by the historical FX rate to USD.
    reporting_currency: str = "USD"
    currency_converted: bool = False   # False → raw fields are in reporting_currency (native)


# ── Public API ─────────────────────────────────────────────────────────────────


def get_fundamentals(
    ticker: str,
    as_of: date,
    *,
    cache_dir: Path,
    lag_days: int = FUND_LAG_DAYS,
    force_refresh: bool = False,
) -> Optional[PITFundamentals]:
    """
    Return fundamental metrics for *ticker* that were available on *as_of*.

    Only quarters whose end date + lag_days <= as_of are considered.
    Returns None if no qualifying quarters exist.
    """
    raw = _load_raw_quarters(ticker, cache_dir, force_refresh)
    if raw is None:
        return None
    return _build_fundamentals(ticker, raw, as_of, lag_days)


def prewarm_fundamentals(
    tickers: list[str],
    cache_dir: Path,
    workers: int = 3,
    force_refresh: bool = False,
) -> None:
    """
    Download and cache fundamentals for all tickers in parallel.
    Must be called before the main backtest loop to avoid slow per-call downloads.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    cache_dir.mkdir(parents=True, exist_ok=True)
    total = len(tickers)
    logger.info("Pre-warming fundamentals for %d tickers (workers=%d)…", total, workers)

    completed = 0
    failed = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_ticker = {
            executor.submit(_load_raw_quarters, t, cache_dir, force_refresh): t
            for t in tickers
        }
        for future in as_completed(future_to_ticker):
            completed += 1
            ticker = future_to_ticker[future]
            try:
                future.result()
            except Exception as exc:
                failed += 1
                logger.debug("Fundamentals failed for %s: %s", ticker, exc)
            if completed % 50 == 0:
                logger.info("  Fundamentals: %d/%d done (%d failed)", completed, total, failed)

    logger.info("Fundamentals pre-warm complete: %d/%d success", completed - failed, total)


# ── Raw data fetch + cache ────────────────────────────────────────────────────


def _cache_path(ticker: str, cache_dir: Path) -> Path:
    safe = ticker.replace("/", "_").replace("\\", "_").replace(":", "_")
    return cache_dir / f"{safe}_fundamentals.json.gz"


def _load_raw_quarters(
    ticker: str,
    cache_dir: Path,
    force_refresh: bool = False,
) -> Optional[dict]:
    """
    Return the raw quarterly data dict for *ticker*.
    Downloads from yfinance if not cached; saves to cache_dir on success.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    p = _cache_path(ticker, cache_dir)

    if not force_refresh and p.exists():
        try:
            with gzip.open(p, "rt", encoding="utf-8") as f:
                data = json.load(f)
            # Refresh if the most recent quarter is within 90 days and cache is >30 days old
            fetched_at = pd.Timestamp(data.get("fetched_at", "2000-01-01"))
            quarters = data.get("quarters", [])
            needs_refresh = False
            if quarters:
                most_recent = pd.Timestamp(quarters[0]["period_end"])
                age_days = (pd.Timestamp.now() - fetched_at).days
                recency_days = (pd.Timestamp.now() - most_recent).days
                if recency_days < 90 and age_days > 30:
                    needs_refresh = True
            if not needs_refresh:
                return data
        except Exception as exc:
            logger.debug("Cache load failed for %s: %s", ticker, exc)

    # Download from yfinance
    data = _fetch_from_yfinance(ticker)
    if data is None:
        return None

    # Save to cache
    try:
        with gzip.open(p, "wt", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as exc:
        logger.debug("Cache save failed for %s: %s", ticker, exc)

    return data


def _reset_yf_session() -> None:
    """
    Force yfinance to drop its crumb/cookie cache so the next request
    obtains a fresh session.  Works across yfinance 0.2.x and 1.x.
    """
    try:
        # yfinance 1.x
        import yfinance.utils as _yfu
        for attr in ("_cookies_cache", "cookies_cache", "_CRUMBS", "crumbs_cache"):
            obj = getattr(_yfu, attr, None)
            if isinstance(obj, dict):
                obj.clear()
    except Exception:
        pass
    try:
        # yfinance 0.2.x / shared
        import yfinance.shared as _yfs
        for attr in ("_CRUMB", "_cookies"):
            if hasattr(_yfs, attr):
                setattr(_yfs, attr, None)
    except Exception:
        pass


def _fetch_from_yfinance(ticker: str) -> Optional[dict]:
    """Download all available quarterly fundamentals from yfinance."""
    max_attempts = 5
    for attempt in range(max_attempts):
        try:
            stock = yf.Ticker(ticker)

            income = stock.get_income_stmt(freq="quarterly")
            cashflow = stock.get_cash_flow(freq="quarterly")
            balance = stock.get_balance_sheet(freq="quarterly")
            info = stock.info or {}

            shares = (
                info.get("sharesOutstanding")
                or info.get("impliedSharesOutstanding")
                or 0
            )
            # financialCurrency is the currency of the financial statements
            # (e.g. "EUR" for European ADRs, "TWD" for TSMC ADR TSM, "USD" for most S&P 500)
            reporting_currency = (info.get("financialCurrency") or "USD").upper().strip()

            return _normalise_yf_data(ticker, income, cashflow, balance, shares, reporting_currency)

        except Exception as exc:
            exc_str = str(exc)
            is_401 = "401" in exc_str or "Unauthorized" in exc_str or "Invalid Crumb" in exc_str
            is_404 = "404" in exc_str or "Not Found" in exc_str

            if is_404:
                # Symbol doesn't exist — no point retrying
                logger.debug("yfinance 404 for %s (symbol not found)", ticker)
                return None

            if attempt < max_attempts - 1:
                if is_401:
                    # Crumb expired: reset session, wait longer before retry
                    _reset_yf_session()
                    wait = 30 + (attempt * 15)   # 30s, 45s, 60s, 75s
                    logger.debug(
                        "yfinance 401 for %s (attempt %d/%d) — session reset, waiting %ds",
                        ticker, attempt + 1, max_attempts, wait,
                    )
                else:
                    wait = 2 ** attempt          # 1s, 2s, 4s, 8s
                time.sleep(wait)
                continue

            logger.debug(
                "yfinance fetch failed for %s after %d attempts: %s", ticker, max_attempts, exc
            )
            return None
    return None


def _normalise_yf_data(
    ticker: str,
    income: pd.DataFrame,
    cashflow: pd.DataFrame,
    balance: pd.DataFrame,
    shares: int,
    reporting_currency: str = "USD",
) -> Optional[dict]:
    """
    Convert yfinance DataFrames (rows=metrics, cols=quarter_end_dates)
    into a list of per-quarter dicts, newest first.
    """
    if income is None or income.empty:
        return None

    # yfinance returns columns as Timestamps (quarter-end dates), newest first
    quarters = []
    for col in income.columns:
        try:
            period_end = pd.Timestamp(col).date()
        except Exception:
            continue

        def _get(df: Optional[pd.DataFrame], *keys) -> Optional[float]:
            if df is None or df.empty:
                return None
            for k in keys:
                if k in df.index:
                    v = df.at[k, col] if col in df.columns else None
                    if v is not None and not (isinstance(v, float) and pd.isna(v)):
                        try:
                            return float(v)
                        except (TypeError, ValueError):
                            pass
            return None

        net_income = _get(income, "Net Income", "NetIncome")
        total_revenue = _get(income, "Total Revenue", "TotalRevenue")
        gross_profit = _get(income, "Gross Profit", "GrossProfit")
        op_cf = _get(cashflow, "Operating Cash Flow", "OperatingCashFlow")
        capex = _get(cashflow, "Capital Expenditure", "CapitalExpenditure")
        total_debt = _get(balance, "Total Debt", "TotalDebt", "Long Term Debt")
        equity = _get(balance, "Stockholders Equity", "StockholdersEquity",
                      "Common Stock Equity", "Total Equity Gross Minority Interest")
        cash_equiv = _get(
            balance,
            "Cash And Cash Equivalents",
            "CashAndCashEquivalents",
            "Cash Cash Equivalents And Short Term Investments",
            "Cash Financial",
        )

        quarters.append({
            "period_end": period_end.isoformat(),
            "net_income": net_income,
            "total_revenue": total_revenue,
            "gross_profit": gross_profit,
            "operating_cash_flow": op_cf,
            "capital_expenditure": capex,
            "total_debt": total_debt,
            "stockholders_equity": equity,
            "cash_and_equivalents": cash_equiv,
        })

    return {
        "ticker": ticker,
        "fetched_at": pd.Timestamp.now().isoformat(),
        "shares_outstanding": int(shares) if shares else None,
        "reporting_currency": reporting_currency,
        "quarters": quarters,   # newest first
    }


# ── PITFundamentals construction ──────────────────────────────────────────────


def _build_fundamentals(
    ticker: str,
    raw: dict,
    as_of: date,
    lag_days: int,
) -> Optional[PITFundamentals]:
    """
    Filter raw quarters to those available as of *as_of*, compute derived metrics.
    """
    quarters = raw.get("quarters", [])
    shares = raw.get("shares_outstanding") or 0

    # Filter: only use quarters where period_end + lag_days <= as_of
    cutoff = as_of - timedelta(days=lag_days)
    usable = [
        q for q in quarters
        if pd.Timestamp(q["period_end"]).date() <= cutoff
    ]

    if not usable:
        return None

    reporting_period = pd.Timestamp(usable[0]["period_end"]).date()
    earliest_use_date = reporting_period + timedelta(days=lag_days)
    quarters_available = len(usable)

    # TTM = sum of 4 most recent quarters
    def ttm(field: str) -> Optional[float]:
        vals = [q[field] for q in usable[:4] if q.get(field) is not None]
        return sum(vals) if vals else None

    net_income_ttm = ttm("net_income")
    revenue_ttm = ttm("total_revenue")
    gross_profit_ttm = ttm("gross_profit")
    op_cf_ttm = ttm("operating_cash_flow")
    capex_ttm = ttm("capital_expenditure")

    # FCF = operating CF - abs(capex)  [capex usually negative]
    fcf_ttm: Optional[float] = None
    if op_cf_ttm is not None and capex_ttm is not None:
        fcf_ttm = op_cf_ttm + min(capex_ttm, 0)  # capex already negative
    elif op_cf_ttm is not None:
        fcf_ttm = op_cf_ttm  # no capex data, use operating CF as proxy

    # Per-share (shares_outstanding is current — acceptable limitation for S&P 500)
    eps_ttm: Optional[float] = None
    fcf_per_share: Optional[float] = None
    if shares > 0:
        if net_income_ttm is not None:
            eps_ttm = net_income_ttm / shares
        if fcf_ttm is not None:
            fcf_per_share = fcf_ttm / shares

    # Revenue growth YoY (need 8 quarters for TTM-vs-TTM)
    revenue_growth_yoy: Optional[float] = None
    if len(usable) >= 8:
        rev_now = ttm_n(usable, "total_revenue", 0, 4)
        rev_prior = ttm_n(usable, "total_revenue", 4, 8)
        if rev_now is not None and rev_prior is not None and rev_prior != 0:
            revenue_growth_yoy = (rev_now - rev_prior) / abs(rev_prior) * 100

    # FCF margin = TTM FCF / TTM revenue
    fcf_margin: Optional[float] = None
    if fcf_ttm is not None and revenue_ttm and revenue_ttm > 0:
        fcf_margin = fcf_ttm / revenue_ttm * 100

    # Net margin
    net_margin: Optional[float] = None
    if net_income_ttm is not None and revenue_ttm and revenue_ttm > 0:
        net_margin = net_income_ttm / revenue_ttm * 100

    # Gross margin
    gross_margin: Optional[float] = None
    if gross_profit_ttm is not None and revenue_ttm and revenue_ttm > 0:
        gross_margin = gross_profit_ttm / revenue_ttm * 100

    # ROE = TTM net income / average equity
    roe: Optional[float] = None
    equity_vals = [q["stockholders_equity"] for q in usable[:4] if q.get("stockholders_equity") is not None]
    if equity_vals and net_income_ttm is not None:
        avg_equity = sum(equity_vals) / len(equity_vals)
        if avg_equity != 0:
            roe = net_income_ttm / abs(avg_equity) * 100  # preserve sign

    # D/E ratio (most recent quarter)
    de_ratio: Optional[float] = None
    for q in usable[:2]:
        debt = q.get("total_debt")
        equity_q = q.get("stockholders_equity")
        if debt is not None and equity_q is not None and equity_q != 0:
            de_ratio = abs(debt) / max(abs(equity_q), 1)
            break

    # Quarterly EPS series for volatility check
    eps_series: list[float] = []
    for q in usable[:8]:
        ni = q.get("net_income")
        if ni is not None and shares > 0:
            eps_series.append(ni / shares)

    # Data quality
    filled = sum(1 for v in [eps_ttm, fcf_per_share, revenue_growth_yoy, fcf_margin, roe, de_ratio] if v is not None)
    if quarters_available >= 8 and filled >= 4:
        quality = "complete"
    elif quarters_available >= 4 and filled >= 2:
        quality = "partial"
    else:
        quality = "insufficient"

    # ── Raw dollar amounts for production valuation adapter ───────────────────
    # Most recent quarter's balance sheet data
    cash_raw: Optional[float] = None
    total_debt_for_raw: Optional[float] = None
    for q in usable[:2]:
        if cash_raw is None and q.get("cash_and_equivalents") is not None:
            cash_raw = q["cash_and_equivalents"]
        if total_debt_for_raw is None and q.get("total_debt") is not None:
            total_debt_for_raw = q["total_debt"]
        if cash_raw is not None and total_debt_for_raw is not None:
            break

    # ── Currency detection + FX conversion ───────────────────────────────────
    reporting_currency = raw.get("reporting_currency", "USD").upper().strip() or "USD"
    currency_converted = False

    if reporting_currency != "USD":
        # Convert all monetary raw values to USD as-of the *as_of* date.
        # Ratios (fcf_margin, roe, de_ratio, net_margin, gross_margin) are
        # dimensionless and do NOT need conversion.
        # Per-share values (eps_ttm, fcf_per_share, eps_series) are in
        # reporting currency per share — convert them as well.
        try:
            from scripts.backtest.data.fx_rates import get_fx_rate as _get_fx

            fx = _get_fx(reporting_currency, "USD", as_of)
            if fx != 1.0 and fx > 0:
                # Dollar amounts (balance sheet + income statement totals)
                if net_income_ttm is not None:
                    net_income_ttm = net_income_ttm * fx
                if revenue_ttm is not None:
                    revenue_ttm = revenue_ttm * fx
                if fcf_ttm is not None:
                    fcf_ttm = fcf_ttm * fx
                if cash_raw is not None:
                    cash_raw = cash_raw * fx
                if total_debt_for_raw is not None:
                    total_debt_for_raw = total_debt_for_raw * fx

                # Per-share values (in reporting currency / share)
                if eps_ttm is not None:
                    eps_ttm = eps_ttm * fx
                if fcf_per_share is not None:
                    fcf_per_share = fcf_per_share * fx
                eps_series = [e * fx for e in eps_series]

                currency_converted = True
                logger.debug(
                    "%s: converted %s→USD at %.6f (as_of %s)",
                    ticker, reporting_currency, fx, as_of,
                )
            else:
                logger.warning(
                    "%s: FX rate for %s→USD unavailable on %s (got %.6f) — leaving in native currency",
                    ticker, reporting_currency, as_of, fx,
                )
        except Exception as exc:
            logger.warning(
                "%s: FX conversion failed (%s→USD on %s): %s — leaving in native currency",
                ticker, reporting_currency, as_of, exc,
            )

    return PITFundamentals(
        ticker=ticker,
        reporting_period=reporting_period,
        earliest_use_date=earliest_use_date,
        quarters_available=quarters_available,
        eps_ttm=eps_ttm,
        fcf_per_share=fcf_per_share,
        revenue_growth_yoy=revenue_growth_yoy,
        fcf_margin=fcf_margin,
        roe=roe,
        de_ratio=de_ratio,
        net_margin=net_margin,
        gross_margin=gross_margin,
        eps_series=eps_series,
        data_quality=quality,
        # Raw dollar amounts (USD after FX conversion when applicable)
        net_income_ttm_raw=net_income_ttm,
        revenue_ttm_raw=revenue_ttm,
        fcf_ttm_raw=fcf_ttm,
        total_debt_raw=total_debt_for_raw,
        cash_raw=cash_raw,
        shares_raw=int(shares) if shares else None,
        # Currency metadata
        reporting_currency=reporting_currency,
        currency_converted=currency_converted,
    )


def ttm_n(quarters: list[dict], field: str, start: int, end: int) -> Optional[float]:
    """Sum quarters[start:end] for *field*, return None if all missing."""
    vals = [q[field] for q in quarters[start:end] if q.get(field) is not None]
    return sum(vals) if vals else None
