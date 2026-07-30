"""EDGAR 13F fetch + parse for the quarterly study pass (spec §5).

Read-only curriculum input: nothing here touches orders, sizing, or the
broker (founding-premise guard-tested). Sync requests, matching
research_swarm's SECClient posture — the cron wraps calls in
asyncio.to_thread. SEC fair access: identifying User-Agent, trivial
volume (a handful of requests per quarter).
"""
import logging
import re
from typing import Any, Dict, List, Optional

import requests

# EDGAR XML is external input — parse with defusedxml (XXE/billion-laughs
# hardening) in production; the local test runner (/usr/bin/python3, no
# pip installs) falls back to stdlib, whose expat also rejects entity
# tricks on modern Pythons.
try:
    from defusedxml import ElementTree as ET
except ImportError:  # pragma: no cover — local test env
    import xml.etree.ElementTree as ET

from execution.constants import SEC_EDGAR_USER_AGENT, STUDY_QUARTERS_BACK

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": SEC_EDGAR_USER_AGENT}
_TIMEOUT = 30

# Filers use BOTH a default namespace (<informationTable xmlns=...>) and a
# prefixed one (<ns1:informationTable xmlns:ns1=...>) — SALP's own filings
# switched to the prefixed form. Match either; a bare substring check on
# "<informationtable" silently misses every prefixed filing.
_INFO_TABLE_ROOT_RE = re.compile(r"<(?:[\w.-]+:)?informationTable[\s>]", re.IGNORECASE)


def _get(url: str) -> requests.Response:
    resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp


def list_13f_filings(cik: str, limit: int = STUDY_QUARTERS_BACK) -> List[Dict[str, str]]:
    """Newest-first 13F-HR / 13F-HR/A accessions from the submissions API."""
    data = _get(f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json").json()
    recent = (data.get("filings") or {}).get("recent") or {}
    out: List[Dict[str, str]] = []
    for form, accession, filed, period in zip(
            recent.get("form") or [], recent.get("accessionNumber") or [],
            recent.get("filingDate") or [], recent.get("reportDate") or []):
        if form in ("13F-HR", "13F-HR/A"):
            out.append({"cik": cik, "form": form, "accession": accession,
                        "filed": filed, "period": period})
        if len(out) >= limit:
            break
    return out


def fetch_info_table_xml(cik: str, accession: str) -> Optional[str]:
    """The information-table XML for one 13F filing, or None if absent."""
    base = (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
            f"{accession.replace('-', '')}")
    index = _get(f"{base}/index.json").json()
    names = [str(i.get("name", ""))
             for i in (index.get("directory") or {}).get("item") or []
             if str(i.get("name", "")).lower().endswith(".xml")]
    # primary_doc.xml is the cover page — try it last.
    names.sort(key=lambda n: n.lower().startswith("primary"))
    for name in names:
        text = _get(f"{base}/{name}").text
        if _INFO_TABLE_ROOT_RE.search(text):
            return text
    return None


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def parse_info_table(xml_text: str) -> List[Dict[str, Any]]:
    """One dict per <infoTable> row. Values as filed — full USD since the
    2023 rule change; every trusted-fund filing postdates it. Rows without
    a cusip or value are skipped (they can't be diffed)."""
    rows: List[Dict[str, Any]] = []
    try:
        root = ET.fromstring(xml_text)
    except Exception:  # noqa: BLE001 — ParseError or defusedxml Entities/DTDForbidden
        logger.exception("13F info table: unparseable or forbidden XML")
        return rows
    for node in root.iter():
        if _local(node.tag) != "infotable":
            continue
        row: Dict[str, Any] = {"issuer": None, "cusip": None, "class": None,
                               "value": None, "shares": None,
                               "share_type": None, "put_call": None}
        for child in node.iter():
            name, text = _local(child.tag), (child.text or "").strip()
            if name == "nameofissuer":
                row["issuer"] = text
            elif name == "cusip":
                row["cusip"] = text or None
            elif name == "titleofclass":
                row["class"] = text
            elif name == "value" and text:
                row["value"] = float(text.replace(",", ""))
            elif name == "sshprnamt" and text:
                row["shares"] = float(text.replace(",", ""))
            elif name == "sshprnamttype":
                row["share_type"] = text
            elif name == "putcall":
                row["put_call"] = text or None
        if row["cusip"] and row["value"] is not None:
            rows.append(row)
    return rows


def fetch_13f_history(ciks: List[str],
                      limit: int = STUDY_QUARTERS_BACK) -> List[Dict[str, Any]]:
    """Merged filing history across a fund's CIKs, one snapshot per report
    period (amendments and dual registrants: the latest-FILED filing wins),
    newest first. A CIK whose submissions fetch fails is logged and skipped —
    the other registrant may still carry the history."""
    filings: List[Dict[str, str]] = []
    for cik in ciks:
        try:
            filings.extend(list_13f_filings(cik, limit=limit))
        except Exception:  # noqa: BLE001
            logger.exception("13F study: submissions fetch failed for CIK %s", cik)
    by_period: Dict[str, Dict[str, str]] = {}
    for f in sorted(filings, key=lambda f: f["filed"]):
        by_period[f["period"]] = f
    history: List[Dict[str, Any]] = []
    for period in sorted(by_period, reverse=True)[:limit]:
        f = by_period[period]
        try:
            xml_text = fetch_info_table_xml(f["cik"], f["accession"])
        except Exception:  # noqa: BLE001
            logger.exception("13F study: info table fetch failed for %s", f["accession"])
            continue
        if xml_text is None:
            logger.warning("13F study: no info table in %s %s", f["cik"], f["accession"])
            continue
        history.append({**f, "holdings": parse_info_table(xml_text)})
    return history
