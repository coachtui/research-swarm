#!/usr/bin/env python3
"""
Dev script — generate a PDF for a given run_id locally.

Usage:
    python scripts/generate_pdf_dev.py <run_id> [--tier investor|trader] [--out /tmp/report.pdf]

Examples:
    # Generate investor-tier PDF for a run
    python scripts/generate_pdf_dev.py abc123 --tier investor

    # Generate trader-tier PDF (includes enhanced trade setup)
    python scripts/generate_pdf_dev.py abc123 --tier trader --out /tmp/full.pdf

The script:
  1. Connects to Neon via Prisma (reads DATABASE_URL from .env)
  2. Loads the run and its stock results
  3. Builds ReportData via DataExtractor
  4. Renders PDF via TemplateRenderer + PDFGenerator
  5. Saves to --out (default: /tmp/dvrg_report_<run_id[:8]>.pdf)
  6. Opens the PDF with the default OS viewer (macOS: open, Linux: xdg-open)

Acceptance checks (manual):
  - PDF renders and is readable
  - Title page shows run name + generated date
  - Investment thesis section shows structured sections (not raw string)
  - Trader tier includes trade table; Investor tier does NOT
  - All sections handle missing data without crashing (no Jinja2 errors)
"""

import argparse
import asyncio
import json
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

# ── Allow running from project root without installing the package ───────────
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load .env so DATABASE_URL is available
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")


async def _get_run(db, run_id: str):
    run = await db.run.find_unique(
        where={"id": run_id},
        include={"stockResults": True},
    )
    if not run:
        raise SystemExit(f"Run not found: {run_id}")
    return run


def _build_report_data(run_row, stock_result_rows):
    from research_swarm.orchestration.models import StockResult, StockStatus
    from research_swarm.reports.data_extractor import DataExtractor
    from research_swarm.reports.models import ReportData

    class _NoOpPersistence:
        def get_previous_report(self, ticker, **kwargs):
            return None

    extractor = DataExtractor(_NoOpPersistence())
    stocks = []

    for sr in stock_result_rows:
        if sr.status != "completed" or not sr.fullOutput:
            print(f"  Skipping {sr.ticker}: status={sr.status}, has_output={bool(sr.fullOutput)}")
            continue

        full_output = sr.fullOutput
        if isinstance(full_output, str):
            full_output = json.loads(full_output)

        result = StockResult(
            ticker=sr.ticker,
            status=StockStatus.COMPLETED,
            moat_score=sr.moatScore,
            is_watchlist_candidate=sr.isWatchlistCandidate or False,
            investment_thesis=sr.investmentThesis,
            full_output=full_output,
            tokens_used=sr.tokensUsed or 0,
            cost_usd=sr.costUsd or 0.0,
            processing_time_seconds=sr.processingTimeSeconds,
        )

        try:
            stock_data = extractor._extract_stock(result)
            stocks.append(stock_data)
            print(f"  ✓ {sr.ticker} — moat={sr.moatScore:.1f}")
        except Exception as e:
            print(f"  ✗ {sr.ticker} — extraction failed: {e}")
            continue

    if not stocks:
        raise SystemExit("No completed stocks with extractable data")

    sorted_stocks = sorted(stocks, key=lambda s: s.moat_score, reverse=True)
    avg_moat = sum(s.moat_score for s in stocks) / len(stocks)

    return ReportData(
        run_id=run_row.id,
        run_name=run_row.runName,
        analysis_date=run_row.createdAt.strftime("%Y-%m-%d"),
        analysis_period=getattr(run_row, "analysisPeriod", None) or "N/A",
        quarters=getattr(run_row, "quarters", None) or [],
        fiscal_year=getattr(run_row, "fiscalYear", None),
        stocks=stocks,
        top_picks=sorted_stocks[:3],
        watchlist_candidates=[s for s in stocks if s.is_watchlist_candidate],
        total_stocks=getattr(run_row, "totalStocks", len(stocks)),
        completed_count=len(stocks),
        failed_count=getattr(run_row, "failedCount", 0),
        average_moat_score=avg_moat,
        total_cost_usd=getattr(run_row, "totalCostUsd", 0.0) or 0.0,
        total_elapsed_seconds=getattr(run_row, "elapsedSeconds", 0.0) or 0.0,
        cost_by_ticker={},
    )


def _generate_pdf(report_data, tier: str, out_path: Path) -> None:
    from research_swarm.reports.renderer import TemplateRenderer
    from research_swarm.reports.pdf_generator import PDFGenerator

    print(f"\nRendering HTML (tier={tier})…")
    renderer = TemplateRenderer()
    html_content = renderer.render_pdf_report(report_data, include_charts=False, tier=tier)

    print(f"Generating PDF → {out_path}")
    pdf_gen = PDFGenerator()
    pdf_gen.generate_from_html(html_content, out_path)
    size_kb = out_path.stat().st_size // 1024
    print(f"PDF written: {out_path} ({size_kb} KB)")


def _open_pdf(path: Path) -> None:
    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.run(["open", str(path)], check=True)
        elif system == "Linux":
            subprocess.run(["xdg-open", str(path)], check=True)
        else:
            print(f"Auto-open not supported on {system}. Open manually: {path}")
    except Exception as e:
        print(f"Could not auto-open PDF: {e}")


async def main(run_id: str, tier: str, out_path: Path) -> None:
    from api.lib.db import get_db

    print(f"Connecting to database…")
    db = await get_db()

    print(f"Loading run {run_id}…")
    run = await _get_run(db, run_id)
    print(f"Run: '{run.runName or run.id}' — status={run.status} — {len(run.stockResults)} stock result(s)")

    if run.status != "completed":
        print(f"Warning: run status is '{run.status}' (not completed) — proceeding anyway")

    print("\nExtracting stock data…")
    report_data = _build_report_data(run, run.stockResults)

    _generate_pdf(report_data, tier, out_path)
    _open_pdf(out_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a PDF report for a run_id (dev only)")
    parser.add_argument("run_id", help="Run ID to generate PDF for")
    parser.add_argument(
        "--tier",
        choices=["investor", "trader"],
        default="investor",
        help="Tier to simulate (controls Trader-only sections). Default: investor",
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="Output PDF path. Default: /tmp/dvrg_report_<run_id[:8]>.pdf",
    )
    args = parser.parse_args()

    out_path: Path = args.out or Path(f"/tmp/dvrg_report_{args.run_id[:8]}_{args.tier}.pdf")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    asyncio.run(main(args.run_id, args.tier, out_path))
