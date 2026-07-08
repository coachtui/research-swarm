"""Tests for the prior-analysis relevance rules (api/services/relevance_service)."""

from datetime import date

import pytest

from api.services.relevance_service import evaluate_relevance


TODAY = date(2026, 7, 7)


def _evaluate(**overrides):
    params = dict(
        analysis_date=date(2026, 6, 20),  # 17 days old
        today=TODAY,
        prior_next_earnings="2026-07-29",
        price_at_analysis=100.0,
        current_price=104.0,
        filings_since=0,
    )
    params.update(overrides)
    return evaluate_relevance(**params)


class TestEvaluateRelevance:
    def test_fresh_report_is_reusable(self):
        verdict = _evaluate()
        assert verdict["reusable"] is True
        assert verdict["checks"]["price_move_pct"] == 4.0
        assert verdict["checks"]["new_8k_filings"] == 0

    def test_too_old_with_earnings_date(self):
        verdict = _evaluate(analysis_date=date(2026, 5, 1))  # 67 days
        assert verdict["reusable"] is False
        assert verdict["checks"]["stale_reason"] == "too_old"

    def test_tighter_age_cap_without_earnings_date(self):
        # 40 days old is fine with a known future earnings date...
        assert _evaluate(analysis_date=date(2026, 5, 28))["reusable"] is True
        # ...but stale when the earnings date is unknown (cap drops to 30)
        verdict = _evaluate(analysis_date=date(2026, 5, 28), prior_next_earnings=None)
        assert verdict["reusable"] is False
        assert verdict["checks"]["stale_reason"] == "too_old"

    def test_earnings_since_analysis(self):
        verdict = _evaluate(prior_next_earnings="2026-07-01")  # before today
        assert verdict["reusable"] is False
        assert verdict["checks"]["stale_reason"] == "earnings_since_analysis"

    def test_earnings_today_counts_as_stale(self):
        verdict = _evaluate(prior_next_earnings=TODAY.isoformat())
        assert verdict["reusable"] is False
        assert verdict["checks"]["stale_reason"] == "earnings_since_analysis"

    def test_unparseable_earnings_date_uses_tight_age_cap(self):
        # "2026-Q3"-style timeframes can't be compared — treated like unknown
        verdict = _evaluate(analysis_date=date(2026, 5, 28), prior_next_earnings="2026-Q3")
        assert verdict["reusable"] is False
        assert verdict["checks"]["stale_reason"] == "too_old"

    def test_price_moved_beyond_band(self):
        verdict = _evaluate(current_price=111.0)  # +11%
        assert verdict["reusable"] is False
        assert verdict["checks"]["stale_reason"] == "price_moved"

    def test_price_drop_beyond_band(self):
        verdict = _evaluate(current_price=89.0)  # -11%
        assert verdict["reusable"] is False
        assert verdict["checks"]["stale_reason"] == "price_moved"

    def test_missing_price_is_conservative(self):
        for overrides in ({"current_price": None}, {"price_at_analysis": None}):
            verdict = _evaluate(**overrides)
            assert verdict["reusable"] is False
            assert verdict["checks"]["stale_reason"] == "price_unverifiable"

    def test_new_8k_filing_is_stale(self):
        verdict = _evaluate(filings_since=1)
        assert verdict["reusable"] is False
        assert verdict["checks"]["stale_reason"] == "new_8k_filings"

    def test_8k_fetch_failure_is_skipped_not_fatal(self):
        verdict = _evaluate(filings_since=None)
        assert verdict["reusable"] is True
        assert verdict["checks"]["8k_check_skipped"] is True
