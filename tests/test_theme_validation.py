"""Ticker validation gates: hallucinated/illiquid/small names die here."""
import sys
import types

import pandas as pd
import pytest


def _install_yf_stub(monkeypatch, hist=None, mcap=None, raise_on_init=False):
    stub = types.ModuleType("yfinance")

    class FakeTicker:
        def __init__(self, symbol):
            if raise_on_init:
                raise RuntimeError("no such ticker")
            self.fast_info = {"market_cap": mcap}

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
