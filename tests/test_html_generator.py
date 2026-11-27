from pathlib import Path

from python_stt.core.html_generator import generate_html_report, get_template_content
from python_stt.core.models import TranscriptionResult, TranscriptSegment


def test_get_template_content():
    content = get_template_content()
    assert "<!DOCTYPE html>" in content
    assert "{{ result.source_name }}" in content


def test_generate_html_report(tmp_path: Path):
    segments = [
        TranscriptSegment(start=0.0, end=3.5, text="First segment text."),
        TranscriptSegment(start=3.5, end=7.0, text="Second segment text."),
    ]
    result = TranscriptionResult(
        source_name="demo.mp4",
        source_url_or_path="https://example.com/demo.mp4",
        language="en",
        language_probability=0.95,
        duration=7.0,
        segments=segments,
    )

    output_file = tmp_path / "reports" / "transcript.html"
    generated_path = generate_html_report(result, output_file)

    assert generated_path.exists()
    html_text = generated_path.read_text(encoding="utf-8")
    assert "demo.mp4" in html_text
    assert "First segment text." in html_text
    assert "Second segment text." in html_text
    assert "00:00" in html_text
    # Short segments are merged into a single block spanning 00:00 - 00:07
    assert "[00:00 - 00:07]" in html_text


def test_generate_html_report_merges_short_segments_into_fewer_cards(tmp_path: Path):
    segments = [
        TranscriptSegment(start=i * 5.0, end=(i + 1) * 5.0, text=f"Piece {i}.") for i in range(48)
    ]
    result = TranscriptionResult(
        source_name="long.mp4",
        source_url_or_path="long.mp4",
        language="en",
        language_probability=0.9,
        duration=240.0,
        segments=segments,
    )

    html_text = generate_html_report(result, tmp_path / "out.html").read_text(encoding="utf-8")

    assert html_text.count('<div class="segment-card">') == len(result.display_segments)
    assert html_text.count('<div class="segment-card">') < len(segments)
    assert "Piece 0. Piece 1." in html_text
