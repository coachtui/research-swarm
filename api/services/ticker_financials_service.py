"""
Ticker Financials Cache Service
================================
Quarterly and annual financial data, cached per ticker to avoid re-fetching
the same earnings data on every analysis run.

Fetch priority:
  1. DB cache  — fresh if fetched within STALE_DAYS (90) days
  2. yfinance  — fast, covers most US + international listings
  3. SEC EDGAR — authoritative for US companies; fills gaps yfinance misses

Usage (in fundamentalist graph):
    from api.services.ticker_financials_service import get_quarterly_financials

    rows = await get_quarterly_financials(ticker, min_quarters=8)
    margin_history = [r["operating_margin"] for r in rows if r["operating_margin"] is not None]
    margin_trend   = compute_margin_trend(margin_history)
    fcf_history    = [r["free_cash_flow"] for r in rows if r["free_cash_flow"] is not None]
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Rows older than this trigger a re-fetch from the upstream source
STALE_DAYS = 90


# ── Public API ────────────────────────────────────────────────────────────────


async def get_quarterly_financials(
    ticker: str,
    min_quarters: int = 8,
    db: Any = None,
) -> List[Dict[str, Any]]:
    """
    Return up to `min_quarters` quarters of financial data for `ticker`.

    Checks DB cache first. If the cache has fewer than `min_quarters` fresh
    rows, fetches the remainder from yfinance (primary) or EDGAR (fallback).
    Rows are returned newest-first.

    Each row dict keys:
        period, period_end, source, revenue, operating_income, operating_margin,
        gross_profit, net_income, ebitda, operating_cash_flow, capex,
        free_cash_flow, total_debt, cash

    `db`: optional injected prisma client. Pass a dedicated client when
    calling from a throwaway event loop (e.g. a worker thread) — the shared
    singleton from api.lib.db.get_db() must never bind a connection to a
    loop that gets closed out from under the pool (closed-loop poisoning
    incident 2026-07-10). Defaults to the shared client when omitted.
    """
    if db is None:
        from api.lib.db import get_db
        db = await get_db()
    cutoff = datetime.now(timezone.utc) - timedelta(days=STALE_DAYS)

    # ── 1. Check DB cache ─────────────────────────────────────────────────────
    existing = await db.tickerfinancials.find_many(
        where={"ticker": ticker, "fetchedAt": {"gte": cutoff}},
        order={"periodEnd": "desc"},
        take=min_quarters * 2,  # grab extra in case some sources have dupes
    )
    cached_rows = [_model_to_dict(r) for r in existing]

    if len(cached_rows) >= min_quarters:
        logger.debug("ticker_financials: %s — %d rows from DB cache", ticker, len(cached_rows))
        return cached_rows[:min_quarters]

    logger.info(
        "ticker_financials: %s — only %d cached rows (need %d), fetching upstream",
        ticker, len(cached_rows), min_quarters,
    )

    # ── 2. Fetch from yfinance ────────────────────────────────────────────────
    yf_rows: List[Dict[str, Any]] = []
    try:
        yf_rows = await _fetch_yfinance(ticker)
        if yf_rows:
            await _upsert_rows(db, ticker, yf_rows)
            logger.info("ticker_financials: %s — stored %d rows from yfinance", ticker, len(yf_rows))
    except Exception as exc:
        logger.warning("ticker_financials: yfinance fetch failed for %s: %s", ticker, exc)

    # ── 3. EDGAR fallback (if yfinance insufficient) ──────────────────────────
    edgar_rows: List[Dict[str, Any]] = []
    if len(yf_rows) < min_quarters:
        try:
            edgar_rows = await _fetch_edgar(ticker)
            if edgar_rows:
                await _upsert_rows(db, ticker, edgar_rows)
                logger.info(
                    "ticker_financials: %s — stored %d rows from EDGAR", ticker, len(edgar_rows)
                )
        except Exception as exc:
            logger.warning("ticker_financials: EDGAR fetch failed for %s: %s", ticker, exc)

    # ── 4. Return merged result from DB (now populated) ───────────────────────
    merged = await db.tickerfinancials.find_many(
        where={"ticker": ticker},
        order={"periodEnd": "desc"},
        take=min_quarters,
    )
    return [_model_to_dict(r) for r in merged]


def compute_margin_trend(margin_history: List[float]) -> Optional[str]:
    """
    Compute operating margin trend from a time-ordered list (oldest→newest).

    Returns "expanding" | "stable" | "contracting" | None (insufficient data).
    Threshold: >2pp difference between first-half avg and second-half avg.
    """
    if not margin_history or len(margin_history) < 3:
        return None

    mid = len(margin_history) // 2
    older_avg = sum(margin_history[:mid]) / mid
    newer_avg = sum(margin_history[mid:]) / (len(margin_history) - mid)
    diff = newer_avg - older_avg  # positive → expanding

    if diff > 2.0:
        return "expanding"
    if diff < -2.0:
        return "contracting"
    return "stable"


def compute_fcf_history(
    op_cf_history: List[float],
    capex_history: List[float],
) -> List[float]:
    """FCF = Operating Cash Flow − CapEx (CapEx stored as positive, subtract it)."""
    length = min(len(op_cf_history), len(capex_history))
    return [
        op_cf_history[i] - abs(capex_history[i])
        for i in range(length)
    ]


# ── yfinance fetch ────────────────────────────────────────────────────────────


async def _fetch_yfinance(ticker: str) -> List[Dict[str, Any]]:
    """
    Pull quarterly income statement + cash flow from yfinance.
    Returns rows ordered oldest→newest.
    """
    import asyncio
    import yfinance as yf
    import pandas as pd

    def _sync_fetch() -> List[Dict[str, Any]]:
        t = yf.Ticker(ticker)

        # Quarterly income statement
        try:
            inc = t.quarterly_income_stmt
        except Exception:
            inc = None

        # Quarterly cash flow
        try:
            cf = t.quarterly_cashflow
        except Exception:
            cf = None

        if inc is None and cf is None:
            return []

        rows: List[Dict[str, Any]] = []
        dates = list(inc.columns) if inc is not None else list(cf.columns)

        def _get(df, *keys) -> Optional[float]:
            if df is None:
                return None
            for k in keys:
                if k in df.index:
                    val = df.loc[k].get(date)
                    if val is not None and not (isinstance(val, float) and pd.isna(val)):
                        try:
                            return float(val) / 1_000_000  # → millions USD
                        except (TypeError, ValueError):
                            pass
            return None

        for date in dates:
            revenue         = _get(inc, "Total Revenue", "Revenue")
            op_income       = _get(inc, "Operating Income", "EBIT")
            gross_profit    = _get(inc, "Gross Profit")
            net_income      = _get(inc, "Net Income", "Net Income Common Stockholders")
            ebitda          = _get(inc, "EBITDA", "Normalized EBITDA")
            op_cf           = _get(cf, "Operating Cash Flow", "Cash Flow From Operations")
            capex_raw       = _get(cf, "Capital Expenditure")
            capex           = abs(capex_raw) if capex_raw is not None else None
            fcf             = (op_cf - capex) if (op_cf is not None and capex is not None) else None
            total_debt      = _get(cf, "Repayment Of Debt")  # approximate; balance sheet better
            cash            = None

            op_margin: Optional[float] = None
            if revenue and revenue != 0 and op_income is not None:
                op_margin = (op_income / revenue) * 100.0

            # period label: "2024-Q4" derived from date
            if isinstance(date, pd.Timestamp):
                q = (date.month - 1) // 3 + 1
                period = f"{date.year}-Q{q}"
                period_end = date.to_pydatetime().replace(tzinfo=timezone.utc)
            else:
                continue

            rows.append({
                "period":              period,
                "period_end":          period_end,
                "source":              "yfinance",
                "revenue":             revenue,
                "operating_income":    op_income,
                "operating_margin":    op_margin,
                "gross_profit":        gross_profit,
                "net_income":          net_income,
                "ebitda":              ebitda,
                "operating_cash_flow": op_cf,
                "capex":               capex,
                "free_cash_flow":      fcf,
                "total_debt":          total_debt,
                "cash":                cash,
            })

        # Return oldest first
        return list(reversed(rows))

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_fetch)


# ── EDGAR fetch ───────────────────────────────────────────────────────────────


async def _fetch_edgar(ticker: str) -> List[Dict[str, Any]]:
    """
    Pull quarterly financials from SEC EDGAR XBRL company facts API.
    Covers US-listed companies only. Fills gaps where yfinance is missing data.
    Returns rows ordered oldest→newest.
    """
    import asyncio
    import httpx

    def _sync_fetch_edgar() -> List[Dict[str, Any]]:
        # Resolve ticker → CIK
        headers = {"User-Agent": "research-swarm/1.0 contact@example.com"}
        try:
            resp = httpx.get(
                "https://efts.sec.gov/LATEST/search-index?q=%22{}%22&dateRange=custom"
                "&startdt=2020-01-01&forms=10-K,10-Q".format(ticker),
                headers=headers,
                timeout=10,
            )
        except Exception:
            pass

        # Use company_tickers.json to map ticker → CIK
        try:
            tickers_resp = httpx.get(
                "https://www.sec.gov/files/company_tickers.json",
                headers=headers,
                timeout=10,
            )
            tickers_data = tickers_resp.json()
        except Exception as exc:
            raise RuntimeError(f"EDGAR ticker resolution failed: {exc}") from exc

        cik = None
        for _entry in tickers_data.values():
            if _entry.get("ticker", "").upper() == ticker.upper():
                cik = str(_entry["cik_str"]).zfill(10)
                break

        if not cik:
            logger.debug("EDGAR: no CIK found for %s (non-US company?)", ticker)
            return []

        # Fetch company facts (XBRL)
        try:
            facts_resp = httpx.get(
                f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
                headers=headers,
                timeout=15,
            )
            facts = facts_resp.json()
        except Exception as exc:
            raise RuntimeError(f"EDGAR company facts fetch failed: {exc}") from exc

        us_gaap = facts.get("facts", {}).get("us-gaap", {})

        def _get_quarterly_series(concept: str) -> Dict[str, float]:
            """Return {period_end_date_str: value_in_millions} for quarterly filings."""
            result: Dict[str, float] = {}
            units = us_gaap.get(concept, {}).get("units", {})
            usd_facts = units.get("USD", [])
            for item in usd_facts:
                if item.get("form") not in ("10-Q", "10-K"):
                    continue
                # Only use period-specific (non-cumulative) filings
                if item.get("fp") not in ("Q1", "Q2", "Q3", "Q4", "FY"):
                    continue
                end = item.get("end", "")
                val = item.get("val")
                if end and val is not None:
                    try:
                        result[end] = float(val) / 1_000_000
                    except (TypeError, ValueError):
                        pass
            return result

        revenue_series  = _get_quarterly_series("Revenues") or _get_quarterly_series("RevenueFromContractWithCustomerExcludingAssessedTax")
        op_income_series = _get_quarterly_series("OperatingIncomeLoss")
        net_income_series = _get_quarterly_series("NetIncomeLoss")
        op_cf_series    = _get_quarterly_series("NetCashProvidedByUsedInOperatingActivities")
        capex_series    = _get_quarterly_series("PaymentsToAcquirePropertyPlantAndEquipment")

        # Build rows from revenue keys (it's usually the most complete series)
        all_dates = sorted(set(revenue_series.keys()) | set(op_cf_series.keys()))

        rows: List[Dict[str, Any]] = []
        for end_str in all_dates:
            try:
                period_end = datetime.strptime(end_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                continue

            q = (period_end.month - 1) // 3 + 1
            period = f"{period_end.year}-Q{q}"

            revenue      = revenue_series.get(end_str)
            op_income    = op_income_series.get(end_str)
            net_income   = net_income_series.get(end_str)
            op_cf        = op_cf_series.get(end_str)
            capex        = capex_series.get(end_str)
            capex        = abs(capex) if capex is not None else None
            fcf          = (op_cf - capex) if (op_cf is not None and capex is not None) else None

            op_margin: Optional[float] = None
            if revenue and revenue != 0 and op_income is not None:
                op_margin = (op_income / revenue) * 100.0

            rows.append({
                "period":              period,
                "period_end":          period_end,
                "source":              "edgar",
                "revenue":             revenue,
                "operating_income":    op_income,
                "operating_margin":    op_margin,
                "gross_profit":        None,
                "net_income":          net_income,
                "ebitda":              None,
                "operating_cash_flow": op_cf,
                "capex":               capex,
                "free_cash_flow":      fcf,
                "total_debt":          None,
                "cash":                None,
            })

        return rows

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_fetch_edgar)


# ── DB helpers ────────────────────────────────────────────────────────────────


async def _upsert_rows(db, ticker: str, rows: List[Dict[str, Any]]) -> None:
    """Upsert a list of financial rows into the DB cache."""
    for row in rows:
        try:
            await db.tickerfinancials.upsert(
                where={
                    "ticker_period_source": {
                        "ticker": ticker,
                        "period": row["period"],
                        "source": row["source"],
                    }
                },
                data={
                    "create": {
                        "ticker":            ticker,
                        "period":            row["period"],
                        "periodEnd":         row["period_end"],
                        "source":            row["source"],
                        "revenue":           row.get("revenue"),
                        "operatingIncome":   row.get("operating_income"),
                        "operatingMargin":   row.get("operating_margin"),
                        "grossProfit":       row.get("gross_profit"),
                        "netIncome":         row.get("net_income"),
                        "ebitda":            row.get("ebitda"),
                        "operatingCashFlow": row.get("operating_cash_flow"),
                        "capex":             row.get("capex"),
                        "freeCashFlow":      row.get("free_cash_flow"),
                        "totalDebt":         row.get("total_debt"),
                        "cash":              row.get("cash"),
                    },
                    "update": {
                        "revenue":           row.get("revenue"),
                        "operatingIncome":   row.get("operating_income"),
                        "operatingMargin":   row.get("operating_margin"),
                        "grossProfit":       row.get("gross_profit"),
                        "netIncome":         row.get("net_income"),
                        "ebitda":            row.get("ebitda"),
                        "operatingCashFlow": row.get("operating_cash_flow"),
                        "capex":             row.get("capex"),
                        "freeCashFlow":      row.get("free_cash_flow"),
                        "totalDebt":         row.get("total_debt"),
                        "cash":              row.get("cash"),
                        "fetchedAt":         datetime.now(timezone.utc),
                    },
                },
            )
        except Exception as exc:
            logger.warning("ticker_financials: upsert failed for %s/%s: %s", ticker, row["period"], exc)


def _model_to_dict(row) -> Dict[str, Any]:
    """Convert Prisma TickerFinancials model to a plain dict."""
    return {
        "period":              row.period,
        "period_end":          row.periodEnd,
        "source":              row.source,
        "revenue":             row.revenue,
        "operating_income":    row.operatingIncome,
        "operating_margin":    row.operatingMargin,
        "gross_profit":        row.grossProfit,
        "net_income":          row.netIncome,
        "ebitda":              row.ebitda,
        "operating_cash_flow": row.operatingCashFlow,
        "capex":               row.capex,
        "free_cash_flow":      row.freeCashFlow,
        "total_debt":          row.totalDebt,
        "cash":                row.cash,
    }
