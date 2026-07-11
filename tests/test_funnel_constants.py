"""Phase 3C constants exist and are internally consistent."""
from execution import constants as c


def test_funnel_constants_exist_and_cohere():
    assert c.SLEEVE_A == "A"
    assert c.SLEEVE_A_FRACTION == 0.70
    assert 0 < c.ENTRY_WEIGHT_MIN < c.ENTRY_WEIGHT_MAX < c.RISK_TRIM_CEILING
    assert c.RISK_TRIM_TARGET == c.ENTRY_WEIGHT_MAX
    assert c.SLEEVE_A_TARGET_POSITIONS <= c.SLEEVE_A_MAX_POSITIONS
    assert c.LIGHT_RUNS_PER_WEEK > c.FULL_RUNS_PER_WEEK
    assert c.EXTENSION_ATR_LIMIT > 0 and c.TRAILING_STOP_ATR_MULT > c.EXTENSION_ATR_LIMIT
    assert 0 < c.ADV_POSITION_CAP_PCT < 0.05
    assert 0 < c.VOL_CEILING_SLEEVE_RISK < 0.02
    assert c.FUNNEL_MCAP_FLOOR >= c.THEME_MCAP_FLOOR_USD
    assert abs(sum(c.CONVICTION_WEIGHTS.values()) - 1.0) < 1e-9
    assert abs(sum(c.SCREEN_WEIGHTS.values()) - 1.0) < 1e-9
    assert 0 < c.SMALL_CAP_HAIRCUT_MIN_MULT < 1.0
    assert 0 < c.STALENESS_DECAY_PER_WEEK < 0.1
    assert 0 < c.RETIRED_THEME_EXIT_CONVICTION < 100


def test_funnel_report_types_registered():
    from execution.reporting import REPORT_TYPES
    for t in ("funnel_summary", "entry_order", "entry_filled", "entry_missed",
              "entry_deferred", "exit_stop", "exit_sell_verdict", "exit_outcompeted",
              "theme_review", "risk_trim", "light_run_failure",
              "dca_add", "review_trigger", "thesis_reduce"):
        assert t in REPORT_TYPES
