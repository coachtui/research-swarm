"""Quarterly 13F study: diff, entry-window reconstruction, digest persist.

CURRICULUM, never copy-trading (spec §5): by filing day the positions are
~7 weeks stale, so the filing is an answer key for a test the market
already gave. The deliverable is METHOD RULES. Tickers seen here carry
zero order authority — nothing in this module or its callers reaches the
broker, sizing, or the planner (guard-tested).
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

from execution.constants import STUDY_MATERIAL_DELTA, STUDY_TOP_WEIGHT_PCT
from execution.reporting import write_report

logger = logging.getLogger(__name__)

SOURCE = "thirteenf_study"

_Key = Tuple[Optional[str], Optional[str]]  # (cusip, put_call)


def _key(row: Dict[str, Any]) -> _Key:
    return (row.get("cusip"), row.get("put_call"))


def normalize_holdings(holdings: List[Dict[str, Any]]) -> Dict[_Key, Dict[str, Any]]:
    """Aggregate split lots (managers report multiple rows per issuer) by
    (cusip, put_call) — a put and a long in the same name stay distinct."""
    out: Dict[_Key, Dict[str, Any]] = {}
    for r in holdings:
        k = _key(r)
        if k in out:
            out[k]["value"] += r.get("value") or 0.0
            out[k]["shares"] = (out[k].get("shares") or 0.0) + (r.get("shares") or 0.0)
        else:
            out[k] = dict(r)
    return out


def diff_quarters(curr: List[Dict[str, Any]],
                  prev: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Position deltas between two info tables, puts/calls included. A
    put-to-long flip shows as one exited + one new row — the study prompt
    is told to read paired moves in the same cusip together."""
    a, b = normalize_holdings(curr), normalize_holdings(prev)
    book = sum(v["value"] or 0.0 for v in a.values()) or 1.0
    prev_book = sum(v["value"] or 0.0 for v in b.values()) or 1.0

    def _move(k: _Key, kind: str) -> Dict[str, Any]:
        cur, old = a.get(k), b.get(k)
        row = cur or old or {}
        cur_v = (cur or {}).get("value") or 0.0
        old_v = (old or {}).get("value") or 0.0
        return {"issuer": row.get("issuer"), "cusip": k[0], "put_call": k[1],
                "kind": kind, "value": cur_v, "prev_value": old_v,
                "shares": (cur or {}).get("shares") or 0.0,
                "prev_shares": (old or {}).get("shares") or 0.0,
                "weight_pct": round(100.0 * cur_v / book, 2),
                "prev_weight_pct": round(100.0 * old_v / prev_book, 2),
                "delta_value_pct": (round((cur_v - old_v) / old_v, 3)
                                    if old_v else None)}

    out: Dict[str, Any] = {"new": [], "exited": [], "increased": [],
                           "decreased": [], "held": []}
    for k in a:
        if k not in b:
            out["new"].append(_move(k, "new"))
            continue
        old_v = b[k].get("value") or 0.0
        delta = ((a[k].get("value") or 0.0) - old_v) / old_v if old_v else 0.0
        kind = ("increased" if delta >= STUDY_MATERIAL_DELTA
                else "decreased" if delta <= -STUDY_MATERIAL_DELTA else "held")
        out[kind].append(_move(k, kind))
    for k in b:
        if k not in a:
            out["exited"].append(_move(k, "exited"))
    out["book_value"] = book
    return out


def reconstruct_windows(history: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Per position across the filing history (newest first): the quarter it
    first appears, per-quarter shares/value, and the implied quarter-end
    price (value/shares — 13F values are quarter-end marks, so this
    brackets WHERE they acted, not their exact fill)."""
    out: Dict[str, Dict[str, Any]] = {}
    for snap in reversed(history):                      # oldest → newest
        for k, row in normalize_holdings(snap.get("holdings") or []).items():
            key = f"{k[0]}:{k[1] or 'LONG'}"
            entry = out.setdefault(key, {
                "issuer": row.get("issuer"), "cusip": k[0], "put_call": k[1],
                "first_period": snap["period"], "quarters": []})
            shares = row.get("shares") or 0.0
            implied = (row["value"] / shares
                       if shares and row.get("share_type") == "SH" else None)
            entry["quarters"].append({
                "period": snap["period"], "value": row.get("value"),
                "shares": shares,
                "implied_price": round(implied, 2) if implied else None})
    return out


def build_study_packet(fund_name: str,
                       history: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The study prompt's raw material for one fund; None when fewer than
    two filings exist (nothing to diff)."""
    if len(history) < 2:
        return None
    diff = diff_quarters(history[0]["holdings"], history[1]["holdings"])
    windows = reconstruct_windows(history)
    material = (diff["new"] + diff["exited"] + diff["increased"] + diff["decreased"]
                + [m for m in diff["held"] if m["weight_pct"] >= STUDY_TOP_WEIGHT_PCT])
    for m in material:
        m["window"] = windows.get(f"{m['cusip']}:{m['put_call'] or 'LONG'}")
    return {"fund": fund_name, "as_of": history[0]["period"],
            "filed": history[0]["filed"], "prior": history[1]["period"],
            "quarters_available": [h["period"] for h in history],
            "book_value": diff["book_value"], "material_moves": material}


def reason_study(packet: Dict[str, Any], llm_call=None) -> str:
    """The PAID call — the cron runs it inside its own memoized step."""
    from execution.constants import (  # noqa: PLC0415
        STUDY_MAX_TOKENS, STUDY_MODEL, STUDY_WEB_SEARCH_MAX_USES,
    )
    from execution.themes.discovery import _call_llm  # noqa: PLC0415
    from execution.thesis.study_prompts import build_study_prompt  # noqa: PLC0415

    call = llm_call or _call_llm
    return call(STUDY_MODEL, build_study_prompt(packet), use_web_search=True,
                max_uses=STUDY_WEB_SEARCH_MAX_USES, max_tokens=STUDY_MAX_TOKENS)


async def persist_digest(db, week: str, fund_name: str, digest: Dict[str, Any],
                         raw: str, packet: Dict[str, Any]) -> None:
    """Ledger row (kind=study_digest — the slot every weekly memo reads) +
    EngineReport journal. Both writers swallow their own failures."""
    from execution.thesis.ledger import append_evidence  # noqa: PLC0415

    body = {"fund": fund_name, "as_of": packet["as_of"], "filed": packet["filed"],
            "method_rules": digest["method_rules"], "moves": digest["moves"],
            "summary": digest["summary"], "skipped": digest["skipped"],
            # The raw diff stays here for the owner's audit (row + journal);
            # load_study_digest strips it before any prompt sees it.
            "material_moves": packet["material_moves"]}
    await append_evidence(db, "study_digest", body, week=week)
    await write_report(
        "study_digest", "info", SOURCE,
        f"13F study: {fund_name} {packet['as_of']} — "
        f"{len(digest['method_rules'])} method rules",
        {"raw": raw, **body}, db=db)
