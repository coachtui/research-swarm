# tests/test_thesis_study.py
"""13F diff + entry-window reconstruction (spec §5.1–5.2). Pure functions."""
from execution.thesis.study import (
    build_study_packet, diff_quarters, normalize_holdings, reconstruct_windows,
)


def _h(issuer, cusip, value, shares, put_call=None, share_type="SH"):
    return {"issuer": issuer, "cusip": cusip, "class": "COM", "value": value,
            "shares": shares, "share_type": share_type, "put_call": put_call}


CURR = [
    _h("BLOOM ENERGY CORP", "093712107", 20_000_000, 800_000),    # increased
    _h("NVIDIA CORP", "67066G104", 11_500_000, 90_000, "Put"),    # new put
    _h("SANDISK CORP", "80004C101", 5_000_000, 100_000),          # held (small drift)
]
PREV = [
    _h("BLOOM ENERGY CORP", "093712107", 15_900_000, 650_000),
    _h("SANDISK CORP", "80004C101", 4_600_000, 100_000),
    _h("LUMENTUM HOLDINGS", "55024U109", 8_700_000, 120_000),     # exited
]


def test_normalize_aggregates_split_lots_by_cusip_and_putcall():
    lots = [_h("BLOOM", "093712107", 100.0, 10.0), _h("BLOOM", "093712107", 50.0, 5.0),
            _h("BLOOM PUT", "093712107", 7.0, 1.0, "Put")]
    agg = normalize_holdings(lots)
    assert agg[("093712107", None)]["value"] == 150.0
    assert agg[("093712107", None)]["shares"] == 15.0
    assert agg[("093712107", "Put")]["value"] == 7.0


def test_diff_classifies_new_exited_increased_held():
    d = diff_quarters(CURR, PREV)
    assert [m["issuer"] for m in d["new"]] == ["NVIDIA CORP"]
    assert d["new"][0]["put_call"] == "Put"
    assert [m["issuer"] for m in d["exited"]] == ["LUMENTUM HOLDINGS"]
    assert [m["issuer"] for m in d["increased"]] == ["BLOOM ENERGY CORP"]
    assert [m["issuer"] for m in d["held"]] == ["SANDISK CORP"]   # +8.7% < 20%
    assert d["book_value"] == 36_500_000
    be = d["increased"][0]
    assert be["prev_shares"] == 650_000 and be["shares"] == 800_000
    assert abs(be["delta_value_pct"] - 0.258) < 0.001
    assert abs(be["weight_pct"] - 54.79) < 0.01


def test_diff_empty_prior_marks_everything_new():
    d = diff_quarters(CURR, [])
    assert len(d["new"]) == 3 and d["exited"] == []


def test_windows_first_appearance_and_implied_price():
    history = [
        {"period": "2026-03-31", "filed": "2026-05-14", "holdings": CURR},
        {"period": "2025-12-31", "filed": "2026-02-12", "holdings": PREV},
    ]
    w = reconstruct_windows(history)
    be = w["093712107:LONG"]
    assert be["first_period"] == "2025-12-31"
    assert [q["period"] for q in be["quarters"]] == ["2025-12-31", "2026-03-31"]
    assert be["quarters"][0]["implied_price"] == round(15_900_000 / 650_000, 2)
    assert w["67066G104:Put"]["first_period"] == "2026-03-31"
    # exited names keep their history (that's the exit window)
    assert w["55024U109:LONG"]["quarters"][-1]["period"] == "2025-12-31"


def test_packet_collects_material_moves_with_windows():
    history = [
        {"period": "2026-03-31", "filed": "2026-05-14", "holdings": CURR},
        {"period": "2025-12-31", "filed": "2026-02-12", "holdings": PREV},
    ]
    p = build_study_packet("Situational Awareness LP", history)
    assert p["fund"] == "Situational Awareness LP"
    assert p["as_of"] == "2026-03-31" and p["prior"] == "2025-12-31"
    issuers = {m["issuer"] for m in p["material_moves"]}
    # new + exited + increased always material; SNDK held but 13.7% ≥ 3% weight
    assert issuers == {"NVIDIA CORP", "LUMENTUM HOLDINGS", "BLOOM ENERGY CORP",
                       "SANDISK CORP"}
    for m in p["material_moves"]:
        assert m["window"] is not None and m["window"]["first_period"]


def test_packet_none_when_fewer_than_two_filings():
    assert build_study_packet("X", [{"period": "2026-03-31", "filed": "f",
                                     "holdings": CURR}]) is None
    assert build_study_packet("X", []) is None
