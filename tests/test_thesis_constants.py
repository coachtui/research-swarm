from execution.constants import (
    ENTRY_LEGAL_STAGES, ENTRY_WEIGHT_MAX, ENTRY_WEIGHT_MIN, ROLE_BANDS,
    THESIS_LEDGER_WEEKS, THESIS_MEMO_MODEL, THESIS_ROLES, THESIS_STAGES,
    THESIS_WEB_SEARCH_MAX_USES,
)


def test_stage_ladder_order_and_entry_legality():
    assert THESIS_STAGES == ("pre_consensus", "catching_on", "crowded", "priced")
    assert ENTRY_LEGAL_STAGES == ("pre_consensus", "catching_on")
    assert set(ENTRY_LEGAL_STAGES) < set(THESIS_STAGES)


def test_role_bands_inside_entry_band_and_ordered():
    assert set(ROLE_BANDS) == set(THESIS_ROLES) == {"anchor", "pure_play", "catalyst"}
    for lo, hi in ROLE_BANDS.values():
        assert ENTRY_WEIGHT_MIN <= lo < hi <= ENTRY_WEIGHT_MAX
    assert ROLE_BANDS["anchor"][1] == ENTRY_WEIGHT_MAX      # anchors top of band
    assert ROLE_BANDS["catalyst"][0] == ENTRY_WEIGHT_MIN    # catalysts bottom


def test_memo_call_settings():
    assert THESIS_MEMO_MODEL == "claude-sonnet-5"
    assert THESIS_WEB_SEARCH_MAX_USES == 15
    assert THESIS_LEDGER_WEEKS == 8
