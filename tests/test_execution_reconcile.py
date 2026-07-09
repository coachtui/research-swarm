"""Tests for reconciliation and circuit-breaker math."""
from execution.engine.circuit_breaker import circuit_breaker_tripped
from execution.engine.reconcile import find_mismatches


class TestFindMismatches:
    def test_clean_within_tolerance(self):
        # 1% relative tolerance absorbs fractional-share rounding drift
        assert find_mismatches({"XLK": 100.0}, {"XLK": 100.5}) == []

    def test_qty_drift_beyond_tolerance(self):
        result = find_mismatches({"XLK": 100.0}, {"XLK": 110.0})
        assert len(result) == 1 and "XLK" in result[0]

    def test_symbol_only_at_broker(self):
        result = find_mismatches({"XLK": 100.0, "AAPL": 5.0}, {"XLK": 100.0})
        assert len(result) == 1 and "AAPL" in result[0]

    def test_symbol_only_in_engine(self):
        result = find_mismatches({}, {"XLE": 10.0})
        assert len(result) == 1 and "XLE" in result[0]


class TestCircuitBreaker:
    def test_trips_at_minus_15pp_vs_spy(self):
        # sleeve -10%, SPY +5% -> -15pp: trips
        assert circuit_breaker_tripped(27000.0, 30000.0, 630.0, 600.0) is True

    def test_holds_above_threshold(self):
        # sleeve -10%, SPY +4% -> -14pp: holds
        assert circuit_breaker_tripped(27000.0, 30000.0, 624.0, 600.0) is False

    def test_absolute_loss_alone_does_not_trip(self):
        # sleeve -14%, SPY -14% -> 0pp relative: holds
        assert circuit_breaker_tripped(25800.0, 30000.0, 516.0, 600.0) is False

    def test_garbage_inception_never_trips(self):
        assert circuit_breaker_tripped(27000.0, 0.0, 630.0, 600.0) is False
