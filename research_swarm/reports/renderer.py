"""Template rendering for Markdown report generation."""

from pathlib import Path
from typing import List

from jinja2 import Environment, FileSystemLoader, Template

from .models import ReportData, ReportSection


_LOGO_CACHE: str | None = None


def _logo_data_uri() -> str:
    """The site logotype (DV|RG), embedded as a data URI so the PDF needs no
    external asset resolution. Cached per process; empty string if missing so
    the template can fall back to the text masthead."""
    global _LOGO_CACHE
    if _LOGO_CACHE is None:
        import base64
        logo = Path(__file__).parent / "assets" / "dvrg-logo.png"
        _LOGO_CACHE = (
            "data:image/png;base64," + base64.b64encode(logo.read_bytes()).decode()
            if logo.exists() else ""
        )
    return _LOGO_CACHE


def _clip(text, limit: int = 100) -> str:
    """Truncate at a sentence or word boundary — never mid-word.

    The template previously used raw character slices ([:100] + "..."), which
    shipped fragments like "Initiate cautiou..." on page one of a paid report.
    Prefer the last sentence end inside the limit when it keeps most of the
    text; otherwise cut at the last word boundary with an ellipsis.
    """
    if text is None:
        return ""
    text = str(text).strip()
    if len(text) <= limit:
        return text

    window = text[:limit]
    # Sentence boundary that preserves at least 60% of the budget
    pos = window.rfind(". ")
    if pos >= int(limit * 0.6):
        return window[: pos + 1].strip()
    pos = window.rfind("; ")
    if pos >= int(limit * 0.6):
        return window[:pos].strip() + "…"
    # Word boundary fallback
    pos = window.rfind(" ")
    if pos <= 0:
        pos = limit
    return window[:pos].rstrip(",;:.") + "…"


class TemplateRenderer:
    """Renders Jinja2 templates for report generation."""

    def __init__(self, templates_dir: Path = None):
        """Initialize template renderer.

        Args:
            templates_dir: Directory containing Jinja2 templates.
                          Defaults to the templates/ directory in this package.
        """
        if templates_dir is None:
            templates_dir = Path(__file__).parent / "templates"

        self.templates_dir = templates_dir
        self.env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.env.filters["clip"] = _clip

    def render_section(
        self,
        section: ReportSection,
        report_data: ReportData,
        include_charts: bool = True,
    ) -> str:
        """Render a specific report section.

        Args:
            section: Section to render
            report_data: Complete report data
            include_charts: Whether to include chart references

        Returns:
            Rendered markdown content for the section
        """
        template_map = {
            ReportSection.EXECUTIVE_SUMMARY: "executive_summary.md.j2",
            ReportSection.STOCK_ANALYSIS: "stock_analysis.md.j2",
            ReportSection.SUPPLY_CHAIN: "supply_chain.md.j2",
            ReportSection.WATCHLIST: "watchlist.md.j2",
        }

        template_file = template_map.get(section)
        if not template_file:
            raise ValueError(f"Unknown section: {section}")

        template = self.env.get_template(template_file)

        # Prepare context based on section
        context = {
            "report": report_data,
            "stocks": report_data.stocks,
            "include_charts": include_charts,
        }

        if section == ReportSection.EXECUTIVE_SUMMARY:
            context["top_picks"] = report_data.top_picks
        elif section == ReportSection.WATCHLIST:
            context["watchlist_candidates"] = report_data.watchlist_candidates

        return template.render(**context)

    def render_full_report(
        self,
        report_data: ReportData,
        sections: List[ReportSection] = None,
        include_charts: bool = True,
    ) -> str:
        """Render complete report with all requested sections.

        Args:
            report_data: Complete report data
            sections: List of sections to include (defaults to all)
            include_charts: Whether to include chart references

        Returns:
            Complete rendered markdown report
        """
        if sections is None:
            sections = [
                ReportSection.EXECUTIVE_SUMMARY,
                ReportSection.STOCK_ANALYSIS,
                ReportSection.WATCHLIST,
            ]

        # Render each section
        section_content = []
        for section in sections:
            rendered = self.render_section(section, report_data, include_charts)
            section_content.append(rendered)

        # Combine sections with separators
        content = "\n\n---\n\n".join(section_content)

        # Wrap in base template
        base_template = self.env.get_template("base.md.j2")
        return base_template.render(report=report_data, content=content)

    def render_pdf_report(
        self,
        report_data: ReportData,
        include_charts: bool = False,
        tier: str = "investor",
    ) -> str:
        """Render the DVRG-branded HTML PDF report.

        Args:
            report_data: Complete report data
            include_charts: Whether to include chart references
            tier: User subscription tier — controls Trader-only section visibility.
                  "investor" hides trade_setup sections; "trader" includes them.

        Returns:
            Complete rendered HTML string for WeasyPrint
        """
        tier = (tier or "investor").lower()
        include_trader_content   = (tier == "trader")
        # Investor+ sees headline signal metrics (σ, noise score, stop prob)
        include_signal_metrics   = tier in ("investor", "trader")
        # Trader-only: full engine diagnostics appendix (scenario weights,
        # multiplier stack, stop prob decomposition, driver ranking)
        include_engine_diagnostics = (tier == "trader")

        template = self.env.get_template("pdf_report.html.j2")
        return template.render(
            report=report_data,
            stocks=report_data.stocks,
            logo_data_uri=_logo_data_uri(),
            include_charts=include_charts,
            include_trader_content=include_trader_content,
            include_signal_metrics=include_signal_metrics,
            include_engine_diagnostics=include_engine_diagnostics,
            tier=tier,
        )

    def render_custom(self, template_string: str, context: dict) -> str:
        """Render a custom template string.

        Args:
            template_string: Jinja2 template string
            context: Template context dictionary

        Returns:
            Rendered content
        """
        template = self.env.from_string(template_string)
        return template.render(**context)

    def get_template(self, template_name: str) -> Template:
        """Get a template by name.

        Args:
            template_name: Name of template file

        Returns:
            Jinja2 Template object
        """
        return self.env.get_template(template_name)
