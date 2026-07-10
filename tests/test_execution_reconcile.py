"""Tests for reconciliation and circuit-breaker math."""
from execution.constants import SECTOR_ETFS
from execution.engine.circuit_breaker import circuit_breaker_tripped
from execution.engine.reconcile import find_mismatches, reconcile_sleeve


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


class TestReconcileSleeve:
    """Per-sleeve reconciliation over a SHARED paper account — the landmine
    fix. A sleeve tolerates other sleeves' symbols but reconciles its own
    scope (engine book ∪ expected universe) exactly."""

    def test_sleeve_b_ignores_sleeve_a_stocks(self):
        # Broker holds B's sector ETF AND A's individual stock; B must NOT
        # freeze over AAPL — the pre-fix whole-account match would have.
        broker = {"XLK": 100.0, "AAPL": 5.0, "NVDA": 3.0}
        engine_b = {"XLK": 100.0}
        assert reconcile_sleeve(broker, engine_b, SECTOR_ETFS.keys()) == []

    def test_sleeve_b_still_catches_in_scope_drift(self):
        broker = {"XLK": 100.0, "AAPL": 5.0}
        engine_b = {"XLK": 110.0}
        result = reconcile_sleeve(broker, engine_b, SECTOR_ETFS.keys())
        assert len(result) == 1 and "XLK" in result[0]

    def test_sleeve_b_catches_phantom_sold_etf(self):
        # Engine thinks it sold XLK, but the broker still holds it -> XLK is in
        # B's expected universe, so the mismatch is still caught.
        result = reconcile_sleeve({"XLK": 100.0}, {}, SECTOR_ETFS.keys())
        assert len(result) == 1 and "XLK" in result[0]

    def test_sleeve_a_ignores_sector_etfs(self):
        # A's scope is only its own book (no expected universe): a sector ETF
        # owned by B is dropped, A's own stock reconciles clean.
        broker = {"XLK": 100.0, "AAPL": 5.0}
        engine_a = {"AAPL": 5.0}
        assert reconcile_sleeve(broker, engine_a, ()) == []

    def test_sleeve_a_mismatch_on_its_own_stock(self):
        broker = {"XLK": 100.0, "AAPL": 5.0}
        engine_a = {"AAPL": 10.0}
        result = reconcile_sleeve(broker, engine_a, ())
        assert len(result) == 1 and "AAPL" in result[0]


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
