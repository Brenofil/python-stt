from pathlib import Path

import pytest

from python_stt.core import pdf_generator
from python_stt.core.pdf_generator import PdfError, generate_pdf_report


def test_pdf_is_written_next_to_html_with_same_name(tmp_path: Path, monkeypatch):
    calls = {}

    class FakeHTML:
        def __init__(self, filename):
            calls["src"] = filename

        def write_pdf(self, target):
            calls["dst"] = target
            Path(target).write_bytes(b"%PDF-fake")

    monkeypatch.setitem(__import__("sys").modules, "weasyprint", type("m", (), {"HTML": FakeHTML}))
    html = tmp_path / "AULA 1a.html"
    html.write_text("<html></html>", encoding="utf-8")

    pdf = generate_pdf_report(html)

    assert pdf == tmp_path / "AULA 1a.pdf"
    assert calls == {"src": str(html), "dst": str(pdf)}


def test_render_failure_raises_pdf_error_and_leaves_no_partial_file(tmp_path: Path, monkeypatch):
    class BrokenHTML:
        def __init__(self, filename):
            pass

        def write_pdf(self, target):
            Path(target).write_bytes(b"partial")
            raise RuntimeError("boom")

    monkeypatch.setitem(
        __import__("sys").modules, "weasyprint", type("m", (), {"HTML": BrokenHTML})
    )
    html = tmp_path / "a.html"
    html.write_text("x", encoding="utf-8")

    with pytest.raises(PdfError, match="boom"):
        generate_pdf_report(html)
    assert not (tmp_path / "a.pdf").exists()


def test_missing_weasyprint_raises_pdf_error(tmp_path: Path, monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "weasyprint", None)
    with pytest.raises(PdfError, match="unavailable"):
        generate_pdf_report(tmp_path / "a.html")


def test_module_exposes_public_api():
    assert callable(pdf_generator.generate_pdf_report)
