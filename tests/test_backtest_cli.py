from scripts.backtest_sleeve_a import build_parser


def test_parser_subcommands_and_defaults():
    p = build_parser()
    ns = p.parse_args(["run"])
    assert ns.command == "run"
    assert ns.start == "2015-01-01" and ns.end == "2026-06-30"
    assert ns.cash == 100_000.0
    ns = p.parse_args(["sweep", "--start", "2018-01-01", "--cash", "50000"])
    assert (ns.command, ns.start, ns.cash) == ("sweep", "2018-01-01", 50_000.0)
    assert build_parser().parse_args(["fetch"]).command == "fetch"


def test_parser_accepts_experiments_subcommand():
    ns = build_parser().parse_args(["experiments"])
    assert ns.command == "experiments"
    assert ns.start == "2015-01-01"


def test_check_base_integrity(tmp_path, capsys):
    import json

    import scripts.backtest_sleeve_a as cli
    ref = tmp_path / "metrics.json"
    ref.write_text(json.dumps(
        {"base": {"cagr": 0.12, "sharpe": 0.95, "max_drawdown": -0.166}}))
    ok = cli._check_base_integrity(
        {"cagr": 0.12, "sharpe": 0.95, "max_drawdown": -0.166}, reference=ref)
    assert ok is True
    ok = cli._check_base_integrity(
        {"cagr": 0.12, "sharpe": 0.90, "max_drawdown": -0.166}, reference=ref)
    assert ok is False
    assert "MISMATCH" in capsys.readouterr().out
    assert cli._check_base_integrity({"cagr": 0.1, "sharpe": 1.0,
                                      "max_drawdown": -0.1},
                                     reference=tmp_path / "absent.json") is None
