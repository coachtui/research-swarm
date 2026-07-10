"""OHLCV download + parquet cache. The only backtest module that touches
the network — and only in fetch_ohlcv. auto_adjust=True: splits/dividends
folded in, matching what the live screen sees from yfinance."""
import logging
from pathlib import Path
from typing import Dict, Iterable, List

import pandas as pd
import yfinance as yf

from execution.constants import BENCHMARK, EQUAL_WEIGHT, SECTOR_ETFS, VIX

logger = logging.getLogger(__name__)

MARKET_SYMBOLS = (BENCHMARK, EQUAL_WEIGHT, VIX, *SECTOR_ETFS)
START, END = "2014-07-01", "2026-07-01"
COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


def _cache_path(cache_dir: Path, sym: str) -> Path:
    return Path(cache_dir) / f"{sym.replace('^', '_IDX_')}.parquet"


def fetch_ohlcv(symbols: Iterable[str], cache_dir: Path,
                start: str = START, end: str = END,
                batch_size: int = 100) -> List[str]:
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    missing = [s for s in symbols if not _cache_path(cache_dir, s).exists()]
    written: List[str] = []
    for i in range(0, len(missing), batch_size):
        chunk = missing[i:i + batch_size]
        data = yf.download(chunk, start=start, end=end, auto_adjust=True,
                           group_by="ticker", progress=False, threads=True)
        for sym in chunk:
            try:
                df = data[sym] if len(chunk) > 1 or isinstance(
                    data.columns, pd.MultiIndex) else data
            except KeyError:
                logger.warning("no data returned for %s", sym)
                continue
            df = df.dropna(how="all")
            if df.empty:
                logger.warning("empty history for %s", sym)
                continue
            df[COLUMNS].to_parquet(_cache_path(cache_dir, sym))
            written.append(sym)
    return written


def load_ohlcv(cache_dir: Path, min_rows: int = 63) -> Dict[str, pd.DataFrame]:
    out: Dict[str, pd.DataFrame] = {}
    for p in sorted(Path(cache_dir).glob("*.parquet")):
        df = pd.read_parquet(p)
        if len(df) >= min_rows:
            out[p.stem.replace("_IDX_", "^")] = df
    return out
