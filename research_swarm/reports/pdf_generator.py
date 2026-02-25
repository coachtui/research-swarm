"""PDF generation from HTML/Markdown reports using xhtml2pdf (pure Python, no system libs)."""

from io import BytesIO
from pathlib import Path

import markdown

from .pdf_styles import PDF_CSS

# Legacy CSS for the backward-compatible markdown→PDF path (simplified for xhtml2pdf)
_LEGACY_CSS = """
@page { size: letter; margin: 1in; }
body { font-family: Helvetica, Arial, sans-serif; font-size: 11pt; line-height: 1.6; color: #333; }
h1 { color: #1a1a2e; border-bottom: 3px solid #00D9B5; padding-bottom: 0.3em; page-break-after: avoid; }
h2 { color: #16213e; border-bottom: 1px solid #ccc; padding-bottom: 0.2em; page-break-after: avoid; }
h3 { color: #2c3e50; page-break-after: avoid; }
h4 { color: #34495e; }
table { border-collapse: collapse; width: 100%; margin: 1em 0; page-break-inside: avoid; }
th, td { border: 1px solid #ddd; padding: 8px 12px; text-align: left; }
th { background: #1a1a2e; color: white; font-weight: bold; }
img { max-width: 100%; height: auto; page-break-inside: avoid; }
blockquote { border-left: 4px solid #00D9B5; padding-left: 1em; color: #666; font-style: italic; }
strong { color: #2c3e50; }
hr { border: none; border-top: 1px solid #ccc; margin: 2em 0; }
"""


def _inject_css(html_content: str, css: str) -> str:
    """Inject a CSS block into the HTML <head> section."""
    style_tag = f'<style type="text/css">\n{css}\n</style>'
    if "<head>" in html_content:
        return html_content.replace("<head>", f"<head>\n{style_tag}", 1)
    if "<body>" in html_content:
        body_idx = html_content.index("<body>")
        return f"<html><head>{style_tag}</head>" + html_content[body_idx:]
    return f"<html><head>{style_tag}</head><body>{html_content}</body></html>"


def _html_to_pdf_bytes(html_content: str) -> bytes:
    """Convert an HTML string to PDF bytes via xhtml2pdf/pisa."""
    from xhtml2pdf import pisa  # lazy import — only needed when generating PDFs

    buf = BytesIO()
    result = pisa.CreatePDF(html_content, dest=buf)
    if result.err:
        raise RuntimeError(f"xhtml2pdf reported {result.err} error(s) during PDF generation")
    return buf.getvalue()


class PDFGenerator:
    """Generates PDF files from HTML/Markdown content using xhtml2pdf."""

    def __init__(self):
        """Initialize PDF generator with DVRG-branded CSS."""
        self._css = PDF_CSS
        self._legacy_css = _LEGACY_CSS

    def generate_from_html(self, html_content: str, output_path: Path, base_dir: Path = None) -> Path:
        """Generate PDF from pre-rendered HTML string (DVRG branded template).

        Args:
            html_content: Complete HTML string from Jinja2 template
            output_path: Path for output PDF file
            base_dir: Unused — kept for API compatibility

        Returns:
            Path to generated PDF file
        """
        if not html_content.strip():
            raise ValueError("HTML content is empty")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        html_with_css = _inject_css(html_content, self._css)
        pdf_bytes = _html_to_pdf_bytes(html_with_css)
        output_path.write_bytes(pdf_bytes)
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
            base_dir: Unused — kept for API compatibility

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
        html_with_css = _inject_css(full_html, self._legacy_css)
        pdf_bytes = _html_to_pdf_bytes(html_with_css)
        output_path.write_bytes(pdf_bytes)
        return output_path
