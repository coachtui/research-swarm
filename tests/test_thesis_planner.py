from execution.constants import MIN_TRADE_NOTIONAL, ROLE_BANDS
from execution.thesis.planner import (
    entry_price_and_ttl, plan_from_memo, size_thesis_entry,
)

_EQ = 70_000.0


def test_role_bands_scale_with_conviction_and_ceilings_only_shrink():
    hi = size_thesis_entry("anchor", 1.0, _EQ, 50e6, 0.02, 1e9, 1e9)
    lo = size_thesis_entry("catalyst", 0.0, _EQ, 50e6, 0.02, 1e9, 1e9)
    assert hi == round(ROLE_BANDS["anchor"][1] * _EQ, 2)
    assert lo == round(ROLE_BANDS["catalyst"][0] * _EQ, 2)
    # vol ceiling binds a twitchy name: 0.0075/0.10 * eq = 5,250 < anchor band
    assert size_thesis_entry("anchor", 1.0, _EQ, 50e6, 0.10, 1e9, 1e9) == 5250.0
    # cash binds
    assert size_thesis_entry("anchor", 1.0, _EQ, 50e6, 0.02, 1e9, 900.0) == 900.0
    # dust drops
    assert size_thesis_entry("anchor", 1.0, _EQ, 50e6, 0.02, 1e9,
                             MIN_TRADE_NOTIONAL - 1) == 0.0
    assert size_thesis_entry("anchor", 1.0, 0.0, 50e6, 0.02, 1e9, 1e9) == 0.0


def test_entry_pricing_styles():
    assert entry_price_and_ttl("at_market", 100.0, 95.0, 4.0) == (100.0, 7)
    assert entry_price_and_ttl("on_pullback", 100.0, 95.0, 4.0) == (96.0, 14)
    assert entry_price_and_ttl("on_pullback", 100.0, 98.0, 4.0) == (98.0, 14)


def _memo(stage, action="enter", ticker="BE"):
    return {"theses": [{"slug": "dc-energy", "stage": stage,
                        "stage_rationale": "r", "evidence_this_week": [],
                        "actions": [{"action": action, "ticker": ticker,
                                     "role": "anchor", "conviction": 0.7,
                                     "entry_style": "at_market",
                                     "why_now": "w", "why_this_expression": "e"}]}],
            "hypothesis_updates": [], "market_view": "v", "skipped": []}


def test_stage_gates_entries_but_not_reviews():
    ok = plan_from_memo(_memo("catching_on"), set(), {"BE"})
    assert [e["ticker"] for e in ok["entries"]] == ["BE"]
    assert ok["stage_updates"] == {"dc-energy": "catching_on"}

    late = plan_from_memo(_memo("crowded"), set(), {"BE"})
    assert late["entries"] == []
    assert late["rejected"][0]["reason"] == "stage_not_entry_legal"

    rev = plan_from_memo(_memo("crowded", action="review", ticker="MU"), {"MU"}, set())
    assert rev["reviews"] == ["MU"]


def test_universe_and_book_gates():
    out = plan_from_memo(_memo("pre_consensus"), set(), set())      # not screened
    assert out["rejected"][0]["reason"] == "not_in_validated_universe"
    out = plan_from_memo(_memo("pre_consensus"), {"BE"}, {"BE"})    # already held
    assert out["entries"] == [] and out["rejected"][0]["reason"] == "enter_already_held"
    out = plan_from_memo(_memo("pre_consensus", action="add"), set(), {"BE"})
    assert out["adds"] == [] and out["rejected"][0]["reason"] == "add_not_held"
    out = plan_from_memo(_memo("pre_consensus", action="add"), {"BE"}, {"BE"})
    assert [a["ticker"] for a in out["adds"]] == ["BE"]
