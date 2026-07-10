"""Universe stand-in: point-in-time S&P 500 membership ∪ current iShares
mid/small holdings, per-week floors applied strictly as-of. Mcap floor is
NOT applied (no point-in-time share counts) — ADV is the liquidity proxy;
the report discloses this."""
import csv
from pathlib import Path
from typing import Dict, List, Optional, Set

import pandas as pd

from execution.constants import FUNNEL_PRICE_FLOOR, THEME_ADV_FLOOR_USD

_MIN_ROWS = 63  # matches execution.funnel.screen._MIN_ROWS


def parse_ishares_csv(path: Path) -> List[str]:
    """iShares holdings CSVs carry a preamble; the table starts at the row
    whose first cell is 'Ticker'. Equity rows only; '.'→'-' for yfinance."""
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.reader(fh))
    header_idx = next(i for i, r in enumerate(rows) if r and r[0].strip() == "Ticker")
    header = rows[header_idx]
    t_col, a_col = header.index("Ticker"), header.index("Asset Class")
    out: List[str] = []
    for r in rows[header_idx + 1:]:
        if len(r) <= max(t_col, a_col) or r[a_col].strip() != "Equity":
            continue
        sym = r[t_col].strip().replace(".", "-").upper()
        if sym and sym != "--":
            out.append(sym)
    return out


def load_universe(csv_dir: Path) -> List[str]:
    syms = set()
    for p in sorted(Path(csv_dir).glob("*.csv")):
        syms.update(parse_ishares_csv(p))
    return sorted(syms)


def load_pit_membership(csv_path: Path) -> pd.DataFrame:
    """Canonical ticker,date_added,date_removed CSV (the format written by
    scripts/backtest/data/sp500_constituents.py --download)."""
    df = pd.read_csv(csv_path, parse_dates=["date_added", "date_removed"])
    df["ticker"] = (df["ticker"].astype(str).str.strip()
                    .str.replace(".", "-", regex=False).str.upper())
    return df


def members_asof(pit: pd.DataFrame, asof: pd.Timestamp) -> Set[str]:
    live = pit[(pit["date_added"] <= asof)
               & (pit["date_removed"].isna() | (pit["date_removed"] > asof))]
    return set(live["ticker"])


def eligible_asof(ohlcv: Dict[str, pd.DataFrame], asof: pd.Timestamp,
                  allowed: Optional[Set[str]] = None) -> List[str]:
    """Price and 20d dollar-ADV floors from data ≤ asof only; `allowed`
    (when given) is the point-in-time membership union."""
    out: List[str] = []
    for sym, df in ohlcv.items():
        if allowed is not None and sym not in allowed:
            continue
        win = df.loc[:asof]
        if len(win) < _MIN_ROWS:
            continue
        price = float(win["Close"].iloc[-1])
        adv = float((win["Close"] * win["Volume"]).tail(20).mean())
        if price >= FUNNEL_PRICE_FLOOR and adv >= THEME_ADV_FLOOR_USD:
            out.append(sym)
    return sorted(out)
