"""Tests for the pure Sleeve B rotation logic."""
from execution.engine.sleeve_b import compute_targets, compute_weights, select_etfs


def _rankings(order):
    """Build sectorRankings with rank_1m = position in `order` (1-based)."""
    return [{"etf": etf, "sector": etf, "rank_1m": i + 1, "rank_change": 0, "score": 1.0 - i * 0.1}
            for i, etf in enumerate(order)]


RANKINGS = _rankings(["XLK", "XLE", "XLF", "XLI", "XLV", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC"])


class TestSelectEtfs:
    def test_fresh_start_takes_top_3(self):
        assert select_etfs(RANKINGS, held=[], regime="risk_on") == ["XLK", "XLE", "XLF"]

    def test_incumbent_survives_one_rank_slip(self):
        # XLF slipped to rank 4; challenger XLI is rank 3 — only 1 better: hold.
        rankings = _rankings(["XLK", "XLE", "XLI", "XLF", "XLV", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC"])
        assert select_etfs(rankings, held=["XLK", "XLE", "XLF"], regime="risk_on") == ["XLK", "XLE", "XLF"]

    def test_challenger_displaces_on_clear_margin(self):
        # XLF slipped to rank 5; challenger XLI is rank 3 — 2 better: displace.
        rankings = _rankings(["XLK", "XLE", "XLI", "XLV", "XLF", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC"])
        assert select_etfs(rankings, held=["XLK", "XLE", "XLF"], regime="risk_on") == ["XLK", "XLE", "XLI"]

    def test_risk_off_single_best_defensive(self):
        # Best-ranked defensive in RANKINGS is XLV (rank 5).
        assert select_etfs(RANKINGS, held=["XLK", "XLE", "XLF"], regime="risk_off") == ["XLV"]


class TestComputeWeights:
    def test_full_conviction_uses_base_weights(self):
        assert compute_weights(["XLK", "XLE", "XLF"], conviction=1.0) == {
            "XLK": 0.5, "XLE": 0.3, "XLF": 0.2,
        }

    def test_zero_conviction_equal_weights(self):
        weights = compute_weights(["XLK", "XLE", "XLF"], conviction=0.0)
        assert all(abs(w - 1 / 3) < 1e-6 for w in weights.values())

    def test_none_conviction_blends_halfway(self):
        weights = compute_weights(["XLK", "XLE", "XLF"], conviction=None)
        assert abs(weights["XLK"] - (0.5 * 0.5 + 0.5 / 3)) < 1e-6

    def test_single_etf_gets_full_weight(self):
        assert compute_weights(["XLV"], conviction=0.8) == {"XLV": 1.0}


class TestComputeTargets:
    def test_neutral_regime_holds_30pct_cash(self):
        outlook = {"id": "o1", "regime": "neutral", "conviction": 1.0, "sectorRankings": RANKINGS}
        result = compute_targets(outlook, held=[], sleeve_equity=30000.0)
        assert sum(result["targets"].values()) == 21000.0  # 70% invested
        assert result["targets"]["XLK"] == 10500.0  # 0.5 * 21000

    def test_risk_off_majority_cash(self):
        outlook = {"id": "o1", "regime": "risk_off", "conviction": 0.9, "sectorRankings": RANKINGS}
        result = compute_targets(outlook, held=["XLK"], sleeve_equity=30000.0)
        assert result["targets"] == {"XLV": 12000.0}  # 40% invested, 60% cash

    def test_journal_is_complete(self):
        outlook = {"id": "o1", "regime": "risk_on", "conviction": 0.7, "sectorRankings": RANKINGS}
        journal = compute_targets(outlook, held=["XLE"], sleeve_equity=30000.0)["journal"]
        for key in ("outlook_id", "regime", "conviction", "invested_fraction",
                    "sleeve_equity", "selection", "weights", "held_before"):
            assert key in journal
        assert journal["outlook_id"] == "o1"
