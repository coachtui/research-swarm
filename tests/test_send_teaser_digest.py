"""Unit tests for teaser digest helper functions."""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from inngest.functions.send_teaser_digest import (
    format_teaser_blurb,
    pick_top_signals,
)


RUN_DATE = datetime(2026, 4, 13, tzinfo=timezone.utc)


def _make_signal(
    ticker: str,
    verdict: str = "buy",
    screener_score: float = 5.0,
    fair_value_gap_pct: float = 15.0,
    ev_probability: float = 0.70,
    es_change_pct: float = 1.2,
    nq_change_pct: float = 2.3,
    synthesis_summary: str = "Strong thesis here.",
    catalyst_summary: str = "Earnings beat",
) -> MagicMock:
    s = MagicMock()
    s.ticker = ticker
    s.verdict = verdict
    s.screenerScore = screener_score
    s.fairValueGapPct = fair_value_gap_pct
    s.evProbability = ev_probability
    s.esChangePct = es_change_pct
    s.nqChangePct = nq_change_pct
    s.synthesisSummary = synthesis_summary
    s.catalystSummary = catalyst_summary
    s.runDate = RUN_DATE
    return s


class TestFormatTeaserBlurb:
    def test_includes_ticker_and_verdict(self):
        signal = _make_signal("NVDA")
        blurb = format_teaser_blurb(signal, base_url="https://dvrg.co")
        assert "NVDA" in blurb
        assert "Buy" in blurb

    def test_includes_fair_value_gap(self):
        signal = _make_signal("NVDA", fair_value_gap_pct=18.2)
        blurb = format_teaser_blurb(signal, base_url="https://dvrg.co")
        assert "18.2%" in blurb

    def test_includes_ev_probability_as_percent(self):
        signal = _make_signal("NVDA", ev_probability=0.72)
        blurb = format_teaser_blurb(signal, base_url="https://dvrg.co")
        assert "72%" in blurb

    def test_includes_market_context(self):
        signal = _make_signal("NVDA", es_change_pct=0.1, nq_change_pct=2.3)
        blurb = format_teaser_blurb(signal, base_url="https://dvrg.co")
        assert "ES" in blurb
        assert "NQ" in blurb

    def test_includes_preview_link(self):
        signal = _make_signal("NVDA")
        blurb = format_teaser_blurb(signal, base_url="https://dvrg.co")
        assert "https://dvrg.co/preview/nvda" in blurb

    def test_capitalises_verdict(self):
        signal = _make_signal("AAPL", verdict="hold")
        blurb = format_teaser_blurb(signal, base_url="https://dvrg.co")
        assert "Hold" in blurb

    def test_handles_missing_ev_probability(self):
        signal = _make_signal("AAPL")
        signal.evProbability = None
        blurb = format_teaser_blurb(signal, base_url="https://dvrg.co")
        assert "AAPL" in blurb  # Should not crash


class TestPickTopSignals:
    def test_prefers_buy_verdicts(self):
        signals = [
            _make_signal("HOLD1", verdict="hold", screener_score=10.0),
            _make_signal("BUY1", verdict="buy", screener_score=8.0),
            _make_signal("BUY2", verdict="buy", screener_score=7.0),
        ]
        result = pick_top_signals(signals, n=2)
        tickers = [s.ticker for s in result]
        assert "BUY1" in tickers
        assert "BUY2" in tickers
        assert "HOLD1" not in tickers

    def test_falls_back_to_all_verdicts_when_too_few_buys(self):
        signals = [
            _make_signal("BUY1", verdict="buy", screener_score=10.0),
            _make_signal("HOLD1", verdict="hold", screener_score=9.0),
            _make_signal("HOLD2", verdict="hold", screener_score=8.0),
        ]
        result = pick_top_signals(signals, n=3)
        assert len(result) == 3

    def test_returns_at_most_n(self):
        signals = [_make_signal(f"T{i}", verdict="buy", screener_score=float(i)) for i in range(20)]
        result = pick_top_signals(signals, n=7)
        assert len(result) == 7

    def test_sorts_by_screener_score_desc(self):
        signals = [
            _make_signal("LOW", verdict="buy", screener_score=1.0),
            _make_signal("HIGH", verdict="buy", screener_score=10.0),
        ]
        result = pick_top_signals(signals, n=2)
        assert result[0].ticker == "HIGH"

    def test_handles_empty_list(self):
        result = pick_top_signals([], n=7)
        assert result == []
