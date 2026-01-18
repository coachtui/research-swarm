"""PDF generation from Markdown reports using WeasyPrint."""

from pathlib import Path

import markdown
from weasyprint import CSS, HTML


class PDFGenerator:
    """Generates PDF files from Markdown content using WeasyPrint."""

    def __init__(self):
        """Initialize PDF generator with custom CSS styling."""
        self.css = CSS(
            string="""
            @page {
                size: letter;
                margin: 1in;
                @bottom-right {
                    content: counter(page) " / " counter(pages);
                    font-size: 9pt;
                    color: #666;
                }
            }

            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                font-size: 11pt;
                line-height: 1.6;
                color: #333;
            }

            h1 {
                color: #1a1a2e;
                border-bottom: 3px solid #4361ee;
                padding-bottom: 0.3em;
                margin-top: 0.5em;
                margin-bottom: 0.5em;
                page-break-after: avoid;
            }

            h2 {
                color: #16213e;
                border-bottom: 1px solid #ccc;
                padding-bottom: 0.2em;
                margin-top: 1em;
                margin-bottom: 0.5em;
                page-break-after: avoid;
            }

            h3 {
                color: #2c3e50;
                margin-top: 0.8em;
                margin-bottom: 0.4em;
                page-break-after: avoid;
            }

            h4 {
                color: #34495e;
                margin-top: 0.6em;
                margin-bottom: 0.3em;
            }

            p {
                margin: 0.5em 0;
            }

            ul, ol {
                margin: 0.5em 0;
                padding-left: 2em;
            }

            li {
                margin: 0.3em 0;
            }

            table {
                border-collapse: collapse;
                width: 100%;
                margin: 1em 0;
                page-break-inside: avoid;
            }

            th, td {
                border: 1px solid #ddd;
                padding: 8px 12px;
                text-align: left;
            }

            th {
                background: #4361ee;
                color: white;
                font-weight: bold;
            }

            tr:nth-child(even) {
                background: #f9f9f9;
            }

            img {
                max-width: 100%;
                height: auto;
                margin: 1em 0;
                page-break-inside: avoid;
            }

            code {
                background: #f4f4f4;
                padding: 2px 6px;
                border-radius: 3px;
                font-family: "Courier New", monospace;
                font-size: 0.9em;
            }

            pre {
                background: #f4f4f4;
                padding: 1em;
                border-radius: 5px;
                overflow-x: auto;
                page-break-inside: avoid;
            }

            pre code {
                background: none;
                padding: 0;
            }

            hr {
                border: none;
                border-top: 1px solid #ccc;
                margin: 2em 0;
            }

            blockquote {
                border-left: 4px solid #4361ee;
                padding-left: 1em;
                margin: 1em 0;
                color: #666;
                font-style: italic;
            }

            strong {
                color: #2c3e50;
                font-weight: bold;
            }

            /* Prevent orphaned headers */
            h1, h2, h3, h4, h5, h6 {
                break-after: avoid-page;
            }

            /* Keep content together */
            .keep-together {
                page-break-inside: avoid;
            }
        """
        )

    def generate(self, markdown_path: Path, output_path: Path) -> Path:
        """Generate PDF from Markdown file.

        Args:
            markdown_path: Path to source Markdown file
            output_path: Path for output PDF file

        Returns:
            Path to generated PDF file

        Raises:
            FileNotFoundError: If markdown_path doesn't exist
            ValueError: If markdown file is empty
        """
        if not markdown_path.exists():
            raise FileNotFoundError(f"Markdown file not found: {markdown_path}")

        # Read markdown content
        with open(markdown_path, "r", encoding="utf-8") as f:
            md_content = f.read()

        if not md_content.strip():
            raise ValueError(f"Markdown file is empty: {markdown_path}")

        # Convert markdown to HTML with extensions
        html_content = markdown.markdown(
            md_content,
            extensions=[
                "tables",  # Support for tables
                "fenced_code",  # Support for code blocks
                "nl2br",  # Convert newlines to <br>
            ],
        )

        # Fix relative image paths to absolute for PDF rendering
        html_content = self._fix_image_paths(html_content, markdown_path.parent)

        # Wrap in HTML structure
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Research Swarm Report</title>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """

        # Generate PDF
        output_path.parent.mkdir(parents=True, exist_ok=True)
        HTML(string=full_html, base_url=str(markdown_path.parent)).write_pdf(
            output_path, stylesheets=[self.css]
        )

        return output_path

    def _fix_image_paths(self, html: str, base_dir: Path) -> str:
        """Convert relative image paths to absolute file:// URLs.

        Args:
            html: HTML content with relative image paths
            base_dir: Base directory for resolving relative paths

        Returns:
            HTML with absolute image paths
        """
        import re

        # Pattern to match image src attributes with relative paths
        pattern = r'src="(\./[^"]+)"'

        def replace_path(match):
            rel_path = match.group(1)
            # Remove leading './'
            clean_path = rel_path[2:] if rel_path.startswith("./") else rel_path
            # Convert to absolute path
            abs_path = (base_dir / clean_path).resolve()
            return f'src="file://{abs_path}"'

        return re.sub(pattern, replace_path, html)

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

        # Convert markdown to HTML
        html_content = markdown.markdown(
            markdown_content,
            extensions=["tables", "fenced_code", "nl2br"],
        )

        # Fix image paths if base_dir provided
        if base_dir:
            html_content = self._fix_image_paths(html_content, base_dir)

        # Wrap in HTML structure
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Research Swarm Report</title>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """

        # Generate PDF
        output_path.parent.mkdir(parents=True, exist_ok=True)
        base_url = str(base_dir) if base_dir else None
        HTML(string=full_html, base_url=base_url).write_pdf(
            output_path, stylesheets=[self.css]
        )

        return output_path
