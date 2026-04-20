"""Unit tests for weekly alert evaluator."""
import pytest

from api.services.alert_evaluator import (
    AlertEvent,
    evaluate_signal_change,
    EV_PROB_THRESHOLD,
)


def _sig(verdict=None, ev=None, prior_verdict=None, prior_ev=None):
    """Build a minimal signal-shaped dict for tests."""
    return {
        "ticker": "AAPL",
        "verdict": verdict,
        "evProbability": ev,
        "priorVerdict": prior_verdict,
        "priorEvProbability": prior_ev,
    }


class TestVerdictFlip:
    def test_hold_to_buy_triggers(self):
        events = evaluate_signal_change(_sig(verdict="buy", prior_verdict="hold"))
        assert any(e.kind == "verdict_flip" for e in events)

    def test_buy_to_avoid_triggers(self):
        events = evaluate_signal_change(_sig(verdict="avoid", prior_verdict="buy"))
        assert any(e.kind == "verdict_flip" for e in events)

    def test_same_verdict_no_event(self):
        events = evaluate_signal_change(_sig(verdict="buy", prior_verdict="buy"))
        assert not any(e.kind == "verdict_flip" for e in events)

    def test_missing_prior_verdict_no_event(self):
        events = evaluate_signal_change(_sig(verdict="buy", prior_verdict=None))
        assert not any(e.kind == "verdict_flip" for e in events)

    def test_missing_current_verdict_no_event(self):
        events = evaluate_signal_change(_sig(verdict=None, prior_verdict="buy"))
        assert not any(e.kind == "verdict_flip" for e in events)

    def test_case_insensitive_match(self):
        """'BUY' and 'buy' should not trigger a flip."""
        events = evaluate_signal_change(_sig(verdict="BUY", prior_verdict="buy"))
        assert not any(e.kind == "verdict_flip" for e in events)


class TestEvProbabilityChange:
    def test_large_jump_triggers(self):
        events = evaluate_signal_change(_sig(ev=0.80, prior_ev=0.60))
        assert any(e.kind == "ev_change" for e in events)

    def test_large_drop_triggers(self):
        events = evaluate_signal_change(_sig(ev=0.40, prior_ev=0.60))
        assert any(e.kind == "ev_change" for e in events)

    def test_small_change_no_event(self):
        events = evaluate_signal_change(_sig(ev=0.65, prior_ev=0.60))
        assert not any(e.kind == "ev_change" for e in events)

    def test_exactly_at_threshold_triggers(self):
        events = evaluate_signal_change(
            _sig(ev=0.60 + EV_PROB_THRESHOLD, prior_ev=0.60)
        )
        assert any(e.kind == "ev_change" for e in events)

    def test_missing_ev_no_event(self):
        events = evaluate_signal_change(_sig(ev=None, prior_ev=0.60))
        assert not any(e.kind == "ev_change" for e in events)

    def test_missing_prior_no_event(self):
        events = evaluate_signal_change(_sig(ev=0.80, prior_ev=None))
        assert not any(e.kind == "ev_change" for e in events)


class TestCombinedEvents:
    def test_both_events_emitted_together(self):
        events = evaluate_signal_change(
            _sig(verdict="buy", prior_verdict="hold", ev=0.80, prior_ev=0.55)
        )
        kinds = {e.kind for e in events}
        assert kinds == {"verdict_flip", "ev_change"}

    def test_no_events_when_nothing_changed(self):
        events = evaluate_signal_change(
            _sig(verdict="hold", prior_verdict="hold", ev=0.60, prior_ev=0.60)
        )
        assert events == []


class TestAlertEventPayload:
    def test_verdict_flip_event_payload(self):
        [event] = [
            e for e in evaluate_signal_change(
                _sig(verdict="buy", prior_verdict="hold")
            )
            if e.kind == "verdict_flip"
        ]
        assert event.ticker == "AAPL"
        assert event.prior_value == "hold"
        assert event.current_value == "buy"

    def test_ev_change_event_payload(self):
        [event] = [
            e for e in evaluate_signal_change(_sig(ev=0.80, prior_ev=0.55))
            if e.kind == "ev_change"
        ]
        assert event.ticker == "AAPL"
        assert event.prior_value == 0.55
        assert event.current_value == 0.80
