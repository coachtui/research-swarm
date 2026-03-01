"""
Historical FX Rate Provider
============================

Fetches and caches daily FX rates (close prices) via yfinance for
point-in-time USD conversion of non-USD fundamental data.

Yfinance ticker format:  ``EURUSD=X``, ``TWDUSD=X``, ``CNHUSD=X``
For JPY, KRW (>=1 USD): we use ``USDJPY=X`` then invert.

Cache
─────
Per-pair parquet files in ``<cache_dir>/fx_rates/``:
    EURUSD.parquet, JPYUSD.parquet, etc.
Columns: ``date`` (index), ``rate`` (float).
The full available history is downloaded once; incremental refresh if
the latest cached date is >30 days before today.

Public API
──────────
    from scripts.backtest.data.fx_rates import get_fx_rate

    rate = get_fx_rate("EUR", "USD", date(2020, 3, 31))
    # → 1.103 (1 EUR = 1.103 USD)

    rate = get_fx_rate("USD", "USD", ...)
    # → 1.0 (always)
"""

from __future__ import annotations

import logging
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ── yfinance ticker map ────────────────────────────────────────────────────────
# Maps (from_ccy, to_ccy) → yfinance ticker.
# For pairs where yfinance quotes USD per foreign unit, use the direct ticker.
# For inverse pairs (e.g. USD/JPY = how many JPY per USD), we invert.
_DIRECT: Dict[str, str] = {
    "EUR": "EURUSD=X",
    "GBP": "GBPUSD=X",
    "AUD": "AUDUSD=X",
    "CAD": "CADUSD=X",   # actually yfinance uses CADUSD=X
    "CHF": "CHFUSD=X",
    "NZD": "NZDUSD=X",
    "HKD": "HKDUSD=X",
    "SGD": "SGDUSD=X",
    "MXN": "MXNUSD=X",
    "BRL": "BRLUSD=X",
    "INR": "INRUSD=X",
    "TWD": "TWDUSD=X",
    "KRW": "KRUSD=X",
    "CNY": "CNYUSD=X",
    "CNH": "CNHUSD=X",   # offshore CNY
    "DKK": "DKKUSD=X",
    "NOK": "NOKUSD=X",
    "SEK": "SEKUSD=X",
    "ILS": "ILSUSD=X",
    "ZAR": "ZARUSD=X",
}

# Pairs that yfinance only quotes as USD→foreign (need inversion).
_INVERSE: Dict[str, str] = {
    "JPY": "JPY=X",      # JPY per USD  → invert to get USD per JPY
}

# Module-level cache {pair_key: DataFrame[rate]}
_rate_cache: Dict[str, pd.Series] = {}


# ── Public API ─────────────────────────────────────────────────────────────────


def get_fx_rate(
    from_currency: str,
    to_currency: str = "USD",
    as_of: Optional[date] = None,
    *,
    cache_dir: Optional[Path] = None,
) -> float:
    """
    Return the FX rate: 1 *from_currency* = X *to_currency* on *as_of*.

    Uses the most recent available rate on or before *as_of* (forward-fill).
    If *as_of* is None, uses today's date.

    Returns 1.0 for same-currency pairs.  Falls back to 1.0 on any error
    (with a warning) rather than aborting the backtest.
    """
    from_ccy = (from_currency or "USD").upper().strip()
    to_ccy = (to_currency or "USD").upper().strip()

    if from_ccy == to_ccy:
        return 1.0

    if to_ccy != "USD":
        # Unsupported cross — try via USD triangulation
        logger.debug("Non-USD target %s — falling back to 1.0", to_ccy)
        return 1.0

    as_of_date = as_of or date.today()

    try:
        series = _load_rates(from_ccy, cache_dir=cache_dir)
        if series is None or series.empty:
            logger.warning("No FX data for %s/USD — using 1.0", from_ccy)
            return 1.0

        ts = pd.Timestamp(as_of_date)
        available = series[series.index <= ts]
        if available.empty:
            logger.warning("No FX data for %s/USD before %s — using 1.0", from_ccy, as_of_date)
            return 1.0

        return float(available.iloc[-1])

    except Exception as exc:
        logger.warning("FX rate lookup failed for %s/USD on %s: %s — using 1.0",
                       from_ccy, as_of_date, exc)
        return 1.0


def prewarm_fx_rates(
    currencies: list[str],
    start: str = "2014-01-01",
    cache_dir: Optional[Path] = None,
) -> None:
    """
    Pre-download FX rate history for all *currencies* in parallel.
    Call before the backtest loop to avoid per-signal downloads.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    unique = [c.upper() for c in currencies if c.upper() != "USD"]
    if not unique:
        return

    logger.info("Pre-warming FX rates for: %s", unique)
    with ThreadPoolExecutor(max_workers=4) as exe:
        futs = {exe.submit(_load_rates, ccy, cache_dir=cache_dir, start=start): ccy
                for ccy in unique}
        for fut in as_completed(futs):
            ccy = futs[fut]
            try:
                fut.result()
                logger.debug("FX prewarm OK: %s/USD", ccy)
            except Exception as exc:
                logger.debug("FX prewarm failed %s: %s", ccy, exc)


# ── Internal ───────────────────────────────────────────────────────────────────


def _cache_path(currency: str, cache_dir: Path) -> Path:
    return cache_dir / f"{currency}USD.parquet"


def _load_rates(
    from_ccy: str,
    *,
    cache_dir: Optional[Path] = None,
    start: str = "2014-01-01",
) -> Optional[pd.Series]:
    """Load (or download + cache) the full FX rate series for *from_ccy*/USD."""
    global _rate_cache

    cache_key = from_ccy
    if cache_key in _rate_cache:
        return _rate_cache[cache_key]

    # Resolve cache directory
    if cache_dir is None:
        from scripts.backtest.config import CACHE_DIR
        import sys
        from pathlib import Path as _Path
        project_root = _Path(__file__).parent.parent.parent.parent
        cache_dir = project_root / CACHE_DIR / "fx_rates"

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    p = _cache_path(from_ccy, cache_dir)

    # Try loading from cache
    series = _try_load_cache(p, from_ccy)
    needs_refresh = _needs_refresh(series)

    if series is not None and not needs_refresh:
        _rate_cache[cache_key] = series
        return series

    # Download from yfinance
    downloaded = _download_rates(from_ccy, start=start)
    if downloaded is not None and not downloaded.empty:
        # Merge with existing cache (if any) to preserve old history
        if series is not None and not series.empty:
            combined = pd.concat([series, downloaded]).sort_index()
            combined = combined[~combined.index.duplicated(keep="last")]
        else:
            combined = downloaded

        _save_cache(combined, p)
        _rate_cache[cache_key] = combined
        return combined

    # Download failed — return what we have (may be stale but usable)
    if series is not None:
        _rate_cache[cache_key] = series
        return series

    return None


def _try_load_cache(p: Path, currency: str) -> Optional[pd.Series]:
    if not p.exists():
        return None
    try:
        df = pd.read_parquet(p)
        if "rate" not in df.columns:
            return None
        series = df["rate"].dropna()
        series.index = pd.to_datetime(series.index)
        return series.sort_index()
    except Exception as exc:
        logger.debug("FX cache load failed for %s: %s", currency, exc)
        return None


def _needs_refresh(series: Optional[pd.Series]) -> bool:
    """Return True if the cached series is missing or stale (>30 days old)."""
    if series is None or series.empty:
        return True
    latest = series.index[-1]
    age_days = (pd.Timestamp.now() - latest).days
    return age_days > 30


def _download_rates(
    from_ccy: str,
    start: str = "2014-01-01",
) -> Optional[pd.Series]:
    """Download daily close FX rates from yfinance."""
    import yfinance as yf

    inverted = from_ccy in _INVERSE
    if from_ccy in _DIRECT:
        ticker_sym = _DIRECT[from_ccy]
    elif from_ccy in _INVERSE:
        ticker_sym = _INVERSE[from_ccy]
    else:
        logger.debug("No yfinance ticker for %s/USD — skipping", from_ccy)
        return None

    for attempt in range(3):
        try:
            df = yf.download(ticker_sym, start=start, progress=False, auto_adjust=True)
            if df is None or df.empty:
                return None

            # Use "Close" column
            if "Close" in df.columns:
                close = df["Close"].squeeze()
            else:
                close = df.iloc[:, 0]

            close = close.dropna().astype(float)
            if inverted:
                # USD per foreign = 1 / (foreign per USD)
                close = 1.0 / close.replace(0, float("nan"))
                close = close.dropna()

            close.name = "rate"
            close.index = pd.to_datetime(close.index)
            return close.sort_index()

        except Exception as exc:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            logger.debug("FX download failed for %s (%s): %s", from_ccy, ticker_sym, exc)
            return None

    return None


def _save_cache(series: pd.Series, p: Path) -> None:
    try:
        df = series.to_frame(name="rate")
        df.to_parquet(p)
    except Exception as exc:
        logger.debug("FX cache save failed: %s", exc)
