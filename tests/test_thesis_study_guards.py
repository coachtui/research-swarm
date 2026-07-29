"""Founding-premise guards (owner ruling 2026-07-27): the 13F study pass is
a CURRICULUM. Tickers from filings get ZERO order authority. Phase A's
guard style (test_funnel_decisions.py::test_no_entry_authority_remains).
"""
import inspect
import json

import execution.thesis.study as study
import execution.thesis.study_edgar as study_edgar
import execution.thesis.study_prompts as study_prompts
import inngest_app.functions.thirteenf_study_quarterly as cron
from execution.thesis.study_prompts import parse_study_response

_BANNED = ("execution.broker", "submit_limit_buy", "submit_order",
           "plan_from_memo", "plan_decisions", "position_size", "alpaca")


def test_study_modules_never_touch_orders_or_broker():
    """No study module may reference the broker, order submission, or the
    planner — the digest's only consumers are the ledger and the journal."""
    for mod in (study, study_edgar, study_prompts, cron):
        src = inspect.getsource(mod).lower()
        for banned in _BANNED:
            assert banned not in src, f"{mod.__name__} references {banned!r}"


def test_digest_schema_carries_method_rules_never_actions():
    """The parsed digest has no actionable shape: no actions, tickers-as-
    orders, conviction, or sizing — method rules, moves (descriptive),
    summary, skipped. The weekly memo reads it as PROSE context only."""
    out = parse_study_response(json.dumps({
        "method_rules": [{"rule": "r", "evidence": "e", "moves_cited": []}],
        "moves": [{"issuer": "X", "direction": "new long", "window": "Q1",
                   "what_was_knowable": "k"}],
        "summary": "s",
        # a drifted model trying to smuggle orders in:
        "actions": [{"action": "enter", "ticker": "NVDA"}]}))
    assert set(out) == {"method_rules", "moves", "summary", "skipped"}
    assert "actions" not in out


def test_study_prompt_states_the_premise():
    """The prompt itself must teach the framing — curriculum, stale, no
    copying — so a future prompt edit that drops it goes red."""
    from execution.thesis.study_prompts import build_study_prompt
    p = build_study_prompt({"fund": "F", "as_of": "a", "filed": "f",
                            "prior": "p", "quarters_available": [],
                            "book_value": 1.0, "material_moves": []}).lower()
    assert "never copy" in p and "stale" in p and "method" in p


def test_trusted_fund_list_shape_is_extensible():
    from execution.constants import TRUSTED_FUNDS_13F
    assert isinstance(TRUSTED_FUNDS_13F, list)
    for fund in TRUSTED_FUNDS_13F:
        assert fund["name"] and isinstance(fund["ciks"], list) and fund["ciks"]
    salp = TRUSTED_FUNDS_13F[0]
    assert set(salp["ciks"]) == {"0002045724", "0002038540"}
