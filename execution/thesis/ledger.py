"""Append-only thesis evidence ledger (spec §6).

The memo's memory: prior memos, hypothesis observations, and the latest 13F
study digest. Reads degrade to empty (memo runs stateless with a journaled
warning — spec §7); writes swallow failures (a broken ledger must never
block the pass — the journal row still records the memo verbatim).
"""
import logging
from typing import Any, Dict, List, Optional

from execution.constants import THESIS_LEDGER_WEEKS

logger = logging.getLogger(__name__)


def _to_dict(r: Any) -> Dict[str, Any]:
    return {"kind": r.kind, "themeSlug": r.themeSlug,
            "hypothesisKey": r.hypothesisKey, "week": r.week,
            "stage": r.stage, "body": r.body}


async def append_evidence(
    db, kind: str, body: Dict[str, Any], *, theme_slug: Optional[str] = None,
    hypothesis_key: Optional[str] = None, week: str, stage: Optional[str] = None,
) -> None:
    from prisma import Json  # noqa: PLC0415 — runtime-only dependency

    try:
        await db.thesisevidence.create(data={
            "kind": kind, "themeSlug": theme_slug, "hypothesisKey": hypothesis_key,
            "week": week, "stage": stage, "body": Json(body)})
    except Exception:  # noqa: BLE001
        logger.exception("thesis ledger: append failed (%s/%s)", kind, theme_slug)


async def load_study_digest(db, take: int = 8) -> List[Dict[str, Any]]:
    """Newest study digest per trusted fund, via a dedicated query. The
    bounded newest-first scan in load_ledger_context ages a QUARTERLY
    digest out of its take window within weeks of weekly rows — this
    lookup never does. Degrades to []."""
    out: List[Dict[str, Any]] = []
    seen: set = set()
    try:
        rows = await db.thesisevidence.find_many(
            where={"kind": "study_digest"}, order={"createdAt": "desc"}, take=take)
        for r in rows:
            body = r.body or {}
            fund = body.get("fund") if isinstance(body, dict) else None
            if fund in seen:
                continue
            seen.add(fund)
            # The stored row keeps material_moves (raw diff) for the owner's
            # audit; the prompt-facing copy must not hand the model the
            # fund's book — curriculum, never copy-trading (spec §5).
            out.append({k: v for k, v in body.items() if k != "material_moves"})
    except Exception:  # noqa: BLE001
        logger.exception("thesis ledger: study digest load failed")
    return out


async def load_ledger_context(
    db, active_slugs: List[str], weeks: int = THESIS_LEDGER_WEEKS,
) -> Dict[str, Any]:
    by_theme: Dict[str, List[Dict[str, Any]]] = {s: [] for s in active_slugs}
    hypotheses: List[Dict[str, Any]] = []
    try:
        # Bounded fetch, newest first; weeks × (themes + hypotheses) rows is
        # small. prisma-client-py has no Json path filters — Python match.
        rows = await db.thesisevidence.find_many(
            order={"createdAt": "desc"}, take=weeks * (len(active_slugs) + 10))
        for r in rows:
            d = _to_dict(r)
            if d["kind"] == "weekly_memo" and d["themeSlug"] in by_theme:
                if len(by_theme[d["themeSlug"]]) < weeks:
                    by_theme[d["themeSlug"]].append(d)
            elif d["kind"] == "hypothesis":
                hypotheses.append(d)
    except Exception:  # noqa: BLE001
        logger.exception("thesis ledger: load failed — memo runs stateless")
    return {"by_theme": by_theme, "hypotheses": hypotheses,
            # Quarterly rows need their own query — the scan window above
            # ages them out within weeks (Phase B fix).
            "study_digest": await load_study_digest(db)}
