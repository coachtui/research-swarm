"""PDF generation from HTML/Markdown reports using WeasyPrint."""

from pathlib import Path

import markdown
from weasyprint import CSS, HTML

from .pdf_styles import PDF_CSS

# Legacy CSS for the backward-compatible markdown→PDF path
_LEGACY_CSS = """
@page { size: letter; margin: 1in; @bottom-right { content: counter(page) " / " counter(pages); font-size: 9pt; color: #666; } }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; font-size: 11pt; line-height: 1.6; color: #333; }
h1 { color: #1a1a2e; border-bottom: 3px solid #00D9B5; padding-bottom: 0.3em; page-break-after: avoid; }
h2 { color: #16213e; border-bottom: 1px solid #ccc; padding-bottom: 0.2em; page-break-after: avoid; }
h3 { color: #2c3e50; page-break-after: avoid; }
h4 { color: #34495e; }
table { border-collapse: collapse; width: 100%; margin: 1em 0; page-break-inside: avoid; }
th, td { border: 1px solid #ddd; padding: 8px 12px; text-align: left; }
th { background: #1a1a2e; color: white; font-weight: bold; }
tr:nth-child(even) { background: #f9f9f9; }
img { max-width: 100%; height: auto; page-break-inside: avoid; }
blockquote { border-left: 4px solid #00D9B5; padding-left: 1em; color: #666; font-style: italic; }
strong { color: #2c3e50; }
hr { border: none; border-top: 1px solid #ccc; margin: 2em 0; }
h1, h2, h3, h4, h5, h6 { break-after: avoid-page; }
"""


class PDFGenerator:
    """Generates PDF files from HTML/Markdown content using WeasyPrint."""

    def __init__(self):
        """Initialize PDF generator with DVRG-branded CSS."""
        self._css = CSS(string=PDF_CSS)
        self._legacy_css = CSS(string=_LEGACY_CSS)

    def generate_from_html(self, html_content: str, output_path: Path, base_dir: Path = None) -> Path:
        """Generate PDF from pre-rendered HTML string (DVRG branded template).

        Args:
            html_content: Complete HTML string from Jinja2 template
            output_path: Path for output PDF file
            base_dir: Base directory for resolving relative paths (optional)

        Returns:
            Path to generated PDF file
        """
        if not html_content.strip():
            raise ValueError("HTML content is empty")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        base_url = str(base_dir) if base_dir else None
        HTML(string=html_content, base_url=base_url).write_pdf(
            output_path, stylesheets=[self._css]
        )
        return output_path

    def generate(self, markdown_path: Path, output_path: Path) -> Path:
        """Generate PDF from Markdown file.

        Args:
            markdown_path: Path to source Markdown file
            output_path: Path for output PDF file

        Returns:
            Path to generated PDF file
        """
        if not markdown_path.exists():
            raise FileNotFoundError(f"Markdown file not found: {markdown_path}")

        with open(markdown_path, "r", encoding="utf-8") as f:
            md_content = f.read()

        if not md_content.strip():
            raise ValueError(f"Markdown file is empty: {markdown_path}")

        return self.generate_from_string(md_content, output_path, base_dir=markdown_path.parent)

    def generate_from_string(
        self, markdown_content: str, output_path: Path, base_dir: Path = None
    ) -> Path:
        """Generate PDF directly from Markdown string.

        Args:
            markdown_content: Markdown content string
            output_path: Path for output PDF file
            base_dir: Base directory for resolving relative paths (optional)

        Returns:
            Path to generated PDF file
        """
        if not markdown_content.strip():
            raise ValueError("Markdown content is empty")

        html_body = markdown.markdown(
            markdown_content,
            extensions=["tables", "fenced_code", "nl2br"],
        )

        full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Research Swarm Report</title>
</head>
<body>
    {html_body}
</body>
</html>"""

        output_path.parent.mkdir(parents=True, exist_ok=True)
        base_url = str(base_dir) if base_dir else None
        HTML(string=full_html, base_url=base_url).write_pdf(
            output_path, stylesheets=[self._legacy_css]
        )
        return output_path
