"""Market-data fetch layer for the outlook engine.

Wraps the existing MarketDataClient (yfinance, cached, rate-limited).
Failure posture: if the benchmark or too many sector ETFs are missing,
raise OutlookDataError so the weekly job skips the week instead of
producing an outlook from partial data.
"""
import logging
from typing import Dict, Iterable

import pandas as pd

from research_swarm.data.market_data_client import MarketDataClient

from execution.constants import BENCHMARK, EQUAL_WEIGHT, SECTOR_ETFS, VIX

logger = logging.getLogger(__name__)

_MAX_MISSING_ETFS = 3


class OutlookDataError(Exception):
    """Market data too incomplete to produce a trustworthy outlook."""


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


def fetch_ohlcv_batch(tickers: Iterable[str], period: str = "1y") -> Dict[str, pd.DataFrame]:
    """Batched OHLCV download. Returns {ticker: DataFrame[Open,High,Low,Close,Volume]}.
    Tickers with no data are omitted — callers treat absence as 'skip this name'."""
    import yfinance as yf  # noqa: PLC0415 — heavy import stays local

    symbols = [t for t in dict.fromkeys(tickers) if t]
    if not symbols:
        return {}
    try:
        raw = yf.download(
            tickers=" ".join(symbols), period=period, interval="1d",
            group_by="ticker", auto_adjust=True, progress=False, threads=True,
        )
    except Exception:  # noqa: BLE001 — one bad ticker must not sink the batch
        logger.exception("fetch_ohlcv_batch: download failed")
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
        except (KeyError, IndexError):  # noqa: BLE001 — one bad ticker must not sink the batch
            continue
    return out
