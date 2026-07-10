from datetime import date

import pytest

from execution.backtest.ledger import Ledger


def test_buy_debits_cash_and_opens_position():
    led = Ledger(10_000.0)
    led.buy("AAA", 10, 50.0, date(2020, 1, 6), "entry_fill", atr=1.5)
    assert led.cash == 9_500.0
    pos = led.positions["AAA"]
    assert (pos.qty, pos.cost_basis, pos.high_water, pos.atr) == (10, 50.0, 50.0, 1.5)
    assert led.journal[-1]["reason"] == "entry_fill"


def test_buy_averages_cost_basis():
    led = Ledger(10_000.0)
    led.buy("AAA", 10, 50.0, date(2020, 1, 6), "entry_fill")
    led.buy("AAA", 10, 60.0, date(2020, 2, 3), "entry_fill")
    assert led.positions["AAA"].qty == 20
    assert led.positions["AAA"].cost_basis == pytest.approx(55.0)


def test_buy_rejects_overspend_and_bad_qty():
    led = Ledger(100.0)
    with pytest.raises(ValueError):
        led.buy("AAA", 3, 50.0, date(2020, 1, 6), "entry_fill")
    with pytest.raises(ValueError):
        led.buy("AAA", 0, 50.0, date(2020, 1, 6), "entry_fill")


def test_sell_partial_then_full_closes_position():
    led = Ledger(10_000.0)
    led.buy("AAA", 10, 50.0, date(2020, 1, 6), "entry_fill")
    led.sell("AAA", 4, 55.0, date(2020, 3, 2), "risk_trim")
    assert led.cash == pytest.approx(9_500.0 + 220.0)
    assert led.positions["AAA"].qty == 6
    led.sell("AAA", 6, 40.0, date(2020, 4, 1), "trailing_stop")
    assert "AAA" not in led.positions
    with pytest.raises(KeyError):
        led.sell("AAA", 1, 40.0, date(2020, 4, 2), "trailing_stop")


def test_sell_rejects_oversell():
    led = Ledger(10_000.0)
    led.buy("AAA", 10, 50.0, date(2020, 1, 6), "entry_fill")
    with pytest.raises(ValueError):
        led.sell("AAA", 11, 55.0, date(2020, 3, 2), "exit")


def test_mark_builds_equity_series():
    led = Ledger(10_000.0)
    led.buy("AAA", 10, 50.0, date(2020, 1, 6), "entry_fill")
    led.mark(date(2020, 1, 6), {"AAA": 52.0})
    led.mark(date(2020, 1, 7), {"AAA": 48.0})
    series = led.equity_series
    assert list(series.values) == [pytest.approx(10_020.0), pytest.approx(9_980.0)]
    assert led.equity({"AAA": 48.0}) == pytest.approx(9_980.0)
