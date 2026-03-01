"""
Daily Total-Return Price Series Provider
=========================================

Downloads and caches daily adjusted-close prices for a given set of tickers
via yfinance.  auto_adjust=True accounts for splits and dividends (total
return approximation).

Cache
─────
Per-ticker files in PRICES_CACHE_DIR:
    {ticker}.parquet  (if pyarrow available)
    {ticker}.pkl.gz   (fallback)

Files are considered fresh if they cover the requested [start, end] range.
Historical data (>1 year old) is never re-fetched (it is immutable).

Public API
──────────
    from scripts.backtest.data.prices import get_total_return_series, get_beta_as_of

    price_data = get_total_return_series(tickers, "2015-01-01", "2026-01-01")
    beta = get_beta_as_of("AAPL", date(2020, 6, 30), price_data)
"""

from __future__ import annotations

import gzip
import logging
import pickle
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# Detect pyarrow
try:
    import pyarrow  # noqa: F401
    _HAS_PYARROW = True
except ImportError:
    _HAS_PYARROW = False


# ── Data container ────────────────────────────────────────────────────────────


@dataclass
class PriceData:
    """Holds daily and month-end price series for a universe of tickers."""

    daily: pd.DataFrame         # index=date (business days), cols=tickers, vals=adj close
    monthly: pd.DataFrame       # index=month-end date, same cols — resampled from daily
    spy_daily: pd.Series        # SPY daily adj close (for beta computation)
    tickers: list[str] = field(default_factory=list)

    def daily_returns(self) -> pd.DataFrame:
        """Percentage daily returns (not log)."""
        return self.daily.pct_change()

    def spy_returns(self) -> pd.Series:
        """SPY daily percentage returns."""
        return self.spy_daily.pct_change()


# ── Public API ─────────────────────────────────────────────────────────────────


def get_total_return_series(
    tickers: list[str],
    start: str,
    end: str,
    *,
    cache_dir: Path,
    batch_size: int = 50,
    force_refresh: bool = False,
    spy_ticker: str = "SPY",
) -> PriceData:
    """
    Fetch daily adjusted-close total-return series for *tickers*.

    Attempts to load from cache first; downloads only what is missing.

    Parameters
    ----------
    tickers     : list of ticker symbols (yfinance-compatible, e.g. BRK-B)
    start, end  : date range strings "YYYY-MM-DD"
    cache_dir   : directory for per-ticker cache files
    batch_size  : number of tickers per yfinance batch download
    force_refresh : re-download even if cache exists
    spy_ticker  : market index for beta computation
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Ensure SPY is included in the download
    all_tickers = sorted(set(tickers) | {spy_ticker})

    # Split into cached and missing
    to_download: list[str] = []
    cached_data: dict[str, pd.Series] = {}

    for ticker in all_tickers:
        cached = _load_ticker_cache(ticker, cache_dir, start, end)
        if cached is not None and not force_refresh:
            cached_data[ticker] = cached
        else:
            to_download.append(ticker)

    if to_download:
        logger.info(
            "Downloading %d tickers (%s → %s)…", len(to_download), start, end
        )
        freshly_downloaded = _batch_download(to_download, start, end, batch_size)
        for ticker, series in freshly_downloaded.items():
            _save_ticker_cache(ticker, series, cache_dir)
            cached_data[ticker] = series

    # Assemble full daily DataFrame
    all_series = {
        t: s for t, s in cached_data.items() if t in set(tickers) | {spy_ticker}
    }

    if not all_series:
        raise RuntimeError("No price data could be loaded for any ticker")

    daily = pd.DataFrame(all_series)
    daily.index = pd.DatetimeIndex(daily.index)
    daily = daily.sort_index()

    # Forward-fill gaps up to 5 consecutive missing days (trading halts, holidays)
    daily = daily.ffill(limit=5)

    # Month-end close
    monthly = daily.resample("ME").last()

    # SPY series
    spy_daily = daily[spy_ticker] if spy_ticker in daily.columns else pd.Series(dtype=float)

    available = [t for t in tickers if t in daily.columns]
    missing = [t for t in tickers if t not in daily.columns]
    if missing:
        logger.warning("%d tickers unavailable (delisted or bad data): %s…",
                       len(missing), missing[:5])

    return PriceData(
        daily=daily[available],
        monthly=monthly[available],
        spy_daily=spy_daily,
        tickers=available,
    )


def get_beta_as_of(
    ticker: str,
    as_of: date,
    price_data: PriceData,
    window: int = 252,
) -> float:
    """
    Rolling 252-day beta for *ticker* vs SPY as of *as_of*.

    Returns 1.0 (market-neutral) if fewer than window/2 days of history.
    """
    if ticker not in price_data.daily.columns or price_data.spy_daily.empty:
        return 1.0

    ts = pd.Timestamp(as_of)
    end_idx = price_data.daily.index.searchsorted(ts, side="right")
    start_idx = max(0, end_idx - window)

    ticker_prices = price_data.daily[ticker].iloc[start_idx:end_idx]
    spy_prices = price_data.spy_daily.iloc[start_idx:end_idx]

    if len(ticker_prices) < window // 2:
        return 1.0

    ret_t = ticker_prices.pct_change().dropna()
    ret_s = spy_prices.pct_change().dropna()

    # Align
    aligned = pd.concat([ret_t, ret_s], axis=1, join="inner")
    if len(aligned) < 30:
        return 1.0

    aligned.columns = ["ticker", "spy"]
    cov = aligned.cov().at["ticker", "spy"]
    var_spy = aligned["spy"].var()
    if var_spy == 0:
        return 1.0

    return float(np.clip(cov / var_spy, -3.0, 5.0))


def get_price_as_of(
    ticker: str,
    as_of: date,
    price_data: PriceData,
) -> Optional[float]:
    """Return the most recent available price on or before *as_of*."""
    if ticker not in price_data.daily.columns:
        return None

    ts = pd.Timestamp(as_of)
    past = price_data.daily.index[price_data.daily.index <= ts]
    if past.empty:
        return None

    val = price_data.daily.at[past[-1], ticker]
    return float(val) if pd.notna(val) and val > 0 else None


def next_business_day(as_of: date, price_data: PriceData) -> date:
    """
    Return the first business day AFTER *as_of* that has price data.
    Fallback: as_of + 1 day (when no price index is available).
    """
    ts = pd.Timestamp(as_of)
    future = price_data.daily.index[price_data.daily.index > ts]
    if future.empty:
        return as_of + pd.Timedelta(days=1)
    return future[0].date()


# ── Cache helpers ─────────────────────────────────────────────────────────────


def _cache_path(ticker: str, cache_dir: Path) -> Path:
    safe = ticker.replace("/", "_").replace("\\", "_")
    ext = ".parquet" if _HAS_PYARROW else ".pkl.gz"
    return cache_dir / f"{safe}{ext}"


def _load_ticker_cache(
    ticker: str,
    cache_dir: Path,
    start: str,
    end: str,
) -> Optional[pd.Series]:
    p = _cache_path(ticker, cache_dir)
    if not p.exists():
        return None

    try:
        if _HAS_PYARROW and p.suffix == ".parquet":
            df = pd.read_parquet(p)
            series = df.iloc[:, 0]
        else:
            with gzip.open(p, "rb") as f:
                series = pickle.load(f)

        series.index = pd.DatetimeIndex(series.index)

        # Validate coverage
        req_start = pd.Timestamp(start)
        req_end = pd.Timestamp(end)
        if series.index[0] <= req_start and series.index[-1] >= req_end:
            return series
        return None
    except Exception as exc:
        logger.debug("Cache load failed for %s: %s", ticker, exc)
        return None


def _save_ticker_cache(ticker: str, series: pd.Series, cache_dir: Path) -> None:
    p = _cache_path(ticker, cache_dir)
    try:
        if _HAS_PYARROW and p.suffix == ".parquet":
            df = series.to_frame(name="close")
            df.to_parquet(p)
        else:
            with gzip.open(p, "wb") as f:
                pickle.dump(series, f)
    except Exception as exc:
        logger.debug("Cache save failed for %s: %s", ticker, exc)


# ── Download helpers ──────────────────────────────────────────────────────────


def _batch_download(
    tickers: list[str],
    start: str,
    end: str,
    batch_size: int,
) -> dict[str, pd.Series]:
    """Download tickers in batches; return dict ticker → close Series."""
    result: dict[str, pd.Series] = {}
    chunks = [tickers[i : i + batch_size] for i in range(0, len(tickers), batch_size)]

    for i, chunk in enumerate(chunks, 1):
        logger.info("  Batch %d/%d (%d tickers)…", i, len(chunks), len(chunk))
        for attempt in range(3):
            try:
                raw = yf.download(
                    chunk,
                    start=start,
                    end=end,
                    auto_adjust=True,
                    progress=False,
                    threads=True,
                )
                break
            except Exception as exc:
                if attempt == 2:
                    logger.error("Batch %d failed after 3 attempts: %s", i, exc)
                    raw = pd.DataFrame()
                    break
                logger.warning("Batch %d attempt %d failed: %s — retrying…", i, attempt + 1, exc)
                time.sleep(2 ** attempt)

        if raw.empty:
            continue

        # Handle both single-ticker and multi-ticker yfinance shapes
        if isinstance(raw.columns, pd.MultiIndex):
            close = raw["Close"]
        else:
            if len(chunk) == 1:
                close = raw[["Close"]]
                close.columns = chunk
            else:
                close = raw[["Close"]]

        for ticker in chunk:
            if ticker in close.columns:
                s = close[ticker].dropna()
                if len(s) > 10:
                    result[ticker] = s

        time.sleep(0.3)  # polite delay between batches

    return result
