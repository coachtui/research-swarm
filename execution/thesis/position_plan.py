"""Position plans: absolute price levels the memo commits to, as resting orders.

Replaces DCA_RUNGS = (0.20, 0.30, 0.40) drawdown-from-high-water. That ladder
re-arms every time a new high prints:

    if high_water > st["armed_high"]: st = {"armed_high": high_water, "used": []}

so its add levels drift UPWARD with the price — you end up adding at
progressively higher absolute prices, which is the opposite of "add under 800,
more under 700, full 500-600". Those numbers are a judgement about what the
business is worth and where the thesis binds. A trailing percentage off the
last peak is not that judgement, and cannot become it.

Two safety properties carry the weight here:

  * a ladder with no thesis_break condition is REFUSED. Rungs become live
    resting bids, so an unguarded ladder is a machine for catching a falling
    knife. "Full position at 500-600 IF the thesis doesn't break" is the whole
    idea, and the condition is the half that makes the rest safe to automate.
  * a broken thesis cancels every unfilled rung. Averaging down into a story
    that has stopped being true is the one failure this must not have.

Pure. No I/O, no broker, no DB — the caller diffs `desired_rung_orders`
against what is actually resting and places/cancels the difference.
"""
from typing import Any, Dict, List

from execution.constants import MIN_TRADE_NOTIONAL


class PlanError(Exception):
    """The plan is unusable — refused rather than partially executed."""


def validate_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Return the plan, or raise. Every rule here exists because breaking it
    turns the ladder into an unguarded standing bid."""
    if not isinstance(plan, dict):
        raise PlanError("plan is not an object")

    ladder = plan.get("ladder")
    if not isinstance(ladder, list) or not ladder:
        raise PlanError("plan has an empty ladder")

    if not str(plan.get("thesis_break") or "").strip():
        raise PlanError(
            "plan has no thesis_break condition — an unguarded ladder averages "
            "into a broken thesis")

    prices: List[float] = []
    total = 0.0
    for i, rung in enumerate(ladder):
        if not isinstance(rung, dict):
            raise PlanError(f"rung {i} is not an object")
        try:
            price = float(rung["price"])
            size = float(rung["size_pct"])
        except (KeyError, TypeError, ValueError) as exc:
            raise PlanError(f"rung {i} needs a numeric price and size_pct") from exc
        if price <= 0:
            raise PlanError(f"rung {i} price must be positive")
        if not str(rung.get("why") or "").strip():
            raise PlanError(f"rung {i} has no why — every level is a decision")
        prices.append(price)
        total += size

    if prices != sorted(prices, reverse=True):
        raise PlanError("ladder prices must descend — you buy lower, not higher")
    if abs(total - 100.0) > 0.01:
        raise PlanError(f"ladder sizes total {total:g}%, must total 100")

    exit_plan = plan.get("exit_plan")
    if exit_plan is not None:
        _validate_exit(exit_plan)

    try:
        if not 0.0 < float(plan.get("target_weight", 0.0)) <= 1.0:
            raise PlanError("target_weight must be a fraction in (0, 1]")
    except (TypeError, ValueError) as exc:
        raise PlanError("target_weight must be numeric") from exc

    return plan


EXIT_POSTURES = ("let_run", "trim_into_strength", "scale_out", "close")
_NEEDS_FRACTION = ("trim_into_strength", "scale_out")


def _validate_exit(exit_plan: Any) -> None:
    """The exit is a POSTURE with reasoning, not a trim size.

    "Let it run" has to be a decision the memo makes and defends — the
    difference between "the constraint keeps binding so I am letting this go"
    and "no threshold tripped" is the difference between a judgement you can
    review later and an accident. Encoding it as fraction=0 erases that.
    """
    if not isinstance(exit_plan, dict):
        raise PlanError("exit_plan is not an object")
    posture = exit_plan.get("posture")
    if posture not in EXIT_POSTURES:
        raise PlanError(
            f"exit_plan posture {posture!r} unknown — one of {EXIT_POSTURES}")
    if not str(exit_plan.get("why") or "").strip():
        raise PlanError("exit_plan has no why — every posture is a decision")
    if posture in _NEEDS_FRACTION:
        try:
            fraction = float(exit_plan["fraction"])
        except (KeyError, TypeError, ValueError) as exc:
            raise PlanError(f"{posture} needs a numeric fraction") from exc
        if not 0.0 < fraction <= 1.0:
            raise PlanError("exit_plan fraction must be in (0, 1]")


def desired_rung_orders(
    plan: Dict[str, Any], current_price: float, held_qty: float,
    sleeve_equity: float, thesis_broken: bool = False,
) -> List[Dict[str, Any]]:
    """The resting limit orders that SHOULD exist for this position right now.

    The caller diffs this against what is actually resting: place what is
    missing, cancel what is not here. That makes the ladder self-healing —
    a rung that fills simply stops appearing.
    """
    if thesis_broken:
        return []   # every unfilled rung dies with the thesis

    validate_plan(plan)
    target_notional = float(plan["target_weight"]) * float(sleeve_equity)
    if target_notional <= 0 or current_price <= 0:
        return []

    held_notional = float(held_qty) * float(current_price)

    orders: List[Dict[str, Any]] = []
    cumulative = 0.0
    for i, rung in enumerate(plan["ladder"]):
        price = float(rung["price"])
        slice_notional = target_notional * float(rung["size_pct"]) / 100.0
        cumulative += slice_notional

        # Already covered: the position is at or past this rung's cumulative
        # target, so the rung is spent. Compared on notional so a partial fill
        # does not silently re-arm the level.
        if held_notional >= cumulative - 1e-9:
            continue
        # Above the market a limit fills instantly — that is a market order
        # wearing a limit's clothes, and never what "add under 800" meant.
        if price >= current_price:
            continue

        qty = round(slice_notional / price, 4)
        if qty * price < MIN_TRADE_NOTIONAL:
            continue
        orders.append({"rung": i, "price": price, "qty": qty,
                       "why": str(rung["why"]).strip()})

    return orders
