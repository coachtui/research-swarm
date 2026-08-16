"""Snapshot assembler — Phase A of the pipeline re-architecture.

One assembly point for everything an analysis fetches. The Manager (and any
standalone agent run) calls `assemble_snapshot()` once; agents consume the
result through the legacy `shared_swarm_data` dict shape via
`snapshot_to_swarm_bundle()`. No agent fetches from a provider directly.

What this adds over the old hybrid-provider call:
- The OpenInsider scrape moves here (it previously lived inside a News Hound
  graph node — the only fetch that escaped the shared bundle) and runs
  concurrently with the main SEC + yfinance fetch.
- Per-section provenance on the returned TickerSnapshot: missing data is an
  explicit `SectionStatus.MISSING` entry, never a silent None.
- A completeness figure logged per assembly.

Byte-identical guarantee: the raw payloads in `snapshot.raw_bundle` come from
the exact same client calls and cache layers as before, so agent outputs are
unchanged. The typed sections of TickerSnapshot are populated where cheaply
derivable; full typed population is Phase B/C.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict, Optional

from research_swarm.logger import logger
from research_swarm.contracts.snapshot import (
    FxNormalization,
    Provenance,
    Quote,
    SectionStatus,
    TickerSnapshot,
)
from research_swarm.data.data_provider_hybrid import hybrid_provider
from research_swarm.data.data_cache_service import data_cache


# Section name → (bundle key, source label). Drives provenance derivation.
_SECTIONS = {
    "filings": ("filings_raw", "sec_edgar"),
    "company_info": ("company_info", "yfinance"),
    "valuation": ("valuation_metrics", "yfinance"),
    "history": ("historical_data", "yfinance"),
    "earnings": ("earnings_data", "yfinance"),
    "quarterly_financials": ("quarterly_financials", "yfinance"),
    "institutional": ("institutional_holders", "yfinance"),
    "short_interest": ("short_interest", "yfinance"),
    "analyst_estimates": ("analyst_estimates", "yfinance"),
    "upgrades_downgrades": ("upgrades_downgrades", "yfinance"),
    "filings_8k": ("recent_8k_filings", "sec_edgar"),
    "dark_pool": ("dark_pool_data", "finra"),
    "insider_transactions": ("openinsider_transactions", "openinsider"),
}


def _fetch_openinsider(ticker: str) -> Optional[list]:
    """OpenInsider transactions with the same Neon-cache behavior the News
    Hound node used: serve cached, fetch on miss, cache only non-empty results
    (an empty list can be a transient scrape failure)."""
    from research_swarm.data.openinsider_client import openinsider_client

    cached = data_cache.get_openinsider(ticker)
    if cached is not None:
        logger.debug(f"[Snapshot] OpenInsider cache HIT for {ticker}")
        return cached

    transactions = openinsider_client.get_insider_transactions(ticker, days_back=365)
    if transactions:
        data_cache.set_openinsider(ticker, transactions)
    return transactions


def _is_empty(value: Any) -> bool:
    """Empty check that understands DataFrames and the filings metadata stub."""
    if value is None:
        return True
    if hasattr(value, "empty"):  # DataFrame
        return bool(value.empty)
    if isinstance(value, dict):
        # A filings_raw dict holding only its _metadata stub is empty
        real_keys = [k for k in value.keys() if k != "_metadata"]
        return len(real_keys) == 0
    if isinstance(value, (list, tuple)):
        return len(value) == 0
    return False


def _build_provenance(bundle: Dict[str, Any], errors: Dict[str, str]) -> Dict[str, Provenance]:
    now = datetime.now()
    provenance: Dict[str, Provenance] = {}
    for section, (bundle_key, source) in _SECTIONS.items():
        if section in errors:
            provenance[section] = Provenance(
                source=source, status=SectionStatus.ERROR, fetched_at=now,
                detail=errors[section],
            )
        elif _is_empty(bundle.get(bundle_key)):
            provenance[section] = Provenance(
                source=source, status=SectionStatus.MISSING, fetched_at=now,
                detail="provider returned no data",
            )
        else:
            # Served through the layered cache/fetch path — finer cache-hit
            # attribution arrives when the assembler owns individual fetches.
            provenance[section] = Provenance(
                source=source, status=SectionStatus.FRESH, fetched_at=now,
            )
    return provenance


def assemble_snapshot(ticker: str, period: str = "1y") -> TickerSnapshot:
    """Fetch everything one equity analysis needs, once.

    Runs the SEC+yfinance+FINRA bundle and the OpenInsider scrape
    concurrently, then wraps the payloads in a TickerSnapshot with
    per-section provenance.
    """
    ticker = ticker.upper()
    logger.info(f"[Snapshot] Assembling snapshot for {ticker}")
    errors: Dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix=f"snap-{ticker}") as pool:
        bundle_future = pool.submit(hybrid_provider.get_complete_swarm_data, ticker, period)
        insider_future = pool.submit(_fetch_openinsider, ticker)

        bundle = bundle_future.result()  # a total fetch failure should raise — the run can't proceed
        try:
            bundle["openinsider_transactions"] = insider_future.result()
        except Exception as e:
            logger.warning(f"[Snapshot] OpenInsider fetch failed for {ticker}: {e}")
            errors["insider_transactions"] = str(e)
            bundle["openinsider_transactions"] = None

    provenance = _build_provenance(bundle, errors)

    # ── Cheap typed fields (full typed population is Phase B/C) ────────────
    company_info = bundle.get("company_info") or {}
    valuation = bundle.get("valuation_metrics") or {}

    quote = None
    if valuation.get("current_price"):
        market_cap = company_info.get("market_cap")
        if market_cap is None and valuation.get("market_cap_millions"):
            market_cap = valuation["market_cap_millions"] * 1_000_000
        quote = Quote(
            price=valuation["current_price"],
            market_cap=market_cap,
            as_of=datetime.now(),
        )

    snapshot = TickerSnapshot(
        ticker=ticker,
        company_name=company_info.get("name"),
        sector=company_info.get("sector"),
        industry=company_info.get("industry"),
        is_foreign_filer=bool(bundle.get("is_foreign")),
        fx=FxNormalization(
            # financial_currency = the currency the statements are reported in
            # (differs from trading currency for ADRs — TSM trades USD, reports TWD)
            reporting_currency=company_info.get("financial_currency")
            or company_info.get("currency")
            or "USD",
            converted=False,  # normalization still happens downstream (Phase B moves it here)
        ),
        as_of=datetime.now(),
        quote=quote,
        provenance=provenance,
        raw_bundle=bundle,
    )

    missing = [s for s, p in provenance.items() if p.status != SectionStatus.FRESH]
    logger.info(
        f"[Snapshot] {ticker}: {snapshot.completeness_pct():.0f}% complete"
        + (f" — missing/error: {', '.join(missing)}" if missing else "")
    )
    return snapshot


def assemble_market_bundle(ticker: str, period: str = "1y") -> Dict[str, Any]:
    """Light bundle for runs that don't need SEC quarterly filings — the
    News Hound / Quant standalone entry points and the ETF path.

    Fetches exactly the sections those agents' deleted per-node fallbacks
    used to fetch, but once, up front, instead of scattered mid-run.
    """
    ticker = ticker.upper()
    logger.info(f"[Snapshot] Assembling light market bundle for {ticker}")

    bundle: Dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix=f"snap-lt-{ticker}") as pool:
        yf_future = pool.submit(
            hybrid_provider._get_extended_yfinance_bundle, ticker, period
        )
        insider_future = pool.submit(_fetch_openinsider, ticker)

        try:
            bundle.update(yf_future.result())
        except Exception as e:
            logger.warning(f"[Snapshot] Market bundle fetch failed for {ticker}: {e}")
        try:
            bundle["openinsider_transactions"] = insider_future.result()
        except Exception as e:
            logger.warning(f"[Snapshot] OpenInsider fetch failed for {ticker}: {e}")
            bundle["openinsider_transactions"] = None

    # 8-K filings and FINRA dark pool (same cache behavior as the full bundle)
    cached_8k = data_cache.get_8k_filings(ticker)
    if cached_8k is not None:
        bundle["recent_8k_filings"] = cached_8k
    else:
        try:
            from research_swarm.data.sec_client import sec_client
            filings_8k = sec_client.get_8k_filings(ticker, days_back=90)
            bundle["recent_8k_filings"] = filings_8k
            if filings_8k is not None:
                data_cache.set_8k_filings(ticker, filings_8k)
        except Exception as e:
            logger.warning(f"[Snapshot] 8-K fetch failed for {ticker}: {e}")
            bundle["recent_8k_filings"] = None

    cached_dark = data_cache.get_dark_pool(ticker)
    if cached_dark is not None:
        bundle["dark_pool_data"] = cached_dark
    else:
        try:
            from research_swarm.data.finra_client import finra_client
            dark = finra_client.get_dark_pool_activity(ticker, weeks_back=13)
            bundle["dark_pool_data"] = dark
            if dark is not None:
                data_cache.set_dark_pool(ticker, dark)
        except Exception as e:
            logger.warning(f"[Snapshot] Dark pool fetch failed for {ticker}: {e}")
            bundle["dark_pool_data"] = None

    return bundle


def snapshot_to_swarm_bundle(snapshot: TickerSnapshot) -> Dict[str, Any]:
    """Legacy adapter: the exact `shared_swarm_data` dict shape the agents
    consume today. Deleted once agents read typed sections (Phase B)."""
    return snapshot.raw_bundle
