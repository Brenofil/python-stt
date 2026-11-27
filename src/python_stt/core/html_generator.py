from importlib import resources
from pathlib import Path

from jinja2 import Template

from python_stt.core.models import TranscriptionResult


def get_template_content() -> str:
    """Load the HTML template from the package templates directory."""
    try:
        # Standard Python 3.11+ resources API
        template_file = resources.files("python_stt").joinpath(
            "templates", "transcription-template.html"
        )
        return template_file.read_text(encoding="utf-8")
    except Exception:
        # Fallback to direct path relative to this file
        template_path = (
            Path(__file__).resolve().parent.parent / "templates" / "transcription-template.html"
        )
        return template_path.read_text(encoding="utf-8")


def generate_html_report(result: TranscriptionResult, output_path: Path) -> Path:
    """Render a TranscriptionResult to an HTML document and save to output_path."""
    template_content = get_template_content()
    template = Template(template_content)
    html_content = template.render(result=result)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_content, encoding="utf-8")
    return output_path
