"""Build, store, and read MarketOutlook records.

build_outlook_record is pure (unit-testable, no prisma). store/get are the
only DB touchpoints and wrap JSON columns in prisma.Json at the edge.
"""
from datetime import datetime
from typing import Any, Dict, Optional

from execution.indicators.regime import apply_strategist_override


def build_outlook_record(
    run_date: datetime,
    indicators: Dict[str, Any],
    strategist: Dict[str, Any],
) -> Dict[str, Any]:
    mechanical = indicators["regime_mechanical"]
    final_regime, overridden = apply_strategist_override(
        mechanical, strategist["regime_proposal"]
    )
    return {
        "runDate": run_date,
        "regime": final_regime,
        "regimeMechanical": mechanical,
        "strategistOverride": overridden,
        "strategistStatus": strategist["status"],
        "conviction": strategist["conviction"],
        "sectorRankings": indicators["rankings"],
        "rotationFlags": indicators["rotations"],
        "breadth": indicators["breadth"],
        "industryRankings": indicators.get("industry"),
        "sizeStyle": indicators.get("size_style"),
        "themeRankings": indicators.get("themes"),
        # The falsifier rides the reasoning prose: MarketOutlook has no column
        # for it and migrations here are hand-written SQL, so folding it in is
        # what carries it through to the memo's macro block.
        "reasoning": _with_falsifier(strategist),
    }


def _with_falsifier(strategist: Dict[str, Any]) -> str:
    reasoning = strategist["reasoning"]
    falsifier = strategist.get("falsifier")
    if not falsifier:
        return reasoning
    return f"{reasoning}\n\nWhat would falsify this read: {falsifier}"


async def store_outlook(db, record: Dict[str, Any]) -> Any:
    from prisma import Json  # runtime-only dependency

    data = dict(record)
    for field in ("sectorRankings", "rotationFlags", "breadth",
                  "industryRankings", "sizeStyle", "themeRankings"):
        if data.get(field) is None:
            data.pop(field, None)
        else:
            data[field] = Json(data[field])
    return await db.marketoutlook.create(data=data)


async def get_latest_outlook(db) -> Optional[Any]:
    return await db.marketoutlook.find_first(order={"runDate": "desc"})
