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
