"""Prompts encode the SA method + hard caps so the LLM pre-filters."""
from execution.constants import (
    MAX_ACTIVE_THEMES,
    MAX_THEME_CONSTITUENTS,
    MIN_THEME_CONSTITUENTS,
)
from execution.themes.prompts import build_delta_prompt, build_monthly_prompt

CONTEXT = {
    "active_themes": [{
        "slug": "photonics", "name": "Photonics", "origin": "seed",
        "thesis": "Optical I/O bottleneck", "confidence": 0.6,
        "constituents": [{"ticker": "LASR", "exposure": "Laser subsystems", "confidence": 0.8}],
    }],
    "retired_themes": [],
    "latest_rankings": [{"slug": "photonics", "score": 0.02, "rank_1m": 1}],
    "research": {"watchlist": ["AEHR"], "supply_chain": ["SK Hynix"], "news_entities": ["CoreWeave"]},
}


def test_monthly_prompt_encodes_sa_method_and_caps():
    p = build_monthly_prompt(CONTEXT)
    for anchor in ("demand chain", "binding constraint", "consensus",
                   "leading indicators", "log space"):
        assert anchor in p.lower(), anchor
    assert str(MAX_ACTIVE_THEMES) in p
    assert str(MIN_THEME_CONSTITUENTS) in p
    assert str(MAX_THEME_CONSTITUENTS) in p
    # current state + research grounding present
    assert "photonics" in p and "LASR" in p and "AEHR" in p and "SK Hynix" in p
    # output contract
    assert '"action"' in p and '"retire"' in p and '"constituents"' in p


def test_monthly_prompt_tolerates_empty_context():
    p = build_monthly_prompt({"active_themes": [], "retired_themes": [],
                              "latest_rankings": None,
                              "research": {"watchlist": [], "supply_chain": [], "news_entities": []}})
    assert "none yet" in p.lower()


def test_delta_prompt_is_constituent_only():
    p = build_delta_prompt({"active_themes": CONTEXT["active_themes"]})
    assert "photonics" in p and "LASR" in p
    assert '"add"' in p and '"remove"' in p
    assert "retire" not in p.lower().replace('"remove"', "")  # no theme-level actions


def test_monthly_prompt_demands_forward_hypotheses_and_roles():
    md = build_monthly_prompt({})
    for phrase in ("what binds NEXT", "next_constraints", "time-to-solve",
                   "anchor", "pure-play", "catalyst", "time-to-survive",
                   "second-order losers"):
        assert phrase in md, phrase


def test_monthly_prompt_carries_vetoes_and_prior_hypotheses():
    """The pass only ever restated the list it was shown (Sept 2026: seven
    'keep's with added=[]). It must see what the entry screen disqualified and
    what it itself hypothesised earlier, and be told a keep is a search."""
    ctx = {**CONTEXT,
           "vetoed": {"ATKR": "acquired by Prysmian for $95 cash"},
           "prior_hypotheses": [{"first_seen": "2026-09-01",
                                 "hypothesis": "grid-scale BESS binds next",
                                 "candidates": ["FLNC"], "leading_indicators": ["x"],
                                 "falsification": "y"}]}
    p = build_monthly_prompt(ctx)
    assert "ATKR" in p and "Prysmian" in p and "never propose" in p
    assert "grid-scale BESS binds next" in p and "2026-09-01" in p
    assert "graduate it" in p and "falsified" in p
    assert "A keep is NOT a restatement" in p
    assert f"at least {MIN_THEME_CONSTITUENTS + 3} candidate" in p


def test_monthly_prompt_without_history_says_so():
    p = build_monthly_prompt(CONTEXT)
    assert "Disqualified names" in p and "Your prior forward hypotheses" in p
    assert p.count("none") >= 2


def test_delta_prompt_carries_vetoes():
    p = build_delta_prompt({"active_themes": CONTEXT["active_themes"],
                            "vetoed": {"ATKR": "cash deal"}})
    assert "ATKR: cash deal" in p and "never propose" in p
    # still constituent-only
    assert "retire" not in p.lower().replace('"remove"', "")
