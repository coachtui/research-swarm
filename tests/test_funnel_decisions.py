"""Weekly planner: exits carry the discipline, winners run, no churn."""
from execution.constants import OUTCOMPETE_MARGIN, RISK_TRIM_CEILING, RISK_TRIM_TARGET
from execution.funnel.decisions import plan_decisions

SLEEVE = 70_000.0


def _h(sym, mv, conv, vetoed=False, review_failed=False):
    return {"symbol": sym, "market_value": mv, "conviction": conv,
            "vetoed": vetoed, "theme_review_failed": review_failed}


def _c(sym, conv, vetoed=False):
    return {"symbol": sym, "conviction": conv, "vetoed": vetoed}


def test_sell_verdict_and_failed_review_exit():
    out = plan_decisions(
        [_h("BAD", 5_000, 0.0, vetoed=True), _h("DEAD", 5_000, 40.0, review_failed=True),
         _h("OK", 5_000, 70.0)],
        [], SLEEVE, max_positions=15,
    )
    reasons = {e["symbol"]: e["reason"] for e in out["exits"]}
    assert reasons == {"BAD": "sell_verdict", "DEAD": "theme_review_failed"}


def test_risk_trim_only_above_ceiling_no_maintenance_rebalance():
    big = SLEEVE * (RISK_TRIM_CEILING + 0.02)           # 22% → trim
    drifted = SLEEVE * 0.16                             # 16% winner → untouched
    out = plan_decisions([_h("BIG", big, 80.0), _h("WIN", drifted, 75.0)], [], SLEEVE, 15)
    assert out["exits"] == []
    assert len(out["trims"]) == 1
    t = out["trims"][0]
    assert t["symbol"] == "BIG" and t["reason"] == "risk_trim"
    assert t["sell_notional"] == round(big - RISK_TRIM_TARGET * SLEEVE, 2)


def test_outcompete_needs_margin():
    holds = [_h("WEAK", 5_000, 50.0), _h("MID", 5_000, 70.0)]
    # book full at 2; challenger inside the margin → no churn
    close = plan_decisions(holds, [_c("CH1", 50.0 + OUTCOMPETE_MARGIN - 1)], SLEEVE, 2)
    assert close["exits"] == [] and close["entry_queue"] == []
    # challenger clears the margin → swap weakest
    swap = plan_decisions(holds, [_c("CH2", 50.0 + OUTCOMPETE_MARGIN + 1)], SLEEVE, 2)
    assert {e["symbol"]: e["reason"] for e in swap["exits"]} == {"WEAK": "outcompeted"}
    assert swap["entry_queue"] == ["CH2"]


def test_entry_queue_fills_open_slots_by_conviction():
    out = plan_decisions(
        [_h("H1", 5_000, 70.0)],
        [_c("A", 90.0), _c("B", 80.0), _c("VETO", 95.0, vetoed=True), _c("H1", 99.0)],
        SLEEVE, max_positions=3,
    )
    assert out["entry_queue"] == ["A", "B"]   # veto blocked, held name blocked, 2 slots


def test_exit_frees_slot_for_entry():
    out = plan_decisions(
        [_h("BAD", 5_000, 0.0, vetoed=True), _h("OK", 5_000, 70.0)],
        [_c("NEW", 60.0)], SLEEVE, max_positions=2,
    )
    assert out["entry_queue"] == ["NEW"]
