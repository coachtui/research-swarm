"""Market-data fetch layer for the outlook engine.

Wraps the existing MarketDataClient (yfinance, cached, rate-limited).
Failure posture: if the benchmark or too many sector ETFs are missing,
raise OutlookDataError so the weekly job skips the week instead of
producing an outlook from partial data.
"""
import logging
import random
import time
from datetime import date
from typing import Dict, Iterable, List, Optional

import pandas as pd

from research_swarm.data.market_data_client import MarketDataClient

from execution.constants import BENCHMARK, EQUAL_WEIGHT, SECTOR_ETFS, VIX

logger = logging.getLogger(__name__)

_MAX_MISSING_ETFS = 3

# Seconds to wait between OHLCV download attempts; len(...) + 1 = total attempts.
# Yahoo's 429 cleared in ~33s on 2026-08-20 (the SPY fetch failed at 21:15:46 and
# succeeded at 21:16:19), so a ladder topping out around half a minute is the
# shape that recovers. Every caller is a cron step running off the event loop,
# so the wait costs latency nobody is waiting on.
_OHLCV_RETRY_BACKOFF = (5.0, 20.0)


class OutlookDataError(Exception):
    """Market data too incomplete to produce a trustworthy outlook."""


def latest_bar_date(df: Optional[pd.DataFrame]) -> Optional[date]:
    """Calendar date of the last row of an OHLCV frame, or None when the frame
    carries no usable date.

    MarketDataClient returns the SAME data in two shapes: a fresh fetch keeps
    yfinance's DatetimeIndex, while a cache hit is rebuilt from JSON and carries
    the date as a plain string column instead. A caller that needs to know which
    session a close belongs to — the daily cron, checking that today's benchmark
    is actually today's — has to handle both, and must get None rather than a
    guess when neither shape is present.
    """
    if df is None or len(df) == 0:
        return None
    columns = getattr(df, "columns", None)
    if columns is not None and "Date" in columns:
        try:
            return pd.to_datetime(df["Date"].iloc[-1]).date()
        except Exception:  # noqa: BLE001 — an unparseable date is "unknown", not fatal
            return None
    if isinstance(df.index, pd.DatetimeIndex):
        return df.index[-1].date()
    return None  # RangeIndex and friends carry no date at all


def fetch_history_for(tickers: Iterable[str], period: str = "1y") -> Dict[str, pd.Series]:
    """Best-effort close-series fetch. Missing tickers are simply absent.

    Callers own their completeness policy (fetch_market_history raises on
    missing benchmarks; the Phase 3A passes degrade to null + alert).
    """
    client = MarketDataClient()
    closes: Dict[str, pd.Series] = {}
    for ticker in tickers:
        df = client.get_historical_data(ticker, period=period)
        if df is None or "Close" not in df or df["Close"].dropna().empty:
            logger.warning("No history for %s", ticker)
            continue
        closes[ticker] = df["Close"].dropna().reset_index(drop=True)
    return closes


def fetch_market_history(period: str = "1y") -> Dict[str, pd.Series]:
    closes = fetch_history_for(list(SECTOR_ETFS) + [BENCHMARK, EQUAL_WEIGHT, VIX], period)

    if BENCHMARK not in closes:
        raise OutlookDataError("SPY history unavailable — cannot compute outlook")
    missing_etfs = [t for t in SECTOR_ETFS if t not in closes]
    if len(missing_etfs) > _MAX_MISSING_ETFS:
        raise OutlookDataError(
            f"{len(missing_etfs)} sector ETFs missing ({missing_etfs}) — refusing partial outlook"
        )
    return closes


def fetch_closes_batch(tickers: Iterable[str], period: str = "1y") -> Dict[str, pd.Series]:
    """ONE yf.download for many tickers (theme constituents — up to ~240).

    Best-effort: missing/empty tickers are simply absent. Bypasses the
    per-ticker MarketDataClient deliberately — 240 sequential cached fetches
    in the Sunday cron is the failure mode this avoids.
    """
    import yfinance as yf  # noqa: PLC0415

    unique = sorted({t.upper() for t in tickers if t})
    if not unique:
        return {}
    try:
        df = yf.download(unique, period=period, auto_adjust=True,
                         progress=False, group_by="ticker", threads=True)
    except Exception:
        logger.exception("fetch_closes_batch: download failed")
        return {}
    if df is None or df.empty:
        return {}
    out: Dict[str, pd.Series] = {}
    if not isinstance(df.columns, pd.MultiIndex):  # single-ticker shape
        series = df.get("Close")
        if series is not None and not series.dropna().empty:
            out[unique[0]] = series.dropna().reset_index(drop=True)
        return out
    for ticker in unique:
        try:
            series = df[ticker]["Close"].dropna()
        except (KeyError, IndexError):
            continue
        if not series.empty:
            out[ticker] = series.reset_index(drop=True)
    return out


def _download_ohlcv(symbols: List[str], period: str) -> Dict[str, pd.DataFrame]:
    """One yf.download attempt. Empty result == nothing usable came back."""
    import yfinance as yf  # noqa: PLC0415 — heavy import stays local

    try:
        raw = yf.download(
            tickers=" ".join(symbols), period=period, interval="1d",
            group_by="ticker", auto_adjust=True, progress=False, threads=True,
        )
    except Exception:
        logger.exception("fetch_ohlcv_batch: download failed")
        return {}
    if raw is None or raw.empty:
        return {}
    out: Dict[str, pd.DataFrame] = {}
    if not isinstance(raw.columns, pd.MultiIndex):  # single-ticker shape
        df = raw[["Open", "High", "Low", "Close", "Volume"]].dropna()
        if not df.empty:
            out[symbols[0]] = df
        return out
    for sym in symbols:
        try:
            df = raw[sym][["Open", "High", "Low", "Close", "Volume"]].dropna()
            if not df.empty:
                out[sym] = df
        except (KeyError, IndexError):  # one bad ticker must not sink the batch
            continue
    return out


def fetch_ohlcv_batch(tickers: Iterable[str], period: str = "1y") -> Dict[str, pd.DataFrame]:
    """Batched OHLCV download. Returns {ticker: DataFrame[Open,High,Low,Close,Volume]}.
    Tickers with no data are omitted — callers treat absence as 'skip this name'.

    Retries ONLY a completely empty result. That is the rate-limit signature:
    yfinance answers a 429 by logging "N Failed downloads" and handing back an
    empty frame WITHOUT raising, so the except above never fires and the whole
    batch vanishes at once — which is how every Sleeve A holding lost its bar on
    2026-08-20 and the day's snapshot was skipped. A batch that returns some
    names is a different event: one delisted or misspelled ticker among ten, and
    making that pay the backoff on every run would be a pointless tax.
    """
    symbols = list(dict.fromkeys(t.upper() for t in tickers if t))
    if not symbols:
        return {}

    for pause in (*_OHLCV_RETRY_BACKOFF, None):
        out = _download_ohlcv(symbols, period)
        if out:
            return out
        if pause is None:
            break
        # Jitter so the daily cron's three back-to-back batches (fills, stops,
        # snapshot) do not retry in lockstep against a provider already saying no.
        delay = pause + random.uniform(0.0, pause * 0.25)
        logger.warning(
            "fetch_ohlcv_batch: no data for any of %d symbols — retrying in %.1fs",
            len(symbols), delay,
        )
        time.sleep(delay)

    logger.error(
        "fetch_ohlcv_batch: no data for any of %d symbols after %d attempts (%s)",
        len(symbols), len(_OHLCV_RETRY_BACKOFF) + 1, ", ".join(symbols[:10]),
    )
    return {}


def fetch_weekly_closes(tickers: Iterable[str], period: str = "5y") -> Dict[str, pd.Series]:
    """Weekly closes for the 200-week MA advisory input. Small symbol sets
    ONLY — holdings + top-ranked candidates, never the full screening
    universe. Mirrors fetch_ohlcv_batch's batched-download / best-effort
    posture, just at interval='1wk'."""
    import yfinance as yf  # noqa: PLC0415 — heavy import stays local

    symbols = list(dict.fromkeys(t.upper() for t in tickers if t))
    if not symbols:
        return {}
    try:
        raw = yf.download(
            tickers=" ".join(symbols), period=period, interval="1wk",
            group_by="ticker", auto_adjust=True, progress=False, threads=True,
        )
    except Exception:
        logger.exception("fetch_weekly_closes: download failed")
        return {}
    if raw is None or raw.empty:
        return {}
    out: Dict[str, pd.Series] = {}
    if not isinstance(raw.columns, pd.MultiIndex):  # single-ticker shape
        series = raw.get("Close")
        if series is not None and not series.dropna().empty:
            out[symbols[0]] = series.dropna()
        return out
    for sym in symbols:
        try:
            series = raw[sym]["Close"].dropna()
        except (KeyError, IndexError):  # one bad ticker must not sink the batch
            continue
        if not series.empty:
            out[sym] = series
    return out


def dist_200wma(weekly_closes: Optional[pd.Series]) -> Optional[float]:
    """Price distance from the 200-week SMA: price / 200w-SMA - 1.
    None when there aren't yet 200 weekly bars (new listing) or the series
    is absent (fetch failure) — an advisory input degrades to null, never
    blocks the screen."""
    if weekly_closes is None or len(weekly_closes) < 200:
        return None
    sma = float(weekly_closes.rolling(200).mean().iloc[-1])
    return float(weekly_closes.iloc[-1] / sma - 1.0) if sma > 0 else None
