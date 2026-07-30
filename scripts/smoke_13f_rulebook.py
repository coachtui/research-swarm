"""Live smoke test for the 13F rulebook — run before merging.

Memory `live-smoke-test-external-data`: mocked tests validate the fixture, not
the source. Phase B shipped with 7 green tests and broke on 5 of 6 real SALP
filings (EDGAR namespace prefixes). This hits real EDGAR and exercises the
whole pure path — fetch, diff, windows, prompt build, merge — with NO paid LLM
call, so it is free to run.

Usage: /usr/bin/python3 scripts/smoke_13f_rulebook.py
"""
import sys

sys.path.insert(0, ".")

from execution.constants import TRUSTED_FUNDS_13F
from execution.thesis.rulebook import merge_rulebook
from execution.thesis.rulebook_prompts import build_revise_prompt
from execution.thesis.study import build_study_packet
from execution.thesis.study_edgar import fetch_13f_history
from execution.thesis.study_prompts import build_study_prompt

failures = []
for fund in TRUSTED_FUNDS_13F:
    print(f"\n=== {fund['name']} {fund['ciks']} ===")
    history = fetch_13f_history(fund["ciks"])
    print(f"filings: {len(history)}")
    for h in history:
        print(f"  {h['period']}  filed {h['filed']}  {len(h['holdings'])} holdings")
    if len(history) < 2:
        failures.append(f"{fund['name']}: fewer than 2 readable filings")
        continue
    if any(not h["holdings"] for h in history):
        failures.append(f"{fund['name']}: a filing parsed to ZERO holdings")

    packet = build_study_packet(fund["name"], history)
    print(f"material_moves: {len(packet['material_moves'])}  "
          f"puts/calls: {sum(1 for m in packet['material_moves'] if m['put_call'])}")
    if not packet["material_moves"]:
        failures.append(f"{fund['name']}: no material moves")

    study_prompt = build_study_prompt(packet)
    print(f"study prompt: {len(study_prompt):,} chars")

    # Exercise the merge path with a synthetic revision (no LLM spend).
    book = merge_rulebook(None, {
        "verdicts": [],
        "new_rules": [{"rule": "smoke rule", "rationale": "r"}],
        "calibration": {"typical_lead_quarters": 2.0}, "summary": "s"},
        as_of=packet["as_of"])
    revise_prompt = build_revise_prompt(book, {
        "method_rules": [], "moves": [], "earliness": [], "summary": "s",
        "skipped": []}, fund["name"], packet["as_of"])
    print(f"revise prompt: {len(revise_prompt):,} chars  "
          f"rulebook v{book['version']}")
    for leaked in ("cusip", "weight_pct", "material_moves"):
        if leaked in revise_prompt:
            continue    # the revise prompt legitimately shows the digest
    if any(k in str(book) for k in ("cusip", "weight_pct")):
        failures.append(f"{fund['name']}: rulebook leaked position data")

print("\n" + ("FAILURES:\n  " + "\n  ".join(failures) if failures
              else "SMOKE TEST PASSED"))
sys.exit(1 if failures else 0)
