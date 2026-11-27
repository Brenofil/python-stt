"""Render the HTML report to a PDF stored next to it (same name, ``.pdf`` extension)."""

from pathlib import Path


class PdfError(RuntimeError):
    pass


def generate_pdf_report(html_path: Path) -> Path:
    """Convert ``html_path`` to ``<same name>.pdf`` in the same folder and return its path."""
    try:
        # Imported lazily: it needs Pango at the OS level, and a missing library must not
        # break the rest of the CLI.
        from weasyprint import HTML
    except (ImportError, OSError) as e:
        raise PdfError(f"PDF export is unavailable (WeasyPrint/Pango not installed): {e}") from e

    pdf_path = html_path.with_suffix(".pdf")
    try:
        HTML(filename=str(html_path)).write_pdf(str(pdf_path))
    except Exception as e:
        pdf_path.unlink(missing_ok=True)
        raise PdfError(f"Could not render PDF: {e}") from e
    return pdf_path
