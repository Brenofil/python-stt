import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from python_stt.core.transcriber import Transcriber


def test_transcribe_reports_progress(tmp_path: Path):
    segments = [
        SimpleNamespace(start=0.0, end=4.0, text=" Hello "),
        SimpleNamespace(start=4.0, end=10.0, text=" world "),
    ]
    info = SimpleNamespace(language="en", language_probability=0.9, duration=10.0)

    transcriber = Transcriber()
    transcriber._model = SimpleNamespace(transcribe=lambda *a, **k: (iter(segments), info))

    calls: list[tuple[float, float]] = []
    result = transcriber.transcribe(
        tmp_path / "x.mp4",
        "x.mp4",
        "x.mp4",
        on_progress=lambda done, total: calls.append((done, total)),
    )

    assert [s.text for s in result.segments] == ["Hello", "world"]
    assert calls[0] == (0.0, 10.0)
    assert calls[-1] == (10.0, 10.0)
    assert [c[0] for c in calls] == sorted(c[0] for c in calls)


def test_unknown_engine_is_rejected():
    with pytest.raises(ValueError, match="Unknown engine"):
        Transcriber(engine="nope")


def test_transformers_engine_without_extras_gives_clear_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", None)  # makes `import torch` raise ImportError
    transcriber = Transcriber(engine="transformers")
    with pytest.raises(RuntimeError, match="uv sync --extra gpu"):
        transcriber.load()
