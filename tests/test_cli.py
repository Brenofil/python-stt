from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from python_stt import __version__
from python_stt.cli import app
from python_stt.core.models import TranscriptionResult, TranscriptSegment
from python_stt.core.transcriber import Transcriber

runner = CliRunner()


@pytest.fixture(autouse=True)
def _no_real_model(monkeypatch):
    """Never load or download a real Whisper model in CLI tests."""
    monkeypatch.setattr(Transcriber, "load", MagicMock())


@pytest.fixture(autouse=True)
def _no_real_pdf(monkeypatch):
    """CLI tests must not depend on Pango being installed; PDF rendering has its own tests."""
    from python_stt.commands import transcribe as cmd

    monkeypatch.setattr(cmd, "generate_pdf_report", lambda p: p.with_suffix(".pdf"))


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_help_lists_commands():
    result = runner.invoke(app, ["help"])
    assert result.exit_code == 0
    for name in ("config", "transcribe", "help"):
        assert name in result.output


def test_help_for_command():
    result = runner.invoke(app, ["help", "transcribe"])
    assert result.exit_code == 0
    assert "source" in result.output.lower()


def test_help_unknown_command():
    result = runner.invoke(app, ["help", "nope"])
    assert result.exit_code == 2


def test_transcribe_local_file(monkeypatch, tmp_path: Path):
    video_file = tmp_path / "sample.mp4"
    video_file.write_bytes(b"dummy")
    output_html = tmp_path / "output.html"

    mock_result = TranscriptionResult(
        source_name="sample.mp4",
        source_url_or_path=str(video_file),
        language="en",
        language_probability=0.99,
        duration=5.0,
        segments=[TranscriptSegment(start=0.0, end=5.0, text="Mock transcription test.")],
    )

    monkeypatch.setattr(
        Transcriber,
        "transcribe",
        MagicMock(return_value=mock_result),
    )

    result = runner.invoke(
        app,
        ["transcribe", str(video_file), "--output", str(output_html), "--model", "tiny"],
    )

    assert result.exit_code == 0
    assert "Transcription complete!" in result.output
    assert output_html.exists()
    assert "Mock transcription test." in output_html.read_text(encoding="utf-8")


def test_transcribe_default_output_goes_to_transcripts_dir(monkeypatch, tmp_path: Path):
    video_file = tmp_path / "sample.mp4"
    video_file.write_bytes(b"dummy")
    monkeypatch.chdir(tmp_path)

    mock_result = TranscriptionResult(
        source_name="sample.mp4",
        source_url_or_path=str(video_file),
        language="en",
        language_probability=0.99,
        duration=5.0,
        segments=[TranscriptSegment(start=0.0, end=5.0, text="Mock transcription test.")],
    )
    monkeypatch.setattr(Transcriber, "transcribe", MagicMock(return_value=mock_result))

    result = runner.invoke(app, ["transcribe", str(video_file), "--model", "tiny"])

    assert result.exit_code == 0
    assert (tmp_path / "transcripts" / "sample.html").exists()


def _mock_result(name: str) -> TranscriptionResult:
    return TranscriptionResult(
        source_name=name,
        source_url_or_path=name,
        language="en",
        language_probability=0.99,
        duration=5.0,
        segments=[TranscriptSegment(start=0.0, end=5.0, text="Mock transcription test.")],
    )


def test_transcribe_batch_summary_with_success_and_error(monkeypatch, tmp_path: Path):
    good = tmp_path / "good.mp4"
    good.write_bytes(b"dummy")
    missing = tmp_path / "missing.mp4"
    list_file = tmp_path / "list.txt"
    list_file.write_text(f"# comment\n\n{good}\n{missing}\n", encoding="utf-8")
    out_dir = tmp_path / "out"

    monkeypatch.setattr(Transcriber, "transcribe", MagicMock(return_value=_mock_result("good.mp4")))

    result = runner.invoke(app, ["transcribe", "-f", str(list_file), "-o", str(out_dir)])

    assert result.exit_code == 1
    assert "Summary" in result.output
    assert "good.mp4" in result.output and "Success" in result.output
    assert "Error" in result.output
    assert "1 succeeded, 1 failed." in result.output
    assert (out_dir / "good.html").exists()


def test_transcribe_batch_same_name_does_not_overwrite(monkeypatch, tmp_path: Path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    first = tmp_path / "a" / "video.mp4"
    second = tmp_path / "b" / "video.mp4"
    first.write_bytes(b"dummy")
    second.write_bytes(b"dummy")
    list_file = tmp_path / "list.txt"
    list_file.write_text(f"{first}\n{second}\n", encoding="utf-8")
    out_dir = tmp_path / "out"

    monkeypatch.setattr(
        Transcriber, "transcribe", MagicMock(return_value=_mock_result("video.mp4"))
    )

    result = runner.invoke(app, ["transcribe", "-f", str(list_file), "-o", str(out_dir)])

    assert result.exit_code == 0
    assert (out_dir / "video.html").exists()
    assert (out_dir / "video-2.html").exists()


def test_transcribe_requires_exactly_one_of_source_or_input_file(tmp_path: Path):
    list_file = tmp_path / "list.txt"
    list_file.write_text("x\n", encoding="utf-8")

    assert runner.invoke(app, ["transcribe"]).exit_code == 2
    assert runner.invoke(app, ["transcribe", "x.mp4", "-f", str(list_file)]).exit_code == 2


def test_dotenv_is_loaded_without_overriding_shell(monkeypatch, tmp_path: Path):
    import os

    from dotenv import load_dotenv

    env_file = tmp_path / ".env"
    env_file.write_text("HF_TOKEN=from_file\nOTHER_VAR=from_file\n", encoding="utf-8")
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setenv("OTHER_VAR", "from_shell")

    load_dotenv(env_file)

    assert os.environ["HF_TOKEN"] == "from_file"
    assert os.environ["OTHER_VAR"] == "from_shell"
    monkeypatch.delenv("HF_TOKEN", raising=False)


def _fake_rclone(monkeypatch, fail_upload: bool = False):
    """Replace the rclone calls in the transcribe command; returns the list of uploads."""
    from python_stt.commands import transcribe as cmd
    from python_stt.core.uploader import UploadError

    uploaded: list[tuple[str, str]] = []

    def fake_upload(path, dest):
        if fail_upload:
            raise UploadError("boom")
        uploaded.append((path.name, dest))
        return f"{dest}/{path.name}"

    monkeypatch.setattr(cmd, "check_destination", lambda dest: None)
    monkeypatch.setattr(cmd, "upload_file", fake_upload)
    return uploaded


def test_batch_uploads_each_report_right_after_generation(monkeypatch, tmp_path: Path):
    for name in ("a.mp4", "b.mp4"):
        (tmp_path / name).write_bytes(b"dummy")
    list_file = tmp_path / "list.txt"
    list_file.write_text(f"{tmp_path / 'a.mp4'}\n{tmp_path / 'b.mp4'}\n", encoding="utf-8")
    monkeypatch.setattr(Transcriber, "transcribe", MagicMock(return_value=_mock_result("x.mp4")))
    uploaded = _fake_rclone(monkeypatch)

    result = runner.invoke(
        app,
        ["transcribe", "-f", str(list_file), "-o", str(tmp_path / "out"), "--upload-to", "gd:dir"],
    )

    assert result.exit_code == 0
    # Each item uploads its HTML and its PDF, in order, as soon as it is done.
    assert uploaded == [
        ("a.html", "gd:dir"),
        ("a.pdf", "gd:dir"),
        ("b.html", "gd:dir"),
        ("b.pdf", "gd:dir"),
    ]


def test_failed_upload_keeps_file_and_exits_nonzero(monkeypatch, tmp_path: Path):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"dummy")
    out = tmp_path / "v.html"
    monkeypatch.setattr(Transcriber, "transcribe", MagicMock(return_value=_mock_result("v.mp4")))
    _fake_rclone(monkeypatch, fail_upload=True)

    result = runner.invoke(app, ["transcribe", str(video), "-o", str(out), "--upload-to", "gd:d"])

    assert result.exit_code == 1
    assert "Upload failed" in result.output
    assert out.exists()


def test_unreachable_upload_destination_aborts_before_loading_model(monkeypatch, tmp_path: Path):
    from python_stt.commands import transcribe as cmd
    from python_stt.core.uploader import UploadError

    def bad_check(dest):
        raise UploadError("no remote")

    monkeypatch.setattr(cmd, "check_destination", bad_check)
    video = tmp_path / "v.mp4"
    video.write_bytes(b"dummy")

    result = runner.invoke(app, ["transcribe", str(video), "--upload-to", "gd:d"])

    assert result.exit_code == 1
    assert "Cannot use upload destination" in result.output
    Transcriber.load.assert_not_called()


def test_pdf_is_generated_and_uploaded_with_html(monkeypatch, tmp_path: Path):
    from python_stt.commands import transcribe as cmd

    video = tmp_path / "v.mp4"
    video.write_bytes(b"dummy")
    monkeypatch.setattr(Transcriber, "transcribe", MagicMock(return_value=_mock_result("v.mp4")))
    monkeypatch.setattr(cmd, "generate_pdf_report", lambda p: p.with_suffix(".pdf"))
    uploaded = _fake_rclone(monkeypatch)

    result = runner.invoke(
        app, ["transcribe", str(video), "-o", str(tmp_path / "v.html"), "--upload-to", "gd:"]
    )

    assert result.exit_code == 0
    assert "PDF Output" in result.output
    assert [name for name, _ in uploaded] == ["v.html", "v.pdf"]


def test_no_pdf_flag_skips_pdf(monkeypatch, tmp_path: Path):
    from python_stt.commands import transcribe as cmd

    video = tmp_path / "v.mp4"
    video.write_bytes(b"dummy")
    monkeypatch.setattr(Transcriber, "transcribe", MagicMock(return_value=_mock_result("v.mp4")))
    called = MagicMock()
    monkeypatch.setattr(cmd, "generate_pdf_report", called)

    result = runner.invoke(
        app, ["transcribe", str(video), "-o", str(tmp_path / "v.html"), "--no-pdf"]
    )

    assert result.exit_code == 0
    called.assert_not_called()


def test_pdf_failure_keeps_html_still_uploads_it_and_exits_nonzero(monkeypatch, tmp_path: Path):
    from python_stt.commands import transcribe as cmd
    from python_stt.core.pdf_generator import PdfError

    video = tmp_path / "v.mp4"
    video.write_bytes(b"dummy")
    out = tmp_path / "v.html"
    monkeypatch.setattr(Transcriber, "transcribe", MagicMock(return_value=_mock_result("v.mp4")))

    def broken(path):
        raise PdfError("no pango")

    monkeypatch.setattr(cmd, "generate_pdf_report", broken)
    uploaded = _fake_rclone(monkeypatch)

    result = runner.invoke(app, ["transcribe", str(video), "-o", str(out), "--upload-to", "gd:"])

    assert result.exit_code == 1
    assert "PDF not generated" in result.output
    assert out.exists()
    assert [name for name, _ in uploaded] == ["v.html"]
