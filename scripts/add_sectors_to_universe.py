"""One-off: annotate sp500_universe.json with SPDR-style sector names via yfinance.

Adds a top-level "sectors" object {ticker: sector} alongside the existing
"tickers" list (which is left untouched). Resumable — reruns skip tickers
already annotated. Sector names are normalized to the SPDR names used by
MarketOutlook.sectorRankings (see execution/constants.py SECTOR_ETFS).
"""
import json
import time
from pathlib import Path

import yfinance as yf

UNIVERSE = (
    Path(__file__).resolve().parents[1]
    / "research_swarm" / "data" / "universes" / "sp500_universe.json"
)

YF_TO_SPDR = {
    "Technology": "Technology",
    "Financial Services": "Financials",
    "Healthcare": "Health Care",
    "Consumer Cyclical": "Consumer Discretionary",
    "Consumer Defensive": "Consumer Staples",
    "Communication Services": "Communication Services",
    "Industrials": "Industrials",
    "Energy": "Energy",
    "Utilities": "Utilities",
    "Basic Materials": "Materials",
    "Real Estate": "Real Estate",
}


def main() -> None:
    data = json.loads(UNIVERSE.read_text())
    sectors = data.get("sectors", {})
    missing = [t for t in data["tickers"] if t not in sectors]
    print(f"{len(missing)} tickers to annotate")

    for ticker in missing:
        try:
            raw = yf.Ticker(ticker).info.get("sector")
        except Exception as e:
            print(f"ERROR   {ticker}: {e}")
            continue
        mapped = YF_TO_SPDR.get(raw)
        if mapped:
            sectors[ticker] = mapped
            print(f"ok      {ticker}: {mapped}")
        else:
            print(f"UNMAPPED {ticker}: {raw!r}")
        time.sleep(0.3)  # be polite to Yahoo

    data["sectors"] = dict(sorted(sectors.items()))
    UNIVERSE.write_text(json.dumps(data, indent=2) + "\n")
    print(f"done: {len(sectors)}/{len(data['tickers'])} annotated")


if __name__ == "__main__":
    main()
