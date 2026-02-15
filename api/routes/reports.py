"""
Report generation endpoints — PDF download from completed analysis runs.
"""

import asyncio
import json
import io
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from loguru import logger

from api.dependencies import get_current_user
from api.models.auth import User
from api.lib.db import get_db

router = APIRouter()


class _NoOpPersistence:
    """Stub persistence for DataExtractor (only used for track record lookups)."""
    def get_previous_report(self, ticker, **kwargs):
        return None


def _build_report_data(run_row, stock_result_rows):
    """Build ReportData from Prisma DB rows using existing DataExtractor logic."""
    from research_swarm.orchestration.models import StockResult, StockStatus
    from research_swarm.reports.data_extractor import DataExtractor
    from research_swarm.reports.models import ReportData

    extractor = DataExtractor(_NoOpPersistence())
    stocks = []

    for sr in stock_result_rows:
        if sr.status != "completed" or not sr.fullOutput:
            continue

        # Handle double-serialized fullOutput (json.dumps on a Json column)
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
        except Exception as e:
            logger.warning(f"Failed to extract {sr.ticker} for PDF: {e}")
            continue

    if not stocks:
        raise ValueError("No completed stocks with data to generate report")

    sorted_stocks = sorted(stocks, key=lambda s: s.moat_score, reverse=True)
    top_picks = sorted_stocks[:3]
    watchlist = [s for s in stocks if s.is_watchlist_candidate]
    avg_moat = sum(s.moat_score for s in stocks) / len(stocks)

    cost_by_ticker = {
        sr.ticker: sr.costUsd or 0.0
        for sr in stock_result_rows
        if sr.status == "completed"
    }

    return ReportData(
        run_id=run_row.id,
        run_name=run_row.runName,
        analysis_date=run_row.createdAt.strftime("%Y-%m-%d"),
        analysis_period=run_row.analysisPeriod or "N/A",
        quarters=run_row.quarters or [],
        fiscal_year=run_row.fiscalYear,
        stocks=stocks,
        top_picks=top_picks,
        watchlist_candidates=watchlist,
        total_stocks=run_row.totalStocks,
        completed_count=run_row.completedCount,
        failed_count=run_row.failedCount,
        average_moat_score=avg_moat,
        total_cost_usd=run_row.totalCostUsd or 0.0,
        total_elapsed_seconds=run_row.elapsedSeconds or 0.0,
        cost_by_ticker=cost_by_ticker,
    )


def _generate_pdf_bytes(report_data) -> bytes:
    """Render ReportData → DVRG HTML → PDF bytes (synchronous, run in thread)."""
    from research_swarm.reports.renderer import TemplateRenderer
    from research_swarm.reports.pdf_generator import PDFGenerator

    renderer = TemplateRenderer()
    html_content = renderer.render_pdf_report(report_data, include_charts=False)

    pdf_gen = PDFGenerator()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        pdf_gen.generate_from_html(html_content, tmp_path)
        pdf_bytes = tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)

    return pdf_bytes


@router.get("/runs/{run_id}/report/pdf")
async def download_pdf_report(
    run_id: str,
    user: User = Depends(get_current_user),
):
    """Generate and download a PDF report for a completed analysis run."""
    db = await get_db()

    run = await db.run.find_unique(
        where={"id": run_id},
        include={"stockResults": True},
    )

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.userId != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    if run.status != "completed":
        raise HTTPException(status_code=400, detail="Run is not completed yet")

    try:
        report_data = _build_report_data(run, run.stockResults)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        pdf_bytes = await asyncio.to_thread(_generate_pdf_bytes, report_data)
    except Exception as e:
        logger.error(f"PDF generation failed for run {run_id}: {e}")
        raise HTTPException(status_code=500, detail="PDF generation failed")

    # Build filename from tickers
    tickers = "_".join(run.tickers[:3])
    if len(run.tickers) > 3:
        tickers += f"_+{len(run.tickers) - 3}"
    filename = f"report_{tickers}_{run_id[:8]}.pdf"

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
