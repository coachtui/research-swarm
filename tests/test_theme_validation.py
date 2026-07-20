"""Ticker validation gates: hallucinated/illiquid/small names die here."""
import sys
import types

import pandas as pd
import pytest


class FakeFastInfo:
    def __init__(self, mcap):
        self._mcap = mcap

    def __getitem__(self, key):
        if key in ("market_cap", "marketCap"):
            return self._mcap
        raise KeyError(key)

    def get(self, key, default=None):
        # real FastInfo.get only recognizes camelCase keys
        return self._mcap if key == "marketCap" else default


def _install_yf_stub(monkeypatch, hist=None, mcap=None, raise_on_init=False,
                     on_ticker=None):
    stub = types.ModuleType("yfinance")

    class FakeTicker:
        def __init__(self, symbol):
            if on_ticker is not None:
                on_ticker(symbol)
            if raise_on_init:
                raise RuntimeError("no such ticker")
            self.fast_info = FakeFastInfo(mcap)

        def history(self, period):
            return hist

    stub.Ticker = FakeTicker
    monkeypatch.setitem(sys.modules, "yfinance", stub)


def _good_history(days=70, price=50.0, volume=1_000_000):
    idx = pd.date_range("2026-03-01", periods=days, freq="B")
    return pd.DataFrame({"Close": [price] * days, "Volume": [volume] * days}, index=idx)


def test_valid_ticker_passes(monkeypatch):
    _install_yf_stub(monkeypatch, hist=_good_history(), mcap=2_000_000_000)
    from execution.themes.validation import validate_ticker
    result = validate_ticker("aehr")
    assert result is not None
    assert result["market_cap"] == 2_000_000_000
    assert result["adv"] == pytest.approx(50.0 * 1_000_000)
    assert result["price"] == 50.0


def test_unresolvable_ticker_fails(monkeypatch):
    _install_yf_stub(monkeypatch, raise_on_init=True)
    from execution.themes.validation import validate_ticker
    assert validate_ticker("DRAM") is None


def test_empty_history_fails(monkeypatch):
    _install_yf_stub(monkeypatch, hist=pd.DataFrame(), mcap=2_000_000_000)
    from execution.themes.validation import validate_ticker
    assert validate_ticker("XXXX") is None


def test_missing_volume_column_fails(monkeypatch):
    idx = pd.date_range("2026-03-01", periods=70, freq="B")
    close_only = pd.DataFrame({"Close": [50.0] * 70}, index=idx)
    _install_yf_stub(monkeypatch, hist=close_only, mcap=2_000_000_000)
    from execution.themes.validation import validate_ticker
    assert validate_ticker("NOVOL") is None


def test_low_adv_fails(monkeypatch):
    _install_yf_stub(monkeypatch, hist=_good_history(price=2.0, volume=1000), mcap=2_000_000_000)
    from execution.themes.validation import validate_ticker
    assert validate_ticker("TINY") is None


def test_small_mcap_fails(monkeypatch):
    _install_yf_stub(monkeypatch, hist=_good_history(), mcap=50_000_000)
    from execution.themes.validation import validate_ticker
    assert validate_ticker("MICRO") is None


def test_validate_tickers_dedupes_and_uppercases(monkeypatch):
    _install_yf_stub(monkeypatch, hist=_good_history(), mcap=2_000_000_000)
    from execution.themes.validation import validate_tickers
    out = validate_tickers(["aehr", "AEHR", "viav"])
    assert set(out) == {"AEHR", "VIAV"}


def test_tradable_gate_rejects_symbols_absent_from_broker_universe(monkeypatch):
    """JDSU/PSTH are delisted — absent from Alpaca's asset universe. They must
    reject even when the yfinance stub would happily validate them."""
    _install_yf_stub(monkeypatch, hist=_good_history(), mcap=2_000_000_000)
    from execution.themes.validation import validate_tickers
    out = validate_tickers(["AEHR", "JDSU", "PSTH"], tradable={"AEHR", "VIAV"})
    assert out["AEHR"] is not None
    assert out["JDSU"] is None
    assert out["PSTH"] is None


def test_tradable_gate_skips_yfinance_entirely_for_untradable(monkeypatch):
    """The gate short-circuits before the network call — a delisted name costs
    us nothing."""
    seen = []
    _install_yf_stub(monkeypatch, hist=_good_history(), mcap=2_000_000_000,
                     on_ticker=seen.append)
    from execution.themes.validation import validate_tickers
    validate_tickers(["AEHR", "JDSU"], tradable={"AEHR"})
    assert seen == ["AEHR"]


def test_tradable_none_means_no_gate(monkeypatch):
    """A broker outage degrades to 'don't gate' — same posture as the funnel."""
    _install_yf_stub(monkeypatch, hist=_good_history(), mcap=2_000_000_000)
    from execution.themes.validation import validate_tickers
    out = validate_tickers(["AEHR", "JDSU"], tradable=None)
    assert out["AEHR"] is not None
    assert out["JDSU"] is not None
