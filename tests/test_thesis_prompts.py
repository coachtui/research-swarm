import json

from execution.thesis.prompts import build_weekly_memo_prompt

_PACKET = {
    "theses": [{
        "slug": "dc-energy", "name": "DC Energy", "stage": "pre_consensus",
        "thesis": "power binds the buildout",
        "metadata": {"binding_constraint": "grid interconnect",
                     "leading_indicators": ["turbine lead times", "PPA announcements"]},
        "constituents": [{"ticker": "BE", "confidence": 0.8}],
        "ledger": [{"week": "2026-07-20", "stage": "pre_consensus",
                    "body": {"evidence_this_week": ["watched turbine lead times"]}}],
    }],
    "hypotheses": [{"hypothesisKey": "hbm-packaging",
                    "body": {"hypothesis": "packaging binds next"}}],
    "book": [{"symbol": "MU", "qty": 5, "avg_price": 991.64,
              "themes": ["memory-hbm"], "unrealized_plpc": 0.04}],
    "crowdedness": {"theme_rankings": [{"slug": "photonics", "score": 0.0437, "rank_change": 4}]},
    "candidates": {"BE": {"dist_200wma": -0.05, "rsi14": 41.0,
                          "fair_value_gap_pct": 22.0, "short_pct_float": 0.08}},
    "study_digest": {"body": {"rules": ["deliver-now power repriced first"]}},
    "regime": "neutral",
}


def test_prompt_carries_ledger_indicators_and_inversion_framing():
    p = build_weekly_memo_prompt(_PACKET)
    assert "turbine lead times" in p          # leading indicators verbatim
    assert "watched turbine lead times" in p  # ledger excerpt (reconciliation)
    assert "already priced" in p              # crowdedness inversion framing
    assert "reconcile" in p.lower()
    assert "deliver-now power repriced first" in p  # study digest rules


def test_prompt_states_output_schema_and_stage_rules():
    p = build_weekly_memo_prompt(_PACKET)
    for token in ('"stage"', '"why_now"', '"why_this_expression"',
                  '"entry_style"', '"hypothesis_updates"', '"market_view"',
                  "pre_consensus", "catching_on", "crowded", "priced",
                  "unverified"):
        assert token in p
    assert "ONLY a JSON object" in p


def test_prompt_survives_empty_packet():
    p = build_weekly_memo_prompt({})
    assert "ONLY a JSON object" in p and "no active theses" in p
