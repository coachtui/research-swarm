# tests/test_thesis_study_edgar.py
"""EDGAR 13F fetch/parse for the quarterly study pass (spec §5)."""
import json
from unittest.mock import MagicMock, patch

from execution.thesis.study_edgar import (
    fetch_13f_history, fetch_info_table_xml, list_13f_filings, parse_info_table,
)

SUBMISSIONS = {
    "filings": {"recent": {
        "form": ["13F-HR", "8-K", "13F-HR/A", "13F-HR"],
        "accessionNumber": ["0002045724-26-000004", "0002045724-26-000003",
                            "0002045724-26-000002", "0002045724-25-000009"],
        "filingDate": ["2026-05-14", "2026-04-01", "2026-02-20", "2026-02-12"],
        "reportDate": ["2026-03-31", "2026-03-30", "2025-12-31", "2025-12-31"],
    }}}

INFO_TABLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
  <infoTable>
    <nameOfIssuer>BLOOM ENERGY CORP</nameOfIssuer>
    <titleOfClass>CL A COM</titleOfClass>
    <cusip>093712107</cusip>
    <value>15900000</value>
    <shrsOrPrnAmt><sshPrnamt>650000</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt>
  </infoTable>
  <infoTable>
    <nameOfIssuer>NVIDIA CORP</nameOfIssuer>
    <titleOfClass>COM</titleOfClass>
    <cusip>67066G104</cusip>
    <value>11500000</value>
    <shrsOrPrnAmt><sshPrnamt>90000</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt>
    <putCall>Put</putCall>
  </infoTable>
  <infoTable>
    <nameOfIssuer>BROKEN ROW</nameOfIssuer>
    <titleOfClass>COM</titleOfClass>
    <value>1</value>
  </infoTable>
</informationTable>"""


def _resp(payload, is_json=True):
    r = MagicMock()
    r.raise_for_status = MagicMock()
    if is_json:
        r.json.return_value = payload
    else:
        r.text = payload
    return r


def test_list_13f_filings_filters_forms_and_orders_newest_first():
    with patch("execution.thesis.study_edgar.requests.get",
               return_value=_resp(SUBMISSIONS)) as get:
        out = list_13f_filings("0002045724", limit=8)
    assert [f["form"] for f in out] == ["13F-HR", "13F-HR/A", "13F-HR"]
    assert out[0]["period"] == "2026-03-31" and out[0]["filed"] == "2026-05-14"
    # SEC requires a padded-CIK URL and an identifying User-Agent
    url = get.call_args.args[0]
    assert "CIK0002045724.json" in url
    assert "@" in get.call_args.kwargs["headers"]["User-Agent"]


def test_list_13f_filings_respects_limit():
    with patch("execution.thesis.study_edgar.requests.get",
               return_value=_resp(SUBMISSIONS)):
        assert len(list_13f_filings("0002045724", limit=2)) == 2


def test_parse_info_table_reads_rows_puts_and_skips_broken():
    rows = parse_info_table(INFO_TABLE_XML)
    assert len(rows) == 2                      # BROKEN ROW has no cusip
    be, nvda = rows
    assert be["issuer"] == "BLOOM ENERGY CORP" and be["cusip"] == "093712107"
    assert be["value"] == 15900000.0 and be["shares"] == 650000.0
    assert be["share_type"] == "SH" and be["put_call"] is None
    assert nvda["put_call"] == "Put"


def test_parse_info_table_unparseable_xml_returns_empty():
    assert parse_info_table("<not xml") == []


def test_fetch_info_table_xml_picks_the_information_table_file():
    index = {"directory": {"item": [
        {"name": "primary_doc.xml"}, {"name": "infotable.xml"},
        {"name": "form13f.txt"}]}}
    primary = "<edgarSubmission>cover page</edgarSubmission>"

    def _get(url, headers=None, timeout=None):
        if url.endswith("index.json"):
            return _resp(index)
        if url.endswith("primary_doc.xml"):
            return _resp(primary, is_json=False)
        return _resp(INFO_TABLE_XML, is_json=False)

    with patch("execution.thesis.study_edgar.requests.get", side_effect=_get):
        xml = fetch_info_table_xml("0002045724", "0002045724-26-000004")
    assert xml is not None and "informationTable" in xml


def test_fetch_history_dedupes_periods_and_merges_ciks():
    # CIK A files Q1; CIK B files an AMENDMENT for Q4 later than A's original.
    sub_a = {"filings": {"recent": {
        "form": ["13F-HR", "13F-HR"],
        "accessionNumber": ["A-1", "A-0"],
        "filingDate": ["2026-05-14", "2026-02-12"],
        "reportDate": ["2026-03-31", "2025-12-31"]}}}
    sub_b = {"filings": {"recent": {
        "form": ["13F-HR/A"],
        "accessionNumber": ["B-9"],
        "filingDate": ["2026-03-01"],
        "reportDate": ["2025-12-31"]}}}
    calls = {}

    def _get(url, headers=None, timeout=None):
        if "CIK0000000001" in url:
            return _resp(sub_a)
        if "CIK0000000002" in url:
            return _resp(sub_b)
        if url.endswith("index.json"):
            return _resp({"directory": {"item": [{"name": "infotable.xml"}]}})
        calls[url] = calls.get(url, 0) + 1
        return _resp(INFO_TABLE_XML, is_json=False)

    with patch("execution.thesis.study_edgar.requests.get", side_effect=_get):
        hist = fetch_13f_history(["0000000001", "0000000002"], limit=8)
    assert [h["period"] for h in hist] == ["2026-03-31", "2025-12-31"]
    assert hist[1]["accession"] == "B-9"       # later-filed amendment won Q4
    assert all(len(h["holdings"]) == 2 for h in hist)


def test_fetch_history_survives_one_cik_failing():
    def _get(url, headers=None, timeout=None):
        if "CIK0000000001" in url:
            raise RuntimeError("EDGAR down")
        if "submissions" in url:
            return _resp({"filings": {"recent": {
                "form": ["13F-HR"], "accessionNumber": ["B-1"],
                "filingDate": ["2026-05-14"], "reportDate": ["2026-03-31"]}}})
        if url.endswith("index.json"):
            return _resp({"directory": {"item": [{"name": "infotable.xml"}]}})
        return _resp(INFO_TABLE_XML, is_json=False)

    with patch("execution.thesis.study_edgar.requests.get", side_effect=_get):
        hist = fetch_13f_history(["0000000001", "0000000002"], limit=8)
    assert len(hist) == 1
