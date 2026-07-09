"""Lifecycle rules: caps, dethrone, activation floor, delta gate."""
import pytest

from execution.themes.lifecycle import plan_delta_actions, plan_monthly_actions

VALID = {"adv": 5e6, "market_cap": 5e8, "price": 20.0, "validated_at": "2026-07-09T00:00:00Z"}


def _proposal(slug, action="add", confidence=0.8, n_constituents=6):
    return {
        "slug": slug, "name": slug.title(), "action": action,
        "thesis": "t", "confidence": confidence, "metadata": {},
        "constituents": [
            {"ticker": f"T{i}{slug[:2].upper()}", "exposure": "x", "confidence": 0.9 - i * 0.01}
            for i in range(n_constituents)
        ],
    }


def _validation_for(proposals, valid=True):
    out = {}
    for p in proposals:
        for c in p["constituents"]:
            out[c["ticker"]] = VALID if valid else None
    return out


def _current(slug, status="active", confidence=0.5, origin="seed", tickers=()):
    return {"slug": slug, "status": status, "origin": origin, "confidence": confidence,
            "constituents": [{"ticker": t, "status": "active"} for t in tickers]}


def test_add_activates_with_enough_valid_constituents():
    props = [_proposal("gas-turbines")]
    plan = plan_monthly_actions([], props, _validation_for(props))
    acts = plan["actions"]
    assert len(acts) == 1 and acts[0]["kind"] == "activate_theme"
    assert len(acts[0]["constituents"]) == 6
    assert acts[0]["dethroned"] is None


def test_add_rejected_below_min_valid_constituents():
    props = [_proposal("gas-turbines", n_constituents=6)]
    validation = _validation_for(props, valid=False)
    plan = plan_monthly_actions([], props, validation)
    assert plan["actions"] == []
    assert any("gas-turbines" in r for r in plan["rejected"])


def test_constituents_capped_at_max_by_confidence():
    props = [_proposal("chips-x", n_constituents=25)]
    plan = plan_monthly_actions([], props, _validation_for(props))
    kept = plan["actions"][0]["constituents"]
    assert len(kept) == 20
    assert kept == sorted(kept, key=lambda c: -c["confidence"])


def test_at_cap_dethrones_weakest_incumbent():
    current = [_current(f"t{i}", confidence=0.3 + i * 0.05) for i in range(12)]
    props = [_proposal("gas-turbines", confidence=0.9)]
    plan = plan_monthly_actions(current, props, _validation_for(props))
    act = plan["actions"][-1]
    assert act["kind"] == "activate_theme" and act["dethroned"] == "t0"
    retires = [a for a in plan["actions"] if a["kind"] == "retire_theme"]
    assert retires and retires[0]["slug"] == "t0"


def test_at_cap_weaker_proposal_rejected():
    current = [_current(f"t{i}", confidence=0.8) for i in range(12)]
    props = [_proposal("weak-theme", confidence=0.5)]
    plan = plan_monthly_actions(current, props, _validation_for(props))
    assert all(a["kind"] != "activate_theme" for a in plan["actions"])
    assert any("weak-theme" in r for r in plan["rejected"])


def test_retire_only_applies_to_active_theme():
    current = [_current("photonics")]
    props = [_proposal("photonics", action="retire"), _proposal("ghost", action="retire")]
    plan = plan_monthly_actions(current, props, {})
    kinds = [(a["kind"], a["slug"]) for a in plan["actions"]]
    assert ("retire_theme", "photonics") in kinds
    assert not any(s == "ghost" for _, s in kinds)


def test_reactivation_flagged_for_retired_slug():
    current = [_current("space", status="retired")]
    props = [_proposal("space", action="add")]
    plan = plan_monthly_actions(current, props, _validation_for(props))
    assert plan["actions"][0]["reactivated"] is True


def test_keep_produces_update_with_diff():
    current = [_current("photonics", tickers=("LASR", "VIAV"))]
    props = [_proposal("photonics", action="keep", n_constituents=6)]
    props[0]["constituents"][0] = {"ticker": "LASR", "exposure": "x", "confidence": 0.9}
    plan = plan_monthly_actions(current, props, _validation_for(props))
    act = plan["actions"][0]
    assert act["kind"] == "update_theme"
    assert "VIAV" in act["remove"]
    assert all(c["ticker"] != "LASR" for c in act["add"])  # unchanged, not re-added


def test_delta_below_threshold_is_journal_only():
    current = [_current("photonics", tickers=("LASR",))]
    deltas = [{"slug": "photonics",
               "add": [{"ticker": "NEWT", "exposure": "x", "confidence": 0.6}],
               "remove": []}]
    plan = plan_delta_actions(current, deltas, {"NEWT": VALID})
    assert plan["actions"][0]["kind"] == "journal_only"


def test_delta_above_threshold_applies_and_respects_cap():
    current = [_current("photonics", tickers=tuple(f"C{i}" for i in range(20)))]
    deltas = [{"slug": "photonics",
               "add": [{"ticker": "NEWT", "exposure": "x", "confidence": 0.9}],
               "remove": []}]
    plan = plan_delta_actions(current, deltas, {"NEWT": VALID})
    assert plan["actions"] == []  # at MAX_THEME_CONSTITUENTS — add rejected
    assert any("NEWT" in r for r in plan["rejected"])


def test_delta_for_unknown_theme_rejected():
    plan = plan_delta_actions([], [{"slug": "ghost", "add": [], "remove": []}], {})
    assert plan["actions"] == []
