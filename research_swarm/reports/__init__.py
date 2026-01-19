"""Report generation module for research swarm analysis.

This module transforms SwarmRun analysis data into professional reports.
"""

from .data_extractor import DataExtractor
from .generator import ReportGenerator, generate_report
from .models import (
    ReportConfig,
    ReportData,
    ReportOutput,
    ReportSection,
    ReportType,
    StockReportData,
)
from .renderer import TemplateRenderer
from .visualizations import ChartGenerator

# PDF generator is optional (requires system dependencies)
try:
    from .pdf_generator import PDFGenerator
except (ImportError, OSError) as e:
    import warnings
    warnings.warn(f"PDF generation unavailable: {e}", ImportWarning)
    PDFGenerator = None

__all__ = [
    # Models
    "ReportConfig",
    "ReportData",
    "ReportOutput",
    "ReportSection",
    "ReportType",
    "StockReportData",
    # Extractors
    "DataExtractor",
    # Visualizations
    "ChartGenerator",
    # Rendering
    "TemplateRenderer",
    # PDF Generation
    "PDFGenerator",
    # Main Generator
    "ReportGenerator",
    "generate_report",
]
