import numpy as np
import pandas as pd
import pytest

from execution.backtest.universe import (
    eligible_asof, load_pit_membership, load_universe, members_asof,
    parse_ishares_csv,
)

ISHARES_SAMPLE = """\
iShares Core S&P 500 ETF
Fund Holdings as of,"Jul 08, 2026"
Inception Date,"May 15, 2000"

Ticker,Name,Sector,Asset Class,Market Value,Weight (%)
AAPL,APPLE INC,Information Technology,Equity,"1,000",7.0
BRK.B,BERKSHIRE HATHAWAY INC CLASS B,Financials,Equity,"900",1.7
XTSLA,BLK CSH FND TREASURY SL AGENCY,Cash and/or Derivatives,Money Market,"5",0.0
MSFT,MICROSOFT CORP,Information Technology,Equity,"950",6.5
"""


def test_parse_ishares_csv_skips_preamble_and_non_equity(tmp_path):
    p = tmp_path / "IVV_holdings.csv"
    p.write_text(ISHARES_SAMPLE)
    assert parse_ishares_csv(p) == ["AAPL", "BRK-B", "MSFT"]


def test_load_universe_unions_and_sorts(tmp_path):
    (tmp_path / "a.csv").write_text(ISHARES_SAMPLE)
    (tmp_path / "b.csv").write_text(ISHARES_SAMPLE.replace("MSFT", "NVDA"))
    assert load_universe(tmp_path) == ["AAPL", "BRK-B", "MSFT", "NVDA"]


def _frame(price: float, volume: float, rows: int = 100) -> pd.DataFrame:
    idx = pd.bdate_range("2020-01-01", periods=rows)
    return pd.DataFrame({
        "Open": price, "High": price, "Low": price,
        "Close": np.full(rows, price), "Volume": np.full(rows, volume),
    }, index=idx)


def test_eligible_asof_applies_floors_and_min_history():
    asof = pd.Timestamp("2020-05-01")
    ohlcv = {
        "GOOD": _frame(price=50.0, volume=100_000),      # ADV $5M — passes
        "PENNY": _frame(price=1.5, volume=10_000_000),   # price floor fails
        "ILLIQ": _frame(price=50.0, volume=1_000),       # ADV $50k fails
        "YOUNG": _frame(price=50.0, volume=100_000, rows=30),  # <63 rows fails
    }
    assert eligible_asof(ohlcv, asof) == ["GOOD"]


def test_eligible_asof_uses_only_data_up_to_asof():
    df = _frame(price=50.0, volume=100_000)
    df.loc[df.index > "2020-04-15", "Volume"] = 0.0     # goes illiquid later
    # 2020-04-01: 66 rows of history (>=63) and full-volume ADV -> eligible
    assert eligible_asof({"AAA": df}, pd.Timestamp("2020-04-01")) == ["AAA"]
    # 2020-05-15: the 20d ADV window is all zero-volume days -> ineligible
    assert eligible_asof({"AAA": df}, pd.Timestamp("2020-05-15")) == []


def test_eligible_asof_respects_allowed_filter():
    asof = pd.Timestamp("2020-05-01")
    ohlcv = {"GOOD": _frame(50.0, 100_000), "ALSO": _frame(50.0, 100_000)}
    assert eligible_asof(ohlcv, asof, allowed={"ALSO"}) == ["ALSO"]
    assert eligible_asof(ohlcv, asof) == ["ALSO", "GOOD"]


PIT_SAMPLE = """\
ticker,date_added,date_removed
AAPL,1982-11-30,
BRK.B,2010-02-16,
TWTR,2018-06-07,2022-10-27
YHOO,1999-12-08,2017-06-19
"""


def test_pit_membership_asof(tmp_path):
    p = tmp_path / "sp500_constituents.csv"
    p.write_text(PIT_SAMPLE)
    pit = load_pit_membership(p)
    assert members_asof(pit, pd.Timestamp("2020-01-01")) == {"AAPL", "BRK-B", "TWTR"}
    assert members_asof(pit, pd.Timestamp("2016-01-01")) == {"AAPL", "BRK-B", "YHOO"}
    assert members_asof(pit, pd.Timestamp("2023-01-01")) == {"AAPL", "BRK-B"}
