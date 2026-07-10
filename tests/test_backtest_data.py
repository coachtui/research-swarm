import numpy as np
import pandas as pd

import execution.backtest.data as data_mod
from execution.backtest.data import MARKET_SYMBOLS, fetch_ohlcv, load_ohlcv


def _fake_download(symbols, **kwargs):
    idx = pd.bdate_range("2020-01-01", periods=80)
    cols = ["Open", "High", "Low", "Close", "Volume"]
    frames = {}
    for s in (symbols if isinstance(symbols, list) else [symbols]):
        frames[s] = pd.DataFrame(
            np.full((80, 5), 10.0), index=idx, columns=cols)
    return pd.concat(frames, axis=1)          # yfinance group_by="ticker" shape


def test_market_symbols_include_benchmarks_and_sectors():
    assert "SPY" in MARKET_SYMBOLS and "RSP" in MARKET_SYMBOLS and "^VIX" in MARKET_SYMBOLS
    assert "XLK" in MARKET_SYMBOLS
    assert len(MARKET_SYMBOLS) == 14


def test_fetch_writes_parquet_and_skips_cached(tmp_path, monkeypatch):
    calls = []
    def spy_download(symbols, **kwargs):
        calls.append(list(symbols))
        return _fake_download(symbols, **kwargs)
    monkeypatch.setattr(data_mod.yf, "download", spy_download)

    got = fetch_ohlcv(["AAA", "BBB"], cache_dir=tmp_path)
    assert sorted(got) == ["AAA", "BBB"]
    assert (tmp_path / "AAA.parquet").exists()

    calls.clear()
    fetch_ohlcv(["AAA", "CCC"], cache_dir=tmp_path)     # AAA cached → only CCC fetched
    assert calls == [["CCC"]]


def test_load_round_trips_and_applies_min_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(data_mod.yf, "download", _fake_download)
    fetch_ohlcv(["AAA", "^VIX"], cache_dir=tmp_path)
    loaded = load_ohlcv(tmp_path)
    assert set(loaded) == {"AAA", "^VIX"}                # ^VIX name round-trips
    assert list(loaded["AAA"].columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert load_ohlcv(tmp_path, min_rows=100) == {}
