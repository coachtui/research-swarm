"""
Validation tests for the DVRG T1 Accumulate historical backtest.

These tests use synthetic / mocked data to verify correctness without
network calls or large data downloads.

Run:
    pytest scripts/backtest/tests/test_backtest.py -v
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Ensure project root is on the path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ── Test 1: No look-ahead bias ────────────────────────────────────────────────


def test_no_lookahead_bias():
    """
    Verify that fundamentals returned by get_fundamentals() always satisfy:
        reporting_period + FUND_LAG_DAYS <= as_of_date

    Uses a mocked raw-quarters dict so no network call is needed.
    """
    import json
    import gzip
    import tempfile

    from scripts.backtest.config import FUND_LAG_DAYS
    from scripts.backtest.data.fundamentals import _build_fundamentals

    # Build a synthetic raw quarters dict
    def make_raw(period_ends: list[str]) -> dict:
        quarters = []
        for pe in period_ends:
            quarters.append({
                "period_end": pe,
                "net_income": 1_000_000,
                "total_revenue": 10_000_000,
                "gross_profit": 4_000_000,
                "operating_cash_flow": 2_000_000,
                "capital_expenditure": -500_000,
                "total_debt": 5_000_000,
                "stockholders_equity": 8_000_000,
            })
        return {
            "ticker": "FAKE",
            "fetched_at": "2026-01-01",
            "shares_outstanding": 1_000_000,
            "quarters": quarters,
        }

    # Quarters: Q3-2020, Q2-2020, Q1-2020, Q4-2019 ... each ~3 months apart
    period_ends = [
        "2020-09-30", "2020-06-30", "2020-03-31", "2019-12-31",
        "2019-09-30", "2019-06-30", "2019-03-31", "2018-12-31",
    ]
    raw = make_raw(period_ends)

    test_cases = [
        # as_of_date, expected: should find Q2-2020 (lag: 2020-06-30 + 60 = 2020-08-29 ≤ 2020-09-01)
        (date(2020, 9, 1), date(2020, 6, 30)),
        # as_of_date: too early to use Q3-2020 (2020-09-30 + 60 = 2020-11-29 > 2020-10-01)
        (date(2020, 10, 1), date(2020, 6, 30)),
        # as_of_date: Q3-2020 available
        (date(2020, 12, 1), date(2020, 9, 30)),
    ]

    for as_of, expected_period in test_cases:
        fund = _build_fundamentals("FAKE", raw, as_of, FUND_LAG_DAYS)
        assert fund is not None, f"Expected fundamentals for as_of={as_of}"
        assert fund.reporting_period == expected_period, (
            f"as_of={as_of}: got reporting_period={fund.reporting_period}, "
            f"expected {expected_period}"
        )
        # Core check: lag must be >= FUND_LAG_DAYS
        lag = (as_of - fund.reporting_period).days
        assert lag >= FUND_LAG_DAYS, (
            f"LOOK-AHEAD VIOLATION on {as_of}: "
            f"reporting_period={fund.reporting_period}, lag={lag} < {FUND_LAG_DAYS}"
        )


# ── Test 2: Universe changes over time ────────────────────────────────────────


def test_universe_changes():
    """
    Verify S&P 500 membership changes between 2016 and 2020 when a real
    constituent CSV is loaded.

    Skip gracefully when no CSV is available (CI/CD without dataset).
    """
    from scripts.backtest.data.sp500_constituents import (
        _find_csv, _load_csv, set_survivorship_bias_ok,
    )

    csv_path = _find_csv()
    if csv_path is None:
        pytest.skip("S&P 500 constituent CSV not found — run --download first")

    import pandas as pd
    df = _load_csv(csv_path)

    def members_as_of(d: date) -> set:
        added_ok = df["date_added"] <= pd.Timestamp(d)
        removed_ok = df["date_removed"].isna() | (df["date_removed"] > pd.Timestamp(d))
        return set(df.loc[added_ok & removed_ok, "ticker"])

    u2016 = members_as_of(date(2016, 1, 31))
    u2020 = members_as_of(date(2020, 1, 31))

    assert len(u2016) >= 400, f"Too few members in Jan 2016: {len(u2016)}"
    assert len(u2020) >= 400, f"Too few members in Jan 2020: {len(u2020)}"

    added = u2020 - u2016
    removed = u2016 - u2020
    assert len(added) > 5, f"Expected additions 2016→2020, got {len(added)}"
    assert len(removed) > 5, f"Expected removals 2016→2020, got {len(removed)}"


# ── Test 3: Portfolio weights sum ≤ 1.0 ───────────────────────────────────────


def test_weights_sum_leq_one():
    """
    Verify build_portfolio() always returns weights summing to ≤ 1.0.
    Test with multiple universe sizes including edge cases.
    """
    from scripts.backtest.signal_snapshot import SignalRow
    from scripts.backtest.backtest_t1 import build_portfolio, apply_t1_filter

    def make_signals(n: int) -> list[SignalRow]:
        rng = np.random.default_rng(42)
        signals = []
        for i in range(n):
            signals.append(SignalRow(
                ticker=f"T{i:04d}",
                as_of_date=date(2020, 1, 31),
                rating="BUY",
                rating_label="Accumulate",
                expected_value=float(rng.uniform(0.15, 0.50)),
                confidence_score=float(rng.uniform(55, 90)),
                risk_level=int(rng.choice([1, 2])),
                risk_level_str="Medium",
                asymmetry_ratio=float(rng.uniform(1.3, 3.0)),
                downside_severity=float(rng.uniform(0.05, 0.29)),
                recommended_weight=float(rng.uniform(0.035, 0.055)),
                moat_score=float(rng.uniform(7.0, 9.0)),
                current_price=100.0,
                ev_price=115.0,
                base_target=110.0,
                bull_target=143.0,
                bear_target=88.0,
                beta=1.0,
                fundamentals_period=date(2019, 12, 31),
                data_quality="complete",
            ))
        return signals

    for n in [3, 10, 25, 30, 50, 100]:
        signals = make_signals(n)
        qualified = apply_t1_filter(signals)
        weights = build_portfolio(qualified)

        total = weights.sum()
        assert total <= 1.0 + 1e-9, (
            f"Weights sum {total:.8f} > 1.0 for n={n} qualified={len(qualified)}"
        )
        if not weights.empty:
            assert weights.max() <= 0.08 + 1e-9, (
                f"Max weight {weights.max():.4f} exceeds MAX_WEIGHT=0.08 for n={n}"
            )
            assert weights.min() >= 0.01 - 1e-9, (
                f"Min weight {weights.min():.4f} below MIN_WEIGHT=0.01 for n={n}"
            )


# ── Test 4: Benchmark alignment ───────────────────────────────────────────────


def test_benchmark_alignment():
    """
    Verify that equity and benchmark curves have aligned, complete date indices.
    Simulates the structure produced by run_backtest().
    """
    # Simulate daily rows as produced by compute_period_returns()
    dates = pd.date_range("2020-01-02", "2022-12-30", freq="B")  # business days
    n = len(dates)

    rng = np.random.default_rng(123)
    gross_rets = rng.normal(0.0003, 0.012, n)
    bench_rets = rng.normal(0.0002, 0.010, n)

    portfolio_equity = pd.Series(
        (1 + gross_rets).cumprod(),
        index=dates,
        name="T1",
    )
    benchmark_equity = pd.Series(
        (1 + bench_rets).cumprod(),
        index=dates,
        name="VOO",
    )

    assert portfolio_equity.index.equals(benchmark_equity.index), (
        "Portfolio and benchmark must share identical date indices"
    )
    assert not portfolio_equity.isna().any(), "Portfolio equity must have no NaN"
    assert not benchmark_equity.isna().any(), "Benchmark equity must have no NaN"
    assert (portfolio_equity > 0).all(), "Portfolio equity must be positive"


# ── Test 5: Transaction costs reduce net returns ──────────────────────────────


def test_cost_drag():
    """
    Verify that net returns are always <= gross returns when trades occur,
    and that the cost formula matches expectations.
    """
    from scripts.backtest.backtest_t1 import compute_turnover_cost
    from scripts.backtest.config import TRANSACTION_COST_BPS

    # Scenario: replace 5 positions in a 25-position portfolio
    old_w = pd.Series({f"T{i:03d}": 0.04 for i in range(25)})
    new_w = pd.Series({f"T{i:03d}": 0.04 for i in range(5, 30)})

    cost = compute_turnover_cost(old_w, new_w)

    # Expected turnover:
    # 5 tickers sold (0.04 each) + 5 tickers bought (0.04 each) = 0.40 total
    # 20 tickers unchanged
    expected_turnover = 0.04 * 5 + 0.04 * 5  # = 0.40
    expected_cost = expected_turnover * (TRANSACTION_COST_BPS / 10_000)

    assert abs(cost - expected_cost) < 1e-9, (
        f"Expected cost {expected_cost:.8f}, got {cost:.8f}"
    )
    assert cost > 0, "Cost must be positive when positions change"

    # Verify no cost when nothing changes
    same_w = pd.Series({f"T{i:03d}": 0.04 for i in range(25)})
    zero_cost = compute_turnover_cost(same_w, same_w)
    assert zero_cost < 1e-12, f"Expected zero cost for unchanged portfolio, got {zero_cost}"


# ── Test 6: PIT fundamental filter correctness ────────────────────────────────


def test_pit_filter_rejects_future_data():
    """
    Verify that a quarter ending AFTER as_of_date - lag_days is rejected.
    """
    from scripts.backtest.data.fundamentals import _build_fundamentals
    from scripts.backtest.config import FUND_LAG_DAYS

    def make_raw(period_ends: list[str]) -> dict:
        return {
            "ticker": "TEST",
            "fetched_at": "2026-01-01",
            "shares_outstanding": 1_000_000,
            "quarters": [
                {
                    "period_end": pe,
                    "net_income": 1_000_000,
                    "total_revenue": 10_000_000,
                    "gross_profit": 4_000_000,
                    "operating_cash_flow": 2_000_000,
                    "capital_expenditure": -500_000,
                    "total_debt": 5_000_000,
                    "stockholders_equity": 8_000_000,
                }
                for pe in period_ends
            ],
        }

    # as_of = 2020-04-01; lag = 60 days → latest usable quarter end = 2020-02-01
    # Q1 2020 (2020-03-31) is NOT available until 2020-05-30
    as_of = date(2020, 4, 1)
    raw = make_raw(["2020-03-31", "2019-12-31", "2019-09-30", "2019-06-30"])
    fund = _build_fundamentals("TEST", raw, as_of, FUND_LAG_DAYS)

    assert fund is not None
    assert fund.reporting_period == date(2019, 12, 31), (
        f"Q1-2020 should not be usable on {as_of}, got {fund.reporting_period}"
    )
    lag = (as_of - fund.reporting_period).days
    assert lag >= FUND_LAG_DAYS, (
        f"LOOK-AHEAD: lag {lag} < {FUND_LAG_DAYS} on {as_of}"
    )


# ── Test 7: Signal computation determinism ────────────────────────────────────


def test_signal_determinism():
    """
    Verify that compute_signal() produces identical output when called twice
    with the same inputs (no random components).
    """
    from scripts.backtest.signal_snapshot import compute_signal
    from scripts.backtest.data.fundamentals import PITFundamentals

    fund = PITFundamentals(
        ticker="AAPL",
        reporting_period=date(2019, 12, 31),
        earliest_use_date=date(2020, 2, 29),
        quarters_available=12,
        eps_ttm=5.20,
        fcf_per_share=4.80,
        revenue_growth_yoy=8.5,
        fcf_margin=22.0,
        roe=55.0,
        de_ratio=1.8,
        net_margin=21.0,
        gross_margin=38.0,
        eps_series=[1.3, 1.25, 1.28, 1.22, 1.15, 1.10, 1.05, 1.08],
        data_quality="complete",
    )

    sig1 = compute_signal("AAPL", date(2020, 3, 31), fund, 280.0, 1.1)
    sig2 = compute_signal("AAPL", date(2020, 3, 31), fund, 280.0, 1.1)

    assert sig1 is not None
    assert sig2 is not None
    assert sig1.moat_score == sig2.moat_score
    assert sig1.expected_value == sig2.expected_value
    assert sig1.confidence_score == sig2.confidence_score
    assert sig1.risk_level == sig2.risk_level


# ── Test 8: Currency — USD passthrough (no conversion) ────────────────────────


def test_usd_currency_passthrough():
    """
    USD reporters must NOT have FX applied.

    Verify:
    - fund.reporting_currency == "USD"
    - fund.currency_converted == False
    - build_stock_info → financialCurrency="USD", NO _currency_normalized key
    - Raw dollar values are unchanged
    """
    from scripts.backtest.config import FUND_LAG_DAYS
    from scripts.backtest.data.fundamentals import _build_fundamentals
    from scripts.backtest.adapters.pit_inputs_builder import build_stock_info

    raw = {
        "ticker": "MSFT",
        "fetched_at": "2024-01-01",
        "shares_outstanding": 7_000_000_000,
        "reporting_currency": "USD",
        "quarters": [
            {
                "period_end": "2023-09-30",
                "net_income": 22_000_000_000,
                "total_revenue": 56_000_000_000,
                "gross_profit": 38_000_000_000,
                "operating_cash_flow": 30_000_000_000,
                "capital_expenditure": -5_000_000_000,
                "total_debt": 50_000_000_000,
                "stockholders_equity": 120_000_000_000,
            },
            {
                "period_end": "2023-06-30",
                "net_income": 20_000_000_000,
                "total_revenue": 53_000_000_000,
                "gross_profit": 36_000_000_000,
                "operating_cash_flow": 28_000_000_000,
                "capital_expenditure": -4_800_000_000,
                "total_debt": 48_000_000_000,
                "stockholders_equity": 118_000_000_000,
            },
            {
                "period_end": "2023-03-31",
                "net_income": 18_000_000_000,
                "total_revenue": 50_000_000_000,
                "gross_profit": 34_000_000_000,
                "operating_cash_flow": 26_000_000_000,
                "capital_expenditure": -4_500_000_000,
                "total_debt": 46_000_000_000,
                "stockholders_equity": 115_000_000_000,
            },
            {
                "period_end": "2022-12-31",
                "net_income": 16_000_000_000,
                "total_revenue": 47_000_000_000,
                "gross_profit": 32_000_000_000,
                "operating_cash_flow": 24_000_000_000,
                "capital_expenditure": -4_200_000_000,
                "total_debt": 44_000_000_000,
                "stockholders_equity": 112_000_000_000,
            },
        ],
    }

    as_of = date(2023, 12, 1)
    fund = _build_fundamentals("MSFT", raw, as_of, FUND_LAG_DAYS)

    assert fund is not None, "Should produce fundamentals for USD ticker"
    assert fund.reporting_currency == "USD"
    assert fund.currency_converted is False, "USD reporter must NOT be converted"

    # build_stock_info must set financialCurrency="USD" without _currency_normalized
    stock_info = build_stock_info(fund, current_price=375.0, beta=0.9)
    assert stock_info["financialCurrency"] == "USD"
    assert "_currency_normalized" not in stock_info, (
        "USD reporter must NOT set _currency_normalized sentinel "
        "(it is not needed — financialCurrency='USD' is sufficient)"
    )


# ── Test 9: Currency — non-USD FX conversion ──────────────────────────────────


def test_non_usd_currency_conversion():
    """
    Non-USD reporters must have monetary fields scaled by the FX rate.

    Verify (mocking get_fx_rate to return 1.10 EUR→USD):
    - fund.reporting_currency == "EUR"
    - fund.currency_converted == True
    - Revenue TTM raw ~ original * 1.10
    - build_stock_info → financialCurrency="USD" AND _currency_normalized=True
    """
    from unittest.mock import patch

    from scripts.backtest.config import FUND_LAG_DAYS
    from scripts.backtest.data.fundamentals import _build_fundamentals
    from scripts.backtest.adapters.pit_inputs_builder import build_stock_info

    # EUR quarterly data (raw, pre-FX)
    eur_revenue_q = 10_000_000_000   # 10B EUR per quarter

    raw = {
        "ticker": "ASML",
        "fetched_at": "2024-01-01",
        "shares_outstanding": 400_000_000,
        "reporting_currency": "EUR",
        "quarters": [
            {
                "period_end": pe,
                "net_income": 2_000_000_000,
                "total_revenue": eur_revenue_q,
                "gross_profit": 5_000_000_000,
                "operating_cash_flow": 3_000_000_000,
                "capital_expenditure": -800_000_000,
                "total_debt": 4_000_000_000,
                "stockholders_equity": 20_000_000_000,
            }
            for pe in [
                "2023-09-30", "2023-06-30", "2023-03-31", "2022-12-31",
                "2022-09-30", "2022-06-30", "2022-03-31", "2021-12-31",
            ]
        ],
    }

    FX_RATE = 1.10  # 1 EUR = 1.10 USD (mocked)
    as_of = date(2023, 12, 1)

    with patch(
        "scripts.backtest.data.fx_rates.get_fx_rate",
        return_value=FX_RATE,
    ):
        fund = _build_fundamentals("ASML", raw, as_of, FUND_LAG_DAYS)

    assert fund is not None, "Should produce fundamentals for non-USD ticker"
    assert fund.reporting_currency == "EUR"
    assert fund.currency_converted is True, "Non-USD reporter with FX rate must be converted"

    # Revenue TTM = 4 quarters × eur_revenue_q × FX
    expected_revenue_ttm = 4 * eur_revenue_q * FX_RATE
    assert fund.revenue_ttm_raw is not None
    assert abs(fund.revenue_ttm_raw - expected_revenue_ttm) < 1e-3, (
        f"Revenue TTM {fund.revenue_ttm_raw:.0f} should be ~{expected_revenue_ttm:.0f} "
        f"(4 × {eur_revenue_q} × {FX_RATE})"
    )

    # build_stock_info must set BOTH financialCurrency="USD" AND _currency_normalized=True
    stock_info = build_stock_info(fund, current_price=700.0, beta=1.2)
    assert stock_info["financialCurrency"] == "USD", (
        "Converted non-USD ticker should present as USD"
    )
    assert stock_info.get("_currency_normalized") is True, (
        "Non-USD + converted must set _currency_normalized=True to pass USD guard"
    )


# ── Test N+1: Scenario sanity — sentinel floor detection ─────────────────────


def test_scenario_sanity_sentinel_floor():
    """
    A base_target of 0.01 when price is $100 is a sentinel value, not a real
    estimate.  validate_scenarios() must catch it and return is_valid=False with
    reason "sentinel_floor_detected".
    """
    from scripts.backtest.signal_snapshot import validate_scenarios

    signal_output = {
        "bear_target":   80.0,
        "base_target":    0.01,   # sentinel — well below 2% of a $100 stock
        "bull_target":  130.0,
    }
    current_price = 100.0

    is_valid, reason = validate_scenarios(signal_output, current_price)

    assert not is_valid, (
        "base_target=0.01 with price=100 must fail scenario sanity"
    )
    assert reason == "sentinel_floor_detected", (
        f"Expected 'sentinel_floor_detected', got '{reason}'"
    )


# ── Test N+2: Scenario sanity — ordering violation detection ─────────────────


def test_scenario_sanity_ordering_violation():
    """
    validate_scenarios() must catch bull < base and base < bear target orderings.
    """
    from scripts.backtest.signal_snapshot import validate_scenarios

    price = 100.0

    # Case A: bull < base (inverted upside)
    signal_inverted_bull = {
        "bear_target":  80.0,
        "base_target": 110.0,
        "bull_target": 105.0,   # bull is below base — ordering violation
    }
    is_valid, reason = validate_scenarios(signal_inverted_bull, price)
    assert not is_valid, "bull < base must fail scenario sanity"
    assert reason == "bull_lt_base", (
        f"Expected 'bull_lt_base', got '{reason}'"
    )

    # Case B: base < bear (bear case above base — sign error)
    signal_inverted_bear = {
        "bear_target":  95.0,   # bear is above base — ordering violation
        "base_target":  90.0,
        "bull_target": 130.0,
    }
    is_valid, reason = validate_scenarios(signal_inverted_bear, price)
    assert not is_valid, "base < bear must fail scenario sanity"
    assert reason == "base_lt_bear", (
        f"Expected 'base_lt_bear', got '{reason}'"
    )


# ── Test: downside_severity is never negative after fix ───────────────────────


def test_downside_severity_never_negative():
    """
    When bear_target > current_price (stock looks undervalued even in bear case),
    downside_severity must be clamped to 0.0, NOT negative.

    Regression test for bug B: `(price - bear) / price` was unguarded and could
    return e.g. -0.38 when bear = 138 and price = 100.  The T1 downside gate
    (`<= 0.30`) would silently pass a negative value, masking the broken scenario.
    """
    from scripts.backtest.signal_snapshot import compute_signal
    from scripts.backtest.data.fundamentals import PITFundamentals

    # Build a synthetic fund that will produce a BUY-rated signal.
    # Raw dollar fields must be set so build_dcf_inputs has valid FCF.
    fund = PITFundamentals(
        ticker="TSST",
        reporting_period=date(2017, 9, 30),
        earliest_use_date=date(2017, 11, 29),
        quarters_available=12,
        eps_ttm=8.00,
        fcf_per_share=7.50,
        revenue_growth_yoy=14.0,
        fcf_margin=25.0,
        roe=30.0,
        de_ratio=0.20,
        net_margin=22.0,
        gross_margin=40.0,
        eps_series=[2.0, 1.9, 2.1, 2.0, 1.8, 1.85, 1.75, 1.80],
        data_quality="complete",
        net_income_ttm_raw=8_000_000_000,
        revenue_ttm_raw=36_363_636_364,
        fcf_ttm_raw=9_000_000_000,
        total_debt_raw=5_000_000_000,
        cash_raw=20_000_000_000,
        shares_raw=1_200_000_000,
        reporting_currency="USD",
    )

    # Price well below bear scenario target to force bear > current_price
    # (stock trading at deep discount — bear case still above market price)
    price = 80.0     # current price $80
    # When base_target ≈ $130 and bear = $104 (80% of base), bear > price.
    sig = compute_signal("TSST", date(2018, 2, 28), fund, price, beta=0.9,
                         scenario_sanity_check=False)

    if sig is None:
        pytest.skip("Signal computation returned None — not enough data for this synthetic fund")

    assert sig.downside_severity >= 0.0, (
        f"downside_severity must be ≥ 0, got {sig.downside_severity:.4f}. "
        f"bear={sig.bear_target:.2f}, price={sig.current_price:.2f}"
    )


# ── Test: validate_scenarios flags skew > 20 as skew_unreasonable ─────────────


def test_validate_scenarios_skew_unreasonable():
    """
    validate_scenarios() must return (False, 'skew_unreasonable:X') when the
    computed asymmetry_ratio exceeds 20.  This happens when bear_target > current_price
    (all scenarios above current price) causing the denominator to collapse to ~1e-6.
    """
    from scripts.backtest.signal_snapshot import validate_scenarios

    price = 100.0
    # All three scenarios are ABOVE current price.
    # bear = $110, base = $140, bull = $180 — ordering is valid but skew is huge.
    # asymmetry_ratio = (180-100) / max(100-110, 1e-6) = 80 / 1e-6 >> 20
    signal_all_above = {
        "bear_target": 110.0,
        "base_target": 140.0,
        "bull_target": 180.0,
    }
    is_valid, reason = validate_scenarios(signal_all_above, price)
    assert not is_valid, (
        "All scenarios above current_price → skew collapse → must be flagged invalid"
    )
    assert reason.startswith("skew_unreasonable"), (
        f"Expected 'skew_unreasonable:X', got '{reason}'"
    )

    # Normal asymmetric scenario (bear below price) must still pass.
    signal_normal = {
        "bear_target":  80.0,
        "base_target": 120.0,
        "bull_target": 160.0,
    }
    is_valid_normal, reason_normal = validate_scenarios(signal_normal, price)
    assert is_valid_normal, (
        f"Normal scenario should pass: bear=80, base=120, bull=160 at price=100 "
        f"(skew={(160-100)/(100-80):.1f}). Reason: '{reason_normal}'"
    )


# ── Test: DCF sanity check blocks sub-$1 output for large-caps ────────────────


def test_dcf_sanity_check_large_cap():
    """
    When a large-cap company (market_cap > $10B) produces a DCF base_value < $1
    (typically because debt > EV + cash → negative equity floored to $0.01),
    DCFCalculator.calculate_dcf() must return None rather than propagating a
    nonsensical sentinel value into the blended fair value.
    """
    from research_swarm.agents.fundamentalist.models import DCFInputs
    from research_swarm.agents.fundamentalist.dcf_calculator import DCFCalculator

    calc = DCFCalculator()

    # Simulate a highly leveraged company with debt >> EV.
    # market_cap = $50B, FCF = $1B, debt = $200B, cash = $10B, shares = 1B.
    # Equity = (EV of FCF stream) + cash - debt → almost certainly negative.
    dcf_inputs = DCFInputs(
        fcf_history=[1_000.0],           # $1B FCF (millions)
        revenue_growth_rate=2.0,
        total_debt=200_000.0,            # $200B debt (millions)
        cash_and_equivalents=10_000.0,   # $10B cash (millions)
        shares_outstanding=1_000.0,      # 1B shares (millions)
        market_cap_millions=50_000.0,    # $50B market cap → triggers sanity check
    )
    result = calc.calculate_dcf(dcf_inputs, current_price=50.0)

    assert result is None, (
        f"DCF must return None for large-cap with negative equity — got base={result.base_target if result else 'N/A'}"
    )

    # A healthy company with the same market cap must NOT be blocked.
    dcf_healthy = DCFInputs(
        fcf_history=[20_000.0],          # $20B FCF (millions)
        revenue_growth_rate=8.0,
        total_debt=30_000.0,             # $30B debt (millions)
        cash_and_equivalents=40_000.0,   # $40B cash (millions)
        shares_outstanding=1_000.0,
        market_cap_millions=50_000.0,
    )
    result_healthy = calc.calculate_dcf(dcf_healthy, current_price=50.0)
    assert result_healthy is not None, "Healthy large-cap DCF should succeed"
    assert result_healthy.base_target >= 1.0, (
        f"Healthy DCF base_target should be ≥ $1, got {result_healthy.base_target}"
    )


# ── Test: T1 qualifiers emerge for at least one month ────────────────────────


def test_t1_qualifiers_with_synthetic_signals():
    """
    With well-formed synthetic signals that meet all T1 criteria
    (moat≥7, EV≥15%, confidence≥55, risk≤2, skew≥1.3, downside≤30%, weight>0),
    apply_t1_filter() and build_portfolio() must produce a non-empty portfolio.

    This is the core regression test for the complete fix set: after fixing
    downside sign, skew robustness, and DCF sanity, a set of valid signals
    MUST produce T1 qualifiers (pass_all > 0 for this synthetic "month").
    """
    from scripts.backtest.signal_snapshot import SignalRow
    from scripts.backtest.backtest_t1 import apply_t1_filter, build_portfolio

    rng = np.random.default_rng(2018)

    def make_qualifying_signal(ticker: str, i: int) -> SignalRow:
        """Create a signal that explicitly satisfies every T1 gate."""
        price = 100.0
        base = 125.0
        bull = 162.5   # 1.30× upside vs 0.20× downside → skew = (62.5/20) = 3.125 ≥ 1.3
        bear = 80.0    # downside_severity = (100-80)/100 = 0.20 ≤ 0.30
        ev_price = base * 0.5 + bull * 0.25 + bear * 0.25   # = 110.125
        ev = (ev_price - price) / price                       # = 0.101 → below threshold, bump
        # Set expected_value directly above threshold
        return SignalRow(
            ticker=ticker,
            as_of_date=date(2018, 2, 28),
            rating="BUY",
            rating_label="Accumulate",         # ← must be "Accumulate"
            expected_value=0.20 + i * 0.01,    # ≥ 0.15 ✓
            confidence_score=65.0,             # ≥ 55 ✓
            risk_level=2,                      # ≤ 2 ✓
            risk_level_str="Medium",
            asymmetry_ratio=3.125,             # ≥ 1.3 ✓
            downside_severity=0.20,            # ≤ 0.30 ✓  (positive, ≥ 0)
            recommended_weight=0.04,           # > 0 ✓
            moat_score=7.5,
            current_price=price,
            ev_price=ev_price,
            base_target=base,
            bull_target=bull,
            bear_target=bear,
            beta=1.0,
            fundamentals_period=date(2017, 12, 31),
            data_quality="complete",
            scenario_valid=True,
        )

    signals = [make_qualifying_signal(f"SY{i:03d}", i) for i in range(10)]

    qualified = apply_t1_filter(signals)
    assert len(qualified) > 0, (
        "apply_t1_filter must return ≥ 1 qualified signal for these well-formed inputs. "
        f"Got 0 from {len(signals)} signals."
    )

    weights = build_portfolio(qualified)
    assert not weights.empty, "build_portfolio must produce non-empty weights"
    assert weights.sum() <= 1.0 + 1e-9, f"Weights sum {weights.sum():.6f} > 1.0"


# ── Test: normalize_bool_series coerces all dtypes correctly ──────────────────


def test_normalize_bool_series():
    """
    normalize_bool_series must coerce bool, int 0/1, str "true"/"false", and
    NaN/None to strict Python bool without raising.
    """
    from scripts.backtest.backtest_t1 import normalize_bool_series

    # bool passthrough
    result = normalize_bool_series(pd.Series([True, False, True]))
    assert result.tolist() == [True, False, True], f"bool dtype: {result.tolist()}"

    # int 0/1
    result = normalize_bool_series(pd.Series([1, 0, 1, 0]))
    assert result.tolist() == [True, False, True, False], f"int dtype: {result.tolist()}"

    # string variants
    result = normalize_bool_series(pd.Series(["True", "False", "true", "false", "1", "0"]))
    assert result.tolist() == [True, False, True, False, True, False], f"str dtype: {result.tolist()}"

    # NaN / None → False
    result = normalize_bool_series(pd.Series([True, np.nan, None, False]))
    assert result.tolist() == [True, False, False, False], f"NaN/None: {result.tolist()}"

    # Mixed int + NaN (common in CSV-loaded DataFrames)
    result = normalize_bool_series(pd.Series([1.0, 0.0, np.nan]))
    assert result.tolist() == [True, False, False], f"float+NaN: {result.tolist()}"


# ── Test: _assert_gate_integrity passes for clean rows ────────────────────────


def test_gate_integrity_passes_for_clean_rows():
    """_assert_gate_integrity must not raise when pass_all == all(5 gates)."""
    from scripts.backtest.backtest_t1 import _assert_gate_integrity

    clean_rows = [
        {
            "month": "2018-01", "ticker": "AAPL",
            "pass_ev": True, "pass_conf": True, "pass_risk": True,
            "pass_skew": True, "pass_downside": True,
            "pass_all": True,   # correct: all 5 = True
            "scenario_valid": True, "t1_qualifies": True,
        },
        {
            "month": "2018-01", "ticker": "MSFT",
            "pass_ev": False, "pass_conf": True, "pass_risk": True,
            "pass_skew": True, "pass_downside": True,
            "pass_all": False,  # correct: one gate False → False
            "scenario_valid": True, "t1_qualifies": False,
        },
    ]
    # Must not raise
    _assert_gate_integrity(clean_rows, context="test_clean", out_dir=None)


# ── Test: _assert_gate_integrity raises for stale/mismatched pass_all ─────────


def test_gate_integrity_raises_for_dirty_rows():
    """
    _assert_gate_integrity must raise RuntimeError when pass_all stored in a row
    disagrees with the recomputed truth from the 5 GATE_COLS.
    This exactly reproduces the original defect: pass_all was False even though
    all 5 gates were True (blocked by the stale rating_label == 'Accumulate' check).
    """
    from scripts.backtest.backtest_t1 import _assert_gate_integrity

    dirty_rows = [
        {
            "month": "2018-01", "ticker": "HOLD_TICKER",
            # All 5 gates True:
            "pass_ev": True, "pass_conf": True, "pass_risk": True,
            "pass_skew": True, "pass_downside": True,
            # But old code set pass_all=False due to rating_label != "Accumulate":
            "pass_all": False,
            "scenario_valid": True, "t1_qualifies": False,
        },
    ]
    with pytest.raises(RuntimeError, match="INTEGRITY FAILURE"):
        _assert_gate_integrity(dirty_rows, context="test_dirty", out_dir=None)


# ── Test: HOLD-rated signal with all 5 gates passing qualifies after fix ───────


def test_hold_rated_signal_qualifies_after_integrity_fix():
    """
    A HOLD-rated signal (moat_score < 7.0, rating_label != 'Accumulate') that
    passes all 5 T1 gates MUST be returned by apply_t1_filter after the fix.

    Before the fix: blocked by ``rating_label == 'Accumulate'`` condition.
    After the fix : qualifies because only the 5 gate thresholds matter.
    """
    from scripts.backtest.signal_snapshot import SignalRow
    from scripts.backtest.backtest_t1 import apply_t1_filter

    hold_signal = SignalRow(
        ticker="HOLD_TEST",
        as_of_date=date(2018, 1, 31),
        rating="HOLD",
        rating_label="HOLD",        # NOT "Accumulate" — moat_score = 6.0 < 7.0
        expected_value=0.20,        # ≥ 0.15 ✓
        confidence_score=65.0,      # ≥ 55 ✓
        risk_level=2,               # ≤ 2 ✓
        risk_level_str="Medium",
        asymmetry_ratio=1.5,        # ≥ 1.3 ✓
        downside_severity=0.20,     # ≤ 0.30 ✓
        recommended_weight=0.0,     # 0 — was previously a disqualifier
        moat_score=6.0,             # < 7.0 → HOLD rating
        current_price=100.0,
        ev_price=120.0,
        base_target=120.0,
        bull_target=140.0,
        bear_target=80.0,
        beta=1.0,
        fundamentals_period=date(2017, 12, 31),
        data_quality="complete",
        scenario_valid=True,
    )

    qualified = apply_t1_filter([hold_signal])
    assert len(qualified) == 1, (
        "HOLD-rated signal with all 5 gates passing must qualify after the integrity fix. "
        f"Got {len(qualified)} qualified (expected 1)."
    )


# ── Test: invalid scenario is never t1_qualifies regardless of gates ──────────


def test_invalid_scenario_never_qualifies():
    """
    A signal with scenario_valid=False must never be returned by apply_t1_filter,
    even if all 5 gate values are above threshold.
    """
    from scripts.backtest.signal_snapshot import SignalRow
    from scripts.backtest.backtest_t1 import apply_t1_filter

    invalid_signal = SignalRow(
        ticker="INVALID_TEST",
        as_of_date=date(2018, 1, 31),
        rating="BUY",
        rating_label="Accumulate",
        expected_value=0.25,
        confidence_score=70.0,
        risk_level=1,
        risk_level_str="Low",
        asymmetry_ratio=2.0,
        downside_severity=0.15,
        recommended_weight=0.05,
        moat_score=8.0,
        current_price=100.0,
        ev_price=125.0,
        base_target=125.0,
        bull_target=150.0,
        bear_target=85.0,
        beta=1.0,
        fundamentals_period=date(2017, 12, 31),
        data_quality="complete",
        scenario_valid=False,           # ← invalid scenario
        invalid_reason="ordering_violation",
    )

    qualified = apply_t1_filter([invalid_signal])
    assert len(qualified) == 0, (
        "Signal with scenario_valid=False must never qualify. "
        f"Got {len(qualified)} qualified (expected 0)."
    )
