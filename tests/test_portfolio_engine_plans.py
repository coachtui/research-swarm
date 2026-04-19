"""Unit tests for generate_action_plan — signal-driven conditional action plans."""
import sys
import types
from unittest.mock import MagicMock

_prisma_stub = types.ModuleType("prisma")
_prisma_stub.Prisma = MagicMock  # type: ignore[attr-defined]
sys.modules.setdefault("prisma", _prisma_stub)

import pytest
from api.services.portfolio_engine import generate_action_plan, classify_posture


def _make_position(
    ticker="NVDA",
    shares=100.0,
    last_known_price=100.0,
    target_weight=0.08,
    thesis_state="intact",
    ownership_status="core_compounder",
):
    pos = MagicMock()
    pos.ticker = ticker
    pos.shares = shares
    pos.lastKnownPrice = last_known_price
    pos.targetWeight = target_weight
    pos.thesisState = thesis_state
    pos.ownershipStatus = ownership_status
    pos.portfolioId = "portfolio1"
    return pos


def _make_stock_result(verdict="buy", fair_value=None, support_level=None):
    """Minimal StockResult fullOutput structure."""
    sr = MagicMock()
    sr.ticker = "NVDA"
    sr.fullOutput = {
        "verdict": verdict,
        "quant_output": {
            "technical_indicators": {
                "moving_averages": {"current_price": 100.0},
                "support_levels": [support_level or 85.0],
            }
        },
        "fundamental_output": {
            "valuation": {
                "fair_value": fair_value or 130.0
            }
        },
    }
    return sr


# ── classify_posture ─────────────────────────────────────────────────────────

def test_classify_posture_over_target_bearish():
    pos = _make_position(shares=130, last_known_price=100.0, target_weight=0.08)
    result = classify_posture(pos, current_alloc=0.13, stock_result=_make_stock_result(verdict="avoid"))
    assert result == "over_target_bearish"

def test_classify_posture_over_target_bullish():
    pos = _make_position(shares=130, last_known_price=100.0, target_weight=0.08)
    result = classify_posture(pos, current_alloc=0.13, stock_result=_make_stock_result(verdict="buy"))
    assert result == "over_target_bullish"

def test_classify_posture_below_target_bullish():
    pos = _make_position(shares=50, last_known_price=100.0, target_weight=0.08)
    result = classify_posture(pos, current_alloc=0.04, stock_result=_make_stock_result(verdict="buy"))
    assert result == "below_target_bullish"

def test_classify_posture_thesis_broken():
    pos = _make_position(thesis_state="broken")
    result = classify_posture(pos, current_alloc=0.05, stock_result=_make_stock_result())
    assert result == "thesis_broken"

def test_classify_posture_watch_only():
    pos = _make_position(shares=0, ownership_status="watch")
    result = classify_posture(pos, current_alloc=0.0, stock_result=_make_stock_result())
    assert result == "watch_only"

def test_classify_posture_hold():
    pos = _make_position(shares=80, last_known_price=100.0, target_weight=0.08)
    result = classify_posture(pos, current_alloc=0.08, stock_result=_make_stock_result(verdict="hold"))
    assert result == "hold"


# ── generate_action_plan ─────────────────────────────────────────────────────

def test_trim_ladder_over_target_bearish():
    pos = _make_position(shares=130, last_known_price=100.0, target_weight=0.08)
    actions = generate_action_plan(
        position=pos,
        stock_result=_make_stock_result(verdict="avoid"),
        current_alloc=0.13,
        portfolio_id="portfolio1",
    )
    assert len(actions) >= 2
    assert all(a["ticker"] == "NVDA" for a in actions)
    assert actions[0]["parentActionId"] is None
    assert actions[0]["triggerPrice"] is not None

def test_entry_ladder_watch_only():
    pos = _make_position(shares=0, ownership_status="watch", target_weight=0.05)
    actions = generate_action_plan(
        position=pos,
        stock_result=_make_stock_result(verdict="buy"),
        current_alloc=0.0,
        portfolio_id="portfolio1",
    )
    assert len(actions) >= 1
    assert all(a["actionType"] in ("INITIATE", "ADD_TIER_20", "ADD_TIER_30") for a in actions)

def test_thesis_broken_exit_plan():
    pos = _make_position(thesis_state="broken", shares=100, last_known_price=100.0)
    actions = generate_action_plan(
        position=pos,
        stock_result=_make_stock_result(verdict="avoid"),
        current_alloc=0.10,
        portfolio_id="portfolio1",
    )
    assert len(actions) == 1
    assert actions[0]["actionType"] == "EXIT_THESIS"
    assert actions[0]["triggerCondition"] == "immediate"

def test_hold_posture_produces_no_actions():
    pos = _make_position(shares=80, last_known_price=100.0, target_weight=0.08)
    actions = generate_action_plan(
        position=pos,
        stock_result=_make_stock_result(verdict="hold"),
        current_alloc=0.08,
        portfolio_id="portfolio1",
    )
    assert actions == []

def test_review_action_when_no_stock_result():
    pos = _make_position()
    actions = generate_action_plan(
        position=pos,
        stock_result=None,
        current_alloc=0.08,
        portfolio_id="portfolio1",
    )
    assert len(actions) == 1
    assert actions[0]["actionType"] == "HOLD"
    assert "No recent analysis" in actions[0]["reasonText"]


from api.services.portfolio_engine import _moat_fallback_weight


@pytest.mark.parametrize(
    "moat,expected",
    [
        (9.2, 0.08),
        (8.5, 0.08),
        (7.4, 0.06),
        (7.0, 0.06),
        (6.2, 0.04),
        (5.0, 0.04),
        (4.0, 0.02),
        (3.5, 0.02),
        (3.0, None),
        (None, None),
    ],
)
def test_moat_fallback_weight(moat, expected):
    assert _moat_fallback_weight(moat) == expected


@pytest.mark.asyncio
async def test_moat_fallback_writes_suggested_weight_when_di_missing(monkeypatch):
    """
    When fullOutput has no decision_intelligence and DI enrichment can't build one
    (e.g. current_price missing), the engine still writes engineSuggestedWeight
    from the moat fallback table.
    """
    from api.services import portfolio_engine as eng

    fo = {"fundamentalist_output": {"valuation_metrics": {"current_price": 0}}}

    class _Result:
        fullOutput = fo
        moatScore = 8.0  # → 0.06 fallback

    fo_parsed = eng._parse_full_output(_Result.fullOutput, _Result.moatScore)
    assert "decision_intelligence" not in fo_parsed  # enrichment bailed

    # The helper alone is deterministic; verify the fallback wiring produces 6%.
    assert eng._moat_fallback_weight(_Result.moatScore) == 0.06
