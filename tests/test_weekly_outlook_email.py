"""Tests for the pure email helper in inngest_app/functions/weekly_outlook.py."""
from datetime import datetime, timezone

from inngest_app.functions.weekly_outlook import build_outlook_email_html

RECORD = {
    "runDate": datetime(2026, 7, 12, tzinfo=timezone.utc),
    "regime": "risk_on",
    "regimeMechanical": "neutral",
    "strategistOverride": True,
    "strategistStatus": "ok",
    "conviction": 0.65,
    "sectorRankings": [
        {"etf": "XLE", "sector": "Energy", "rank_1m": 1, "rank_3m": 2,
         "rank_change": 1, "score": 0.024, "rs_1m": 0.03, "rs_3m": 0.02,
         "rs_6m": 0.01, "rank_6m": 3},
    ],
    "rotationFlags": [{"etf": "XLK", "sector": "Technology",
                       "direction": "out_of", "rank_change": -5}],
    "breadth": {"pct_above_200dma": 63.6, "equal_weight_trend_3m": 0.8},
    "reasoning": "Breadth improving and energy leadership broadening.",
}


def test_email_contains_regime_and_top_sector():
    html = build_outlook_email_html(RECORD)
    assert "RISK ON" in html.upper().replace("_", " ")
    assert "Energy" in html and "XLE" in html
    assert "Breadth improving" in html


def test_email_shows_override_and_rotations():
    html = build_outlook_email_html(RECORD)
    assert "neutral" in html.lower()          # mechanical shown alongside final
    assert "Technology" in html               # rotation flag rendered


def test_email_handles_fallback_status():
    record = {**RECORD, "strategistStatus": "fallback", "conviction": None,
              "strategistOverride": False, "regime": "neutral"}
    html = build_outlook_email_html(record)
    assert "fallback" in html.lower()
