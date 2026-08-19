"""
Deterministic macro / market-state snapshot.

One scan of the world per interval, shared by every analysis that runs against
it. Nothing here is company-specific and nothing here is LLM-generated: it is
index levels, volatility, rates, currencies, commodities, sector rotation, and
regional performance, all computed arithmetically from price series.

The point is attribution, not prediction. Without this layer the pipeline sees
only the company's own chart, so a market-wide drawdown, a sector rotation, or
a currency shock reads as company-specific weakness. Supplying the state of the
world lets the analysis say how much of a move belongs to the company and how
much belongs to the tape.

The interpretive half — which geopolitical events are live and how they
transmit — is `macro_brief.py`. This module deliberately contains no judgment,
so it can be cached and shared without contaminating any single ticker's read.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from research_swarm.logger import logger

# ── The instrument set ───────────────────────────────────────────────────────
# Chosen so that the common transmission channels are each observable:
# broad equity, volatility, the rates curve, the dollar, energy/metals, sector
# rotation, and the regional blocs that drive cross-border shocks.

BROAD_INDICES = {
    "SPY": "S&P 500",
    "QQQ": "Nasdaq 100",
    "IWM": "Russell 2000 (small caps)",
}

RISK_INSTRUMENTS = {
    "^VIX": "VIX (equity volatility)",
    "^TNX": "US 10Y Treasury yield",
    "^IRX": "US 3M T-bill yield",
    "DX-Y.NYB": "US Dollar Index",
    "JPY=X": "USD/JPY",
    "CL=F": "WTI crude oil",
    "GC=F": "Gold",
    "HG=F": "Copper",
}

SECTOR_ETFS = {
    "XLK": "Technology",
    "XLF": "Financials",
    "XLV": "Healthcare",
    "XLE": "Energy",
    "XLI": "Industrials",
    "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples",
    "XLB": "Materials",
    "XLU": "Utilities",
    "XLRE": "Real Estate",
    "XLC": "Communication Services",
}

# Regional blocs — these are how a country-level shock (a BOJ hike, a Korean
# deleveraging episode, a China stimulus) becomes visible without needing
# per-company revenue geography.
REGION_ETFS = {
    "EWJ": "Japan",
    "EWY": "South Korea",
    "FXI": "China (large cap)",
    "EZU": "Eurozone",
    "EEM": "Emerging Markets",
    "EWT": "Taiwan",
}

# Sectors that historically lead in risk-off vs risk-on tape.
DEFENSIVE_SECTORS = ("XLP", "XLU", "XLV")
CYCLICAL_SECTORS = ("XLY", "XLI", "XLB", "XLF")


@dataclass
class InstrumentMove:
    symbol: str
    label: str
    last: Optional[float] = None
    return_1d: Optional[float] = None
    return_1m: Optional[float] = None
    return_3m: Optional[float] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "label": self.label,
            "last": self.last,
            "return_1d": self.return_1d,
            "return_1m": self.return_1m,
            "return_3m": self.return_3m,
        }


@dataclass
class MacroSnapshot:
    """Deterministic state of the world. No company in scope, no judgment."""

    as_of: str
    indices: Dict[str, InstrumentMove] = field(default_factory=dict)
    risk: Dict[str, InstrumentMove] = field(default_factory=dict)
    sectors: Dict[str, InstrumentMove] = field(default_factory=dict)
    regions: Dict[str, InstrumentMove] = field(default_factory=dict)

    # Derived, still deterministic
    regime: str = "unknown"
    regime_rationale: str = ""
    yield_curve_slope: Optional[float] = None
    sector_leaders: List[str] = field(default_factory=list)
    sector_laggards: List[str] = field(default_factory=list)
    region_leaders: List[str] = field(default_factory=list)
    region_laggards: List[str] = field(default_factory=list)
    coverage_pct: float = 0.0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "as_of": self.as_of,
            "indices": {k: v.as_dict() for k, v in self.indices.items()},
            "risk": {k: v.as_dict() for k, v in self.risk.items()},
            "sectors": {k: v.as_dict() for k, v in self.sectors.items()},
            "regions": {k: v.as_dict() for k, v in self.regions.items()},
            "regime": self.regime,
            "regime_rationale": self.regime_rationale,
            "yield_curve_slope": self.yield_curve_slope,
            "sector_leaders": self.sector_leaders,
            "sector_laggards": self.sector_laggards,
            "region_leaders": self.region_leaders,
            "region_laggards": self.region_laggards,
            "coverage_pct": self.coverage_pct,
        }


def _pct_return(series, days: int) -> Optional[float]:
    """Percent return over the trailing N trading days."""
    try:
        if series is None or len(series) < 2:
            return None
        window = series.dropna()
        if len(window) < 2:
            return None
        end = float(window.iloc[-1])
        start_idx = max(0, len(window) - 1 - days)
        start = float(window.iloc[start_idx])
        if start == 0:
            return None
        return round((end / start - 1) * 100, 2)
    except Exception:
        return None


def _fetch_one(symbol: str, label: str) -> InstrumentMove:
    """Fetch one instrument's move profile. Failures degrade to empty."""
    from research_swarm.data.market_data_client import market_data_client

    move = InstrumentMove(symbol=symbol, label=label)
    try:
        df = market_data_client.get_historical_data(symbol, period="6mo")
        if df is None or df.empty or "Close" not in df:
            logger.debug(f"[Macro] No data for {symbol}")
            return move
        close = df["Close"].dropna()
        if close.empty:
            return move
        move.last = round(float(close.iloc[-1]), 2)
        move.return_1d = _pct_return(close, 1)
        move.return_1m = _pct_return(close, 21)
        move.return_3m = _pct_return(close, 63)
    except Exception as e:
        logger.debug(f"[Macro] Failed to fetch {symbol}: {e}")
    return move


def _classify_regime(
    spy: Optional[InstrumentMove],
    vix: Optional[InstrumentMove],
    sectors: Dict[str, InstrumentMove],
) -> tuple[str, str]:
    """Label the tape from volatility, direction, and defensive leadership.

    Deliberately coarse. The goal is to stop a report from narrating a
    market-wide drawdown as company weakness, which needs only a reliable
    coarse read — not a precise one.
    """
    reasons: List[str] = []

    spy_1m = spy.return_1m if spy else None
    vix_level = vix.last if vix else None

    # Defensive vs cyclical leadership over 1 month
    def _avg(symbols) -> Optional[float]:
        vals = [
            sectors[s].return_1m
            for s in symbols
            if s in sectors and sectors[s].return_1m is not None
        ]
        return sum(vals) / len(vals) if vals else None

    defensive = _avg(DEFENSIVE_SECTORS)
    cyclical = _avg(CYCLICAL_SECTORS)
    rotation = (defensive - cyclical) if (defensive is not None and cyclical is not None) else None

    risk_off_votes = 0
    risk_on_votes = 0

    if vix_level is not None:
        if vix_level >= 25:
            risk_off_votes += 1
            reasons.append(f"VIX elevated at {vix_level:.1f}")
        elif vix_level <= 15:
            risk_on_votes += 1
            reasons.append(f"VIX subdued at {vix_level:.1f}")
        else:
            reasons.append(f"VIX moderate at {vix_level:.1f}")

    if spy_1m is not None:
        if spy_1m <= -4.0:
            risk_off_votes += 1
            reasons.append(f"S&P down {abs(spy_1m):.1f}% over 1M")
        elif spy_1m >= 4.0:
            risk_on_votes += 1
            reasons.append(f"S&P up {spy_1m:.1f}% over 1M")
        else:
            reasons.append(f"S&P roughly flat over 1M ({spy_1m:+.1f}%)")

    if rotation is not None:
        if rotation >= 2.0:
            risk_off_votes += 1
            reasons.append(f"defensives leading cyclicals by {rotation:.1f}pp")
        elif rotation <= -2.0:
            risk_on_votes += 1
            reasons.append(f"cyclicals leading defensives by {abs(rotation):.1f}pp")

    if risk_off_votes >= 2:
        regime = "risk-off"
    elif risk_on_votes >= 2:
        regime = "risk-on"
    else:
        regime = "mixed"

    return regime, "; ".join(reasons)


def build_macro_snapshot() -> MacroSnapshot:
    """Fetch the full instrument set concurrently and derive the regime."""
    from concurrent.futures import ThreadPoolExecutor

    snapshot = MacroSnapshot(as_of=datetime.now().isoformat(timespec="seconds"))

    jobs: List[tuple[str, str, str]] = []  # (bucket, symbol, label)
    for sym, label in BROAD_INDICES.items():
        jobs.append(("indices", sym, label))
    for sym, label in RISK_INSTRUMENTS.items():
        jobs.append(("risk", sym, label))
    for sym, label in SECTOR_ETFS.items():
        jobs.append(("sectors", sym, label))
    for sym, label in REGION_ETFS.items():
        jobs.append(("regions", sym, label))

    logger.info(f"[Macro] Fetching {len(jobs)} instruments for the market-state snapshot")

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {
            pool.submit(_fetch_one, sym, label): (bucket, sym)
            for bucket, sym, label in jobs
        }
        for future, (bucket, sym) in futures.items():
            try:
                move = future.result()
            except Exception as e:
                logger.debug(f"[Macro] {sym} failed: {e}")
                continue
            getattr(snapshot, bucket)[sym] = move

    populated = sum(
        1
        for bucket in ("indices", "risk", "sectors", "regions")
        for m in getattr(snapshot, bucket).values()
        if m.last is not None
    )
    snapshot.coverage_pct = round(populated / len(jobs) * 100, 1) if jobs else 0.0

    # Yield curve slope (10Y − 3M), the standard recession/las-cycle read
    tnx = snapshot.risk.get("^TNX")
    irx = snapshot.risk.get("^IRX")
    if tnx and irx and tnx.last is not None and irx.last is not None:
        snapshot.yield_curve_slope = round(tnx.last - irx.last, 2)

    # Sector rotation ranking over 1 month
    ranked = sorted(
        (m for m in snapshot.sectors.values() if m.return_1m is not None),
        key=lambda m: m.return_1m,
        reverse=True,
    )
    snapshot.sector_leaders = [m.label for m in ranked[:3]]
    snapshot.sector_laggards = [m.label for m in ranked[-3:]][::-1]

    ranked_regions = sorted(
        (m for m in snapshot.regions.values() if m.return_1m is not None),
        key=lambda m: m.return_1m,
        reverse=True,
    )
    snapshot.region_leaders = [m.label for m in ranked_regions[:2]]
    snapshot.region_laggards = [m.label for m in ranked_regions[-2:]][::-1]

    snapshot.regime, snapshot.regime_rationale = _classify_regime(
        snapshot.indices.get("SPY"), snapshot.risk.get("^VIX"), snapshot.sectors
    )

    logger.success(
        f"[Macro] Snapshot complete: regime={snapshot.regime}, "
        f"coverage={snapshot.coverage_pct:.0f}%, curve={snapshot.yield_curve_slope}"
    )
    return snapshot
