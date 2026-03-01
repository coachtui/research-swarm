"""
Point-in-Time S&P 500 Constituent Provider
===========================================

Provides membership snapshots that change through time so the backtest
universe reflects what was actually investable on each rebalance date.
Without PIT membership the backtest suffers survivorship bias (only
stocks that survived to today appear in the universe).

DATA SOURCES (in preference order)
───────────────────────────────────
1. Local CSV at data/sp500_historical_constituents.csv  (recommended)
   Columns: ticker, date_added, date_removed
   date_removed is empty / NaT for current members.

   Obtain from any of:
     • Norgate Data  — norgate.com
     • Sharadar SF1  — data.nasdaq.com/databases/SFA
     • CRSP via WRDS — wrds.upenn.edu
     • GitHub: https://github.com/fja05680/sp500
       → python -m scripts.backtest.data.sp500_constituents --download

2. Wikipedia (survivorship-biased, MVP only)
   Requires --allow-survivorship-bias flag to be set before import.
   Prints a large warning and falls back gracefully.

USAGE
─────
    from scripts.backtest.data.sp500_constituents import (
        get_constituents,
        set_survivorship_bias_ok,
        download_constituents_csv,
    )

    # Allow Wikipedia fallback (survivorship-biased)
    set_survivorship_bias_ok(True)

    members = get_constituents(date(2018, 6, 30))   # → list[str]
"""

from __future__ import annotations

import io
import logging
import sys
import time
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ── Module-level state ────────────────────────────────────────────────────────
_df: Optional[pd.DataFrame] = None           # loaded CSV
_cache: dict[date, list[str]] = {}           # date → tickers cache
_csv_path: Optional[Path] = None             # resolved CSV path
_survivorship_bias_ok: bool = False          # set via set_survivorship_bias_ok()

# S&P 500 Wikipedia fallback (current list only)
_WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

# fja05680/sp500 GitHub — stable ticker start/end CSV (already in add/remove format)
_FJA_CSV_URL = (
    "https://raw.githubusercontent.com/fja05680/sp500/master/"
    "sp500_ticker_start_end.csv"
)


# ── Public API ─────────────────────────────────────────────────────────────────


def set_survivorship_bias_ok(ok: bool) -> None:
    """Allow Wikipedia fallback when no PIT CSV is available."""
    global _survivorship_bias_ok
    _survivorship_bias_ok = ok


def get_constituents(as_of: date, csv_path: Optional[Path] = None) -> list[str]:
    """
    Return S&P 500 members as of *as_of* date.

    Members are tickers where:
        date_added <= as_of  AND  (date_removed is NaT OR date_removed > as_of)

    Raises
    ------
    RuntimeError
        If no PIT CSV is found and survivorship bias mode is not enabled.
    """
    global _df, _csv_path

    # Resolve CSV path
    if csv_path is None and _csv_path is None:
        _csv_path = _find_csv()
    if csv_path is not None:
        _csv_path = csv_path

    # Load CSV if needed
    if _df is None:
        if _csv_path is not None and _csv_path.exists():
            _df = _load_csv(_csv_path)
            logger.info("S&P 500 constituents loaded from %s (%d rows)", _csv_path, len(_df))
        else:
            _df = _get_fallback_df(as_of)
            if _df is None:
                raise RuntimeError(
                    "\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    " SURVIVORSHIP BIAS ERROR\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    " No point-in-time S&P 500 constituent file found.\n"
                    " Without this file the backtest has survivorship bias\n"
                    " (only today's survivors appear in the universe).\n\n"
                    " To fix:\n"
                    "   python -m scripts.backtest.data.sp500_constituents --download\n\n"
                    " To override (survivorship-biased results):\n"
                    "   Pass --allow-survivorship-bias to backtest_t1.py\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                )

    # Return from cache if available
    if as_of in _cache:
        return _cache[as_of]

    # Filter to members on as_of date
    df = _df
    added_ok = df["date_added"] <= pd.Timestamp(as_of)
    removed_ok = df["date_removed"].isna() | (df["date_removed"] > pd.Timestamp(as_of))
    members = df.loc[added_ok & removed_ok, "ticker"].tolist()

    _cache[as_of] = members
    return members


def get_all_tickers_ever(start: date, end: date) -> list[str]:
    """
    Return the union of all tickers that were S&P 500 members at any point
    between start and end.  Used to pre-warm the price and fundamentals cache.
    """
    global _df, _csv_path

    # Resolve CSV path (same logic as get_constituents)
    if _csv_path is None:
        _csv_path = _find_csv()

    if _df is None:
        if _csv_path is not None and _csv_path.exists():
            _df = _load_csv(_csv_path)
            logger.info("S&P 500 constituents loaded from %s (%d rows)", _csv_path, len(_df))
        else:
            _df = _get_fallback_df(start)
            if _df is None:
                raise RuntimeError(
                    "\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    " SURVIVORSHIP BIAS ERROR\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    " No point-in-time S&P 500 constituent file found.\n\n"
                    " To fix:\n"
                    "   python -m scripts.backtest.data.sp500_constituents --download\n\n"
                    " To override (survivorship-biased results):\n"
                    "   Pass --allow-survivorship-bias to backtest_t1.py\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                )

    df = _df
    # Tickers that were active at any point within [start, end]
    was_added_before_end = df["date_added"] <= pd.Timestamp(end)
    removed_after_start = df["date_removed"].isna() | (df["date_removed"] >= pd.Timestamp(start))
    return df.loc[was_added_before_end & removed_after_start, "ticker"].unique().tolist()


def download_constituents_csv(output_path: Path) -> None:
    """
    Download S&P 500 historical constituents from the fja05680/sp500
    GitHub repository and convert to the canonical CSV format.

    Source: sp500_ticker_start_end.csv — already has ticker, start_date, end_date.

    Canonical format:
        ticker,date_added,date_removed

    Run once as a setup step:
        python -m scripts.backtest.data.sp500_constituents --download
    """
    try:
        import requests
    except ImportError:
        logger.error("requests library required: pip install requests")
        return

    logger.info("Downloading S&P 500 historical components from GitHub…")
    r = requests.get(_FJA_CSV_URL, timeout=30)
    r.raise_for_status()

    # sp500_ticker_start_end.csv columns: ticker, start_date, end_date
    df = pd.read_csv(io.StringIO(r.text), dtype=str)

    if not {"ticker", "start_date", "end_date"}.issubset(df.columns):
        logger.error("Unexpected columns in fja05680 CSV: %s", list(df.columns))
        return

    # Normalise to canonical column names
    df = df.rename(columns={"start_date": "date_added", "end_date": "date_removed"})
    df["ticker"] = df["ticker"].str.upper().str.strip().str.replace(".", "-", regex=False)
    df["date_added"] = pd.to_datetime(df["date_added"], errors="coerce").dt.strftime("%Y-%m-%d")
    df["date_removed"] = pd.to_datetime(df["date_removed"], errors="coerce").dt.strftime("%Y-%m-%d")
    df["date_removed"] = df["date_removed"].fillna("")

    # Drop rows with unparseable date_added
    bad = df["date_added"].isna() | (df["date_added"] == "NaT")
    if bad.any():
        logger.warning("Dropping %d rows with unparseable date_added", bad.sum())
        df = df[~bad]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df[["ticker", "date_added", "date_removed"]].to_csv(output_path, index=False)

    logger.info("Wrote %d constituent records → %s", len(df), output_path)


# ── Internal helpers ──────────────────────────────────────────────────────────


def _find_csv() -> Optional[Path]:
    """Search for the constituents CSV in known locations."""
    from scripts.backtest.config import SP500_CONSTITUENTS_CSV
    project_root = Path(__file__).parent.parent.parent.parent  # scripts/backtest/data → project root
    candidates = [
        project_root / SP500_CONSTITUENTS_CSV,
        Path(SP500_CONSTITUENTS_CSV),
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _load_csv(path: Path) -> pd.DataFrame:
    """Load and validate the constituents CSV."""
    df = pd.read_csv(path, dtype=str)

    required = {"ticker", "date_added", "date_removed"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Constituent CSV missing columns: {missing}")

    df["ticker"] = df["ticker"].str.upper().str.strip().str.replace(".", "-", regex=False)
    df["date_added"] = pd.to_datetime(df["date_added"], errors="coerce")
    df["date_removed"] = pd.to_datetime(df["date_removed"], errors="coerce")  # NaT for empty

    # Drop rows with unparseable dates
    bad = df["date_added"].isna()
    if bad.any():
        logger.warning("Dropping %d rows with unparseable date_added", bad.sum())
        df = df[~bad]

    return df.reset_index(drop=True)


def _get_fallback_df(as_of: date) -> Optional[pd.DataFrame]:
    """
    Wikipedia fallback — survivorship biased.
    Only used when _survivorship_bias_ok is True.
    """
    if not _survivorship_bias_ok:
        return None

    _print_survivorship_warning()

    try:
        tables = pd.read_html(_WIKI_URL, attrs={"id": "constituents"})
        tickers = tables[0]["Symbol"].str.upper().str.strip().str.replace(".", "-", regex=False)
        df = pd.DataFrame({
            "ticker": tickers,
            "date_added": pd.Timestamp("1990-01-01"),   # conservative start
            "date_removed": pd.NaT,
        })
        logger.info("Wikipedia fallback: loaded %d current S&P 500 members", len(df))
        return df
    except Exception as exc:
        logger.error("Wikipedia fallback failed: %s", exc)
        return None


def _print_survivorship_warning() -> None:
    msg = (
        "\n"
        "╔══════════════════════════════════════════════════════════════╗\n"
        "║  ⚠  SURVIVORSHIP BIAS WARNING                               ║\n"
        "╠══════════════════════════════════════════════════════════════╣\n"
        "║  Using Wikipedia (current S&P 500 members) as universe.     ║\n"
        "║  Delisted / removed companies are EXCLUDED from history.    ║\n"
        "║  This OVERSTATES backtest returns — treat results as        ║\n"
        "║  an UPPER BOUND, not a realistic estimate.                  ║\n"
        "║                                                              ║\n"
        "║  For unbiased results:                                       ║\n"
        "║    python -m scripts.backtest.data.sp500_constituents \\     ║\n"
        "║            --download                                        ║\n"
        "╚══════════════════════════════════════════════════════════════╝\n"
    )
    print(msg, file=sys.stderr, flush=True)


# ── CLI entry-point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    parser = argparse.ArgumentParser(description="S&P 500 constituent data utility")
    parser.add_argument("--download", action="store_true", help="Download PIT constituent CSV")
    parser.add_argument(
        "--out", type=Path, default=None,
        help="Output path (default: data/sp500_historical_constituents.csv)",
    )
    args = parser.parse_args()

    if args.download:
        project_root = Path(__file__).parent.parent.parent.parent
        from scripts.backtest.config import SP500_CONSTITUENTS_CSV
        out = args.out or (project_root / SP500_CONSTITUENTS_CSV)
        download_constituents_csv(out)
    else:
        parser.print_help()
