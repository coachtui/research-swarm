"""Prompts for theme discovery — Aschenbrenner's Situational Awareness method.

The monthly prompt is a reasoning engine, not a lookup: it walks the AI
demand chain, finds binding constraints, scores the consensus gap, and only
then proposes themes/constituents. Caps and floors are stated so the model
pre-filters instead of burning validation calls.
"""
import json
from typing import Any, Dict, List

from execution.constants import (
    MAX_ACTIVE_THEMES,
    MAX_THEME_CONSTITUENTS,
    MIN_THEME_CONSTITUENTS,
    THEME_ADV_FLOOR_USD,
    THEME_MCAP_FLOOR_USD,
)

_SA_METHOD = """## Method (follow it in order — this is how you reason)

1. TRUST TRENDLINES IN LOG SPACE. Extrapolate compute/capex/power/revenue
   exponentials mechanically from multi-year data. The burden of proof is on
   "the trend breaks", not "the trend continues".
2. WALK THE DERIVATIVE DEMAND CHAIN. AI revenue -> capex -> accelerators ->
   (logic fab, HBM/memory, advanced packaging, networking/optics) ->
   datacenters -> power -> gas/turbines/grid/transformers/land. Map the
   chain AS IT IS TODAY — links appear and disappear as buildout progresses.
3. FIND THE BINDING CONSTRAINT. For each link ask: how long is the lead
   time, how much spare capacity exists? Alpha concentrates in the link with
   the longest lead time and the least spare capacity.
4. SCORE THE CONSENSUS GAP. Compare trend-implied demand with what sell-side
   and incumbent forecasts assume. A theme that is already priced in is not
   a theme. Use web search to check CURRENT forecasts, capex announcements,
   power contracts, and fab/packaging expansion news — your training data is
   stale by definition.
5. WATCH PHYSICAL COMMITMENTS. Power contracts, transformer scrambles,
   greenfield fab/packaging plants, giant GPU orders, rig counts — physical
   commitments lead reported financials by 1-3 years. Name the leading
   indicators to watch for every theme you propose.
"""

_REVEALED_BEHAVIOR = """## Revealed behavior of the best thematic investors (13F study, 2026-07-10)
- Buy the BINDING CONSTRAINT, not the beneficiary. Consensus buys who
  sells the theme; the re-rating lives in what the theme cannot proceed
  without (power -> cooling -> energized shells -> memory/storage ->
  optics -> fiber -> bridge power).
- The constraint MIGRATES. Your primary deliverable each month is FORWARD:
  answer "what binds NEXT once today's constraints are priced?" A
  constraint that has become a consensus headline is priced — rotate the
  reasoning to its successor.
- Speed matters: time-to-solve is a selection criterion. Short-time-frame
  demand accrues to whoever can deliver NOW (fuel cells, gensets, converted
  capacity) over elegant solutions that take a decade.
- Express every theme across the cap spectrum and by ROLE — state the
  role in each constituent's exposure sentence: anchor
  (contracted/profitable floor with thesis optionality), pure-play
  (asymmetric constraint exposure), or catalyst (identifiable pending
  repricing event). For pure-plays and catalysts also state
  time-to-survive: whether the balance sheet reaches the catalyst.
- Name the theme's second-order losers in metadata (who is disrupted or
  squeezed if the thesis plays out).

In addition to "themes", return a top-level "next_constraints" array with
1-3 FORWARD hypotheses — constraints not yet investable-obvious:
  {"hypothesis": "<one sentence>", "candidates": ["TICK", ...],
   "leading_indicators": ["<2-4 observable signals>", ...],
   "falsification": "<what kills the hypothesis>"}
A hypothesis graduates to a proposed theme in a LATER month only when its
leading indicators confirm."""


def _themes_block(themes: List[Dict[str, Any]]) -> str:
    if not themes:
        return "none yet — the seed themes below have no constituents until you populate them"
    lines = []
    for t in themes:
        cons = ", ".join(f"{c['ticker']} ({c['confidence']:.2f})" for c in t.get("constituents", []))
        lines.append(f"- {t['slug']} [{t.get('origin', 'engine')}] conf={t['confidence']:.2f}: "
                     f"{t['thesis']} | constituents: {cons or 'NONE'}")
    return "\n".join(lines)


def build_monthly_prompt(context: Dict[str, Any]) -> str:
    research = context.get("research") or {}
    rankings = context.get("latest_rankings")
    retired = context.get("retired_themes") or []
    return f"""You are the theme-discovery engine of a long-horizon systematic fund.
Your job: maintain a list of investable THEMES — links in the AI buildout
demand chain where a binding constraint creates a multi-year re-rating — and
the public-company CONSTITUENTS with material exposure to each.

{_SA_METHOD}

{_REVEALED_BEHAVIOR}

## Current theme list (you maintain this — seeds compete equally)
{_themes_block(context.get("active_themes") or [])}

## Retired themes (reactivate only with new evidence)
{json.dumps(retired) if retired else "none"}

## Latest theme rankings (relative strength vs SPY, if available)
{json.dumps(rankings) if rankings else "none yet"}

## Internal research context (owner's watchlist + supply-chain names seen in research)
- Watchlist tickers: {", ".join(research.get("watchlist") or []) or "none"}
- Supply-chain names from recent reports: {", ".join(research.get("supply_chain") or []) or "none"}
- News-entity names from recent reports: {", ".join(research.get("news_entities") or []) or "none"}

## Hard rules
- At most {MAX_ACTIVE_THEMES} active themes. A new theme must be MORE
  compelling than the weakest incumbent, which you should then retire.
- A theme needs at least {MIN_THEME_CONSTITUENTS} listed, liquid US-traded
  constituents (ADV >= ${THEME_ADV_FLOOR_USD:,.0f}/day, market cap >=
  ${THEME_MCAP_FLOOR_USD:,.0f}) or it cannot activate. Propose up to
  {MAX_THEME_CONSTITUENTS} per theme, strongest exposure first.
- Every constituent must have REAL, MATERIAL exposure stated in one
  falsifiable sentence with evidence. No ETFs, no foreign-only listings.
  Small caps with pure exposure beat megacaps with diluted exposure —
  surfacing what cap-weighted ETFs hide is the point.
- Every theme needs: which demand-chain link it is, why the constraint sits
  there, the consensus gap, and 2-4 leading indicators to watch (put these
  in metadata).
- "keep" themes: restate the full constituent list you want (it replaces the
  current one). "retire": say why (priced in, constraint resolved, thesis
  broken).

Respond with ONLY a JSON object, no other text:
{{
  "themes": [
    {{
      "slug": "<kebab-case>",
      "name": "<display name>",
      "action": "add" | "keep" | "retire",
      "thesis": "<demand-chain link + binding constraint + consensus gap, 2-4 sentences>",
      "confidence": <float 0.0-1.0>,
      "metadata": {{
        "binding_constraint": "<one line>",
        "consensus_gap_notes": "<one line>",
        "leading_indicators": ["<indicator>", ...]
      }},
      "constituents": [
        {{"ticker": "<SYMBOL>", "exposure": "<one falsifiable sentence>", "confidence": <float>}}
      ]
    }}
  ],
  "next_constraints": [
    {{"hypothesis": "<one sentence>", "candidates": ["<SYMBOL>", ...],
      "leading_indicators": ["<2-4 observable signals>", ...],
      "falsification": "<what kills the hypothesis>"}}
  ]
}}"""


def build_delta_prompt(context: Dict[str, Any]) -> str:
    return f"""You maintain the constituent lists of a systematic fund's theme baskets.
This is the WEEKLY DELTA pass: propose constituent additions/removals only.
Do NOT propose new themes and do NOT touch theme-level fields.

## Active themes and current constituents
{_themes_block(context.get("active_themes") or [])}

## Rules
- Suggest a change only when you have a concrete reason (new listing, lost
  exposure, acquisition, delisting, materially better pure-play).
- VERIFY EVERY SYMBOL YOU ADD IS STILL TRADING TODAY. Search before you
  propose. Companies get acquired, merge, rename, split, and liquidate — a
  ticker you remember may not exist anymore. Confirm the symbol currently
  trades on a US exchange and still maps to the company you mean. If you
  cannot confirm it, do not propose it.
- Additions need REAL, MATERIAL exposure stated in one falsifiable sentence.
  US-listed, liquid names only (ADV >= ${THEME_ADV_FLOOR_USD:,.0f}/day,
  market cap >= ${THEME_MCAP_FLOOR_USD:,.0f}). Max {MAX_THEME_CONSTITUENTS}
  constituents per theme.
- No changes is a perfectly good answer: return an empty themes list.

Respond with ONLY a JSON object, no other text:
{{
  "themes": [
    {{
      "slug": "<existing theme slug>",
      "add": [{{"ticker": "<SYMBOL>", "exposure": "<sentence>", "confidence": <float>}}],
      "remove": [{{"ticker": "<SYMBOL>", "reason": "<sentence>", "confidence": <float>}}]
    }}
  ]
}}"""
