"""Entry mechanics: no chasing, no market orders, ceilings shrink only."""
import pytest

from execution.constants import (
    ADV_POSITION_CAP_PCT, ENTRY_WEIGHT_MAX, ENTRY_WEIGHT_MIN,
    EXTENSION_ATR_LIMIT, MIN_TRADE_NOTIONAL, PATIENT_LIMIT_TTL_WEEKS,
    VOL_CEILING_SLEEVE_RISK,
)
from execution.funnel.entries import (
    entry_limit_price, entry_ttl_days, extension_state, size_entry,
)

SLEEVE = 70_000.0


def test_extension_threshold():
    assert extension_state(EXTENSION_ATR_LIMIT - 0.1) == "normal"
    assert extension_state(EXTENSION_ATR_LIMIT + 0.1) == "extended"


def test_limit_prices_never_chase():
    assert entry_limit_price("normal", 20.0, 19.0, 1.0) == 20.0
    # extended: retracement limit at the higher of sma20 / close − 1 ATR
    assert entry_limit_price("extended", 24.0, 21.5, 2.0) == 22.0   # close−ATR wins
    assert entry_limit_price("extended", 24.0, 23.0, 2.0) == 23.0   # sma20 wins
    assert entry_ttl_days("normal") == 7
    assert entry_ttl_days("extended") == PATIENT_LIMIT_TTL_WEEKS * 7


def test_size_band_tracks_conviction():
    lo = size_entry(0.0, SLEEVE, adv_usd=1e9, atr_pct=0.01,
                    deployable_remaining=SLEEVE, cash_available=SLEEVE)
    hi = size_entry(100.0, SLEEVE, adv_usd=1e9, atr_pct=0.01,
                    deployable_remaining=SLEEVE, cash_available=SLEEVE)
    assert lo == pytest.approx(ENTRY_WEIGHT_MIN * SLEEVE)
    assert hi == pytest.approx(ENTRY_WEIGHT_MAX * SLEEVE)


def test_vol_ceiling_binds_wild_names():
    # 10% daily ATR: cap = 0.0075/0.10 = 7.5% of sleeve < 12% band top
    n = size_entry(100.0, SLEEVE, adv_usd=1e9, atr_pct=0.10,
                   deployable_remaining=SLEEVE, cash_available=SLEEVE)
    assert n == pytest.approx(VOL_CEILING_SLEEVE_RISK / 0.10 * SLEEVE)


def test_adv_ceiling_binds_thin_names():
    # $500k ADV: cap = 1% = $5k, below the 12% band top ($8.4k of $70k sleeve)
    n = size_entry(100.0, SLEEVE, adv_usd=500_000.0, atr_pct=0.01,
                   deployable_remaining=SLEEVE, cash_available=SLEEVE)
    assert n == pytest.approx(ADV_POSITION_CAP_PCT * 500_000.0)  # $5k


def test_deployable_cash_and_dust():
    assert size_entry(100.0, SLEEVE, 1e9, 0.01, deployable_remaining=1_000.0,
                      cash_available=SLEEVE) == pytest.approx(1_000.0)
    assert size_entry(100.0, SLEEVE, 1e9, 0.01, deployable_remaining=SLEEVE,
                      cash_available=200.0) == pytest.approx(200.0)
    assert size_entry(100.0, SLEEVE, 1e9, 0.01, deployable_remaining=MIN_TRADE_NOTIONAL - 1,
                      cash_available=SLEEVE) == 0.0


def test_zero_or_missing_atr_pct_returns_zero():
    assert size_entry(80.0, SLEEVE, 1e9, 0.0, SLEEVE, SLEEVE) == 0.0
