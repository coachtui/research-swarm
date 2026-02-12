"""Template rendering for Markdown report generation."""

from pathlib import Path
from typing import List

from jinja2 import Environment, FileSystemLoader, Template

from .models import ReportData, ReportSection


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
