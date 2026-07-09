"""Prompt construction for the weekly macro strategist."""
from typing import Any, Dict

STRATEGIST_SYSTEM_ROLE = (
    "You are a disciplined macro strategist for a long-horizon systematic fund. "
    "You synthesize sector rotation, breadth, and volatility indicators into a "
    "weekly market outlook. You are conservative: you only disagree with the "
    "mechanical regime when the evidence is clear."
)


def _rankings_table(rankings) -> str:
    lines = ["etf | sector | rs_1m | rs_3m | rs_6m | rank_1m | rank_3m | rank_change | score"]
    for r in rankings:
        lines.append(
            f"{r['etf']} | {r['sector']} | {r['rs_1m']:+.4f} | {r['rs_3m']:+.4f} | "
            f"{r['rs_6m']:+.4f} | {r['rank_1m']} | {r['rank_3m']} | "
            f"{r['rank_change']:+d} | {r['score']:+.4f}"
        )
    return "\n".join(lines)


def build_strategist_prompt(payload: Dict[str, Any]) -> str:
    rotations = payload["rotations"]
    rotation_lines = "\n".join(
        f"- {f['sector']} ({f['etf']}): rotation {f['direction']} "
        f"(rank change {f['rank_change']:+d})"
        for f in rotations
    ) or "- none detected"

    headlines = payload.get("macro_headlines") or []
    headline_lines = "\n".join(f"- {h}" for h in headlines) or "- No macro headlines available."

    breadth = payload["breadth"]
    inputs = payload["regime_inputs"]

    return f"""{STRATEGIST_SYSTEM_ROLE}

## Sector relative strength vs SPY (rank 1 = strongest; positive rank_change = improving recently)
{_rankings_table(payload["rankings"])}

## Rotation flags (1-month rank vs 3-month rank moved >= 3 places)
{rotation_lines}

## Breadth
- Percent of sector ETFs above their 200-day MA: {breadth.get("pct_above_200dma")}
- Equal-weight vs cap-weight 3-month trend (RSP/SPY): {breadth.get("equal_weight_trend_3m")}%

## Mechanical regime call
- Regime: {payload["regime_mechanical"]}
- Inputs: SPY above 200dma = {inputs.get("spy_above_200dma")}, VIX = {inputs.get("vix_last")}, breadth = {inputs.get("pct_above_200dma")}%

## Macro headlines this week
{headline_lines}

## Your task
Write this week's market outlook. Rules:
1. You may propose a regime at most ONE NOTCH away from the mechanical call
   (risk_off <-> neutral <-> risk_on). Proposals further away will be clamped.
2. Focus on where money is rotating INTO early — rank_change is the early signal.
3. Be specific and falsifiable in your reasoning (cite the numbers above).

Respond with ONLY a JSON object, no other text:
{{
  "regime_proposal": "risk_on" | "neutral" | "risk_off",
  "conviction": <float 0.0-1.0>,
  "sector_comments": {{"<ETF>": "<one-sentence view>", ...}},
  "rotation_calls": ["<one sentence per rotation you believe is real>"],
  "reasoning": "<4-8 sentences citing the indicator values>"
}}"""
