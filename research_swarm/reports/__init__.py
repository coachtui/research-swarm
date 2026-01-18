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
from .pdf_generator import PDFGenerator
from .renderer import TemplateRenderer
from .visualizations import ChartGenerator

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
