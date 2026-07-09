"""Tests for the pure escalation scoring module."""
from research_swarm.data.escalation import (
    EscalationCandidate,
    EscalationContext,
    escalation_score,
    select_escalations,
)

CTX = EscalationContext(favored_sectors=frozenset({"Technology", "Energy", "Financials"}))
EMPTY_CTX = EscalationContext(favored_sectors=frozenset())


def cand(**kw):
    return EscalationCandidate(ticker=kw.pop("ticker", "AAPL"),
                               screener_score=kw.pop("screener_score", 5.0), **kw)


class TestEscalationScore:
    def test_no_triggers_scores_zero(self):
        score, reasons = escalation_score(cand(), EMPTY_CTX)
        assert score == 0.0 and reasons == []

    def test_prior_buy(self):
        score, reasons = escalation_score(cand(prior_verdict="buy"), EMPTY_CTX)
        assert score == 3.0 and reasons == ["prior_buy"]

    def test_prior_hold_does_not_trigger(self):
        score, _ = escalation_score(cand(prior_verdict="hold"), EMPTY_CTX)
        assert score == 0.0

    def test_post_earnings_within_5_days(self):
        score, reasons = escalation_score(cand(days_since_earnings=5), EMPTY_CTX)
        assert score == 2.5 and reasons == ["post_earnings"]

    def test_earnings_6_days_ago_does_not_trigger(self):
        score, _ = escalation_score(cand(days_since_earnings=6), EMPTY_CTX)
        assert score == 0.0

    def test_outlook_favored_sector(self):
        score, reasons = escalation_score(cand(sector="Technology"), CTX)
        assert score == 2.0 and reasons == ["outlook_sector"]

    def test_unfavored_sector_does_not_trigger(self):
        score, _ = escalation_score(cand(sector="Utilities"), CTX)
        assert score == 0.0

    def test_no_outlook_means_no_sector_points(self):
        score, _ = escalation_score(cand(sector="Technology"), EMPTY_CTX)
        assert score == 0.0

    def test_divergence_up(self):
        score, reasons = escalation_score(
            cand(screener_score=6.0, prior_screener_score=3.0), EMPTY_CTX)
        assert score == 2.0 and reasons == ["score_divergence"]

    def test_divergence_down_also_triggers(self):
        score, _ = escalation_score(
            cand(screener_score=1.0, prior_screener_score=4.5), EMPTY_CTX)
        assert score == 2.0

    def test_small_move_does_not_trigger(self):
        score, _ = escalation_score(
            cand(screener_score=5.0, prior_screener_score=3.0), EMPTY_CTX)
        assert score == 0.0

    def test_no_prior_score_means_no_divergence(self):
        score, _ = escalation_score(cand(screener_score=9.0), EMPTY_CTX)
        assert score == 0.0

    def test_watchlist(self):
        score, reasons = escalation_score(cand(on_watchlist=True), EMPTY_CTX)
        assert score == 1.5 and reasons == ["watchlist"]

    def test_triggers_sum(self):
        score, reasons = escalation_score(
            cand(prior_verdict="buy", days_since_earnings=2, on_watchlist=True), EMPTY_CTX)
        assert score == 3.0 + 2.5 + 1.5
        assert reasons == ["prior_buy", "post_earnings", "watchlist"]


class TestSelectEscalations:
    def test_watchlist_alone_stays_below_threshold(self):
        decisions = select_escalations([cand(on_watchlist=True)], EMPTY_CTX)
        assert decisions[0].action == "hold"

    def test_exactly_threshold_escalates(self):
        decisions = select_escalations([cand(sector="Technology")], CTX)  # 2.0
        assert decisions[0].action == "swarm"

    def test_cap_takes_top_by_score(self):
        cands = [cand(ticker=f"T{i}", prior_verdict="buy") for i in range(4)]
        cands += [cand(ticker=f"E{i}", days_since_earnings=1) for i in range(3)]
        decisions = select_escalations(cands, EMPTY_CTX, cap=5)
        swarm = {d.ticker for d in decisions if d.action == "swarm"}
        # all four prior-buys (3.0) beat post-earnings (2.5); one earnings pick fills slot 5
        assert {"T0", "T1", "T2", "T3"} <= swarm and len(swarm) == 5

    def test_tiebreak_is_deterministic(self):
        cands = [cand(ticker="BBB", prior_verdict="buy", screener_score=5.0),
                 cand(ticker="AAA", prior_verdict="buy", screener_score=5.0)]
        first = select_escalations(cands, EMPTY_CTX, cap=1)
        second = select_escalations(list(reversed(cands)), EMPTY_CTX, cap=1)
        pick1 = [d.ticker for d in first if d.action == "swarm"]
        pick2 = [d.ticker for d in second if d.action == "swarm"]
        assert pick1 == pick2 == ["AAA"]  # ticker asc breaks the tie

    def test_fresh_report_reuses_without_consuming_slot(self):
        cands = [cand(ticker=f"T{i}", prior_verdict="buy") for i in range(5)]
        cands.append(cand(ticker="FRESH", prior_verdict="buy", has_fresh_report=True))
        decisions = select_escalations(cands, EMPTY_CTX, cap=5)
        by = {d.ticker: d for d in decisions}
        assert by["FRESH"].action == "reuse"
        assert sum(1 for d in decisions if d.action == "swarm") == 5

    def test_fresh_report_below_threshold_holds(self):
        decisions = select_escalations(
            [cand(on_watchlist=True, has_fresh_report=True)], EMPTY_CTX)
        assert decisions[0].action == "hold"

    def test_every_candidate_gets_a_decision_in_input_order(self):
        cands = [cand(ticker="A"), cand(ticker="B", prior_verdict="buy")]
        decisions = select_escalations(cands, EMPTY_CTX)
        assert [d.ticker for d in decisions] == ["A", "B"]
        assert decisions[0].score == 0.0 and decisions[1].score == 3.0
