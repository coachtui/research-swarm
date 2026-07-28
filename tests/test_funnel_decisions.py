"""Weekly planner: exits carry the discipline, winners run, no churn."""
from execution.constants import RISK_TRIM_CEILING, RISK_TRIM_TARGET
from execution.funnel.decisions import plan_decisions

SLEEVE = 70_000.0


def _h(sym, mv, conv, vetoed=False, review_failed=False):
    return {"symbol": sym, "market_value": mv, "conviction": conv,
            "vetoed": vetoed, "theme_review_failed": review_failed}


def test_sell_verdict_and_failed_review_exit():
    out = plan_decisions(
        [_h("BAD", 5_000, 0.0, vetoed=True), _h("DEAD", 5_000, 40.0, review_failed=True),
         _h("OK", 5_000, 70.0)],
        SLEEVE, max_positions=15,
    )
    reasons = {e["symbol"]: e["reason"] for e in out["exits"]}
    assert reasons == {"BAD": "sell_verdict", "DEAD": "theme_review_failed"}


def test_risk_trim_only_above_ceiling_no_maintenance_rebalance():
    big = SLEEVE * (RISK_TRIM_CEILING + 0.02)           # 22% → trim
    drifted = SLEEVE * 0.16                             # 16% winner → untouched
    out = plan_decisions([_h("BIG", big, 80.0), _h("WIN", drifted, 75.0)], SLEEVE, 15)
    assert out["exits"] == []
    assert len(out["trims"]) == 1
    t = out["trims"][0]
    assert t["symbol"] == "BIG" and t["reason"] == "risk_trim"
    assert t["sell_notional"] == round(big - RISK_TRIM_TARGET * SLEEVE, 2)


def test_trim_ceiling_none_disables_mechanical_trims():
    holdings = [{"symbol": "BIG", "conviction": 80.0, "market_value": 30_000.0}]
    plan = plan_decisions(holdings, 100_000.0, 15, trim_ceiling=None)
    assert plan["trims"] == []


def test_defaults_keep_old_trim_behavior():
    # Verify defaults maintain old trim behavior (exits are sell-verdict/
    # theme-review only now — no candidates, so no outcompete exit).
    holdings = [
        {"symbol": "WEAK", "conviction": 40.0, "market_value": 5_000.0},
        {"symbol": "BIG", "conviction": 80.0, "market_value": 30_000.0},
    ]
    plan = plan_decisions(holdings, 100_000.0, 2)
    assert plan["exits"] == []
    assert plan["trims"] and plan["trims"][0]["symbol"] == "BIG" and plan["trims"][0]["reason"] == "risk_trim"


def test_no_entry_authority_remains():
    """Founding-premise guard: plan_decisions can exit and trim, never enter."""
    import inspect
    sig = inspect.signature(plan_decisions)
    assert "candidates" not in sig.parameters and "evictions" not in sig.parameters
    out = plan_decisions([], 1000.0, 15)
    assert set(out) == {"exits", "trims", "notes"}
