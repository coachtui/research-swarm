from datetime import date

import pytest

from execution.backtest.fills import LimitOrder, check_stop, sell_fill_price, try_fill_buy


def _order(limit: float) -> LimitOrder:
    return LimitOrder(symbol="AAA", qty=10, limit=limit, atr=1.0,
                      placed=date(2020, 1, 6), expires=date(2020, 1, 13), conviction=60.0)


def test_no_fill_when_low_stays_above_limit():
    assert try_fill_buy(_order(50.0), day_open=52.0, day_low=50.5) is None


def test_intraday_touch_fills_at_limit():
    assert try_fill_buy(_order(50.0), day_open=52.0, day_low=49.0) == 50.0


def test_gap_down_open_fills_at_the_better_open():
    assert try_fill_buy(_order(50.0), day_open=47.0, day_low=46.0) == 47.0


def test_sell_fill_price_applies_slippage():
    assert sell_fill_price(100.0) == pytest.approx(99.9)      # default 10 bps
    assert sell_fill_price(100.0, slippage_bps=0.0) == 100.0


def test_check_stop_ratchets_high_water_up_only():
    hw, hit = check_stop(high_water=100.0, today_close=104.0, atr=2.0)
    assert (hw, hit) == (104.0, False)
    hw, hit = check_stop(high_water=104.0, today_close=101.0, atr=2.0)
    assert (hw, hit) == (104.0, False)          # stop = 104 - 2.5*2 = 99


def test_buy_fill_price_adds_adverse_slippage():
    from execution.backtest.fills import buy_fill_price
    assert buy_fill_price(100.0) == 100.1          # default 10 bps against us
    assert buy_fill_price(100.0, 0.0) == 100.0
    assert buy_fill_price(33.3333, 10.0) == 33.3666


def test_check_stop_triggers_below_trail():
    # production constant TRAILING_STOP_ATR_MULT = 2.5 → stop = 104 - 5 = 99
    hw, hit = check_stop(high_water=104.0, today_close=98.9, atr=2.0)
    assert (hw, hit) == (104.0, True)
