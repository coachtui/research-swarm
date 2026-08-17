"""
Refresh the S&P 500 constituent list with canonical GICS sectors.

Writes research_swarm/data/universes/sp500_constituents.json — the universe
`calibrate_sector_medians.py` measures over. Grouping by this file's sectors
(not yfinance's taxonomy) is what keeps misfiled names like LYFT from
leaking into the wrong benchmark.

Run before each quarterly sector-median calibration.
"""

from __future__ import annotations

import io
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import requests

OUT = Path("research_swarm/data/universes/sp500_constituents.json")

# Wikipedia's GICS names → the keys our sector tables use
SECTOR_MAP = {
    "Information Technology": "Technology",
    "Health Care": "Healthcare",
    "Communication Services": "Communication Services",
    "Consumer Discretionary": "Consumer Discretionary",
    "Consumer Staples": "Consumer Staples",
    "Financials": "Financials",
    "Industrials": "Industrials",
    "Energy": "Energy",
    "Materials": "Materials",
    "Utilities": "Utilities",
    "Real Estate": "Real Estate",
}


def main() -> None:
    resp = requests.get(
        "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
        headers={"User-Agent": "Mozilla/5.0 (research-swarm calibration)"},
        timeout=30,
    )
    resp.raise_for_status()
    df = pd.read_html(io.StringIO(resp.text))[0]

    constituents = []
    for _, row in df.iterrows():
        sector = SECTOR_MAP.get(str(row["GICS Sector"]).strip())
        if not sector:
            print("unmapped sector:", row["GICS Sector"])
            continue
        constituents.append({
            "ticker": str(row["Symbol"]).strip().replace(".", "-"),  # BRK.B → BRK-B
            "sector": sector,
            "industry": str(row["GICS Sub-Industry"]).strip(),
        })

    OUT.write_text(json.dumps({
        "source": "Wikipedia: List of S&P 500 companies",
        "as_of": date.today().isoformat(),
        "count": len(constituents),
        "constituents": constituents,
    }, indent=1))
    print(f"wrote {len(constituents)} constituents to {OUT}")
    print(Counter(c["sector"] for c in constituents))


if __name__ == "__main__":
    main()
