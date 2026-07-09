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
