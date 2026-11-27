import subprocess
from pathlib import Path

import pytest

from python_stt.core import uploader
from python_stt.core.uploader import UploadError, check_destination, upload_file


def _completed(returncode=0, stderr=""):
    return subprocess.CompletedProcess([], returncode, stdout="", stderr=stderr)


def test_upload_file_uses_copyto_and_returns_remote_path(monkeypatch, tmp_path: Path):
    calls = []
    monkeypatch.setattr(uploader.subprocess, "run", lambda a, **k: calls.append(a) or _completed())
    f = tmp_path / "lecture.html"

    remote = upload_file(f, "gdrive:folder/")

    assert remote == "gdrive:folder/lecture.html"
    assert calls == [["rclone", "copyto", str(f), "gdrive:folder/lecture.html"]]


def test_upload_failure_reports_last_stderr_line(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        uploader.subprocess, "run", lambda *a, **k: _completed(1, "x\nCouldn't find remote")
    )
    with pytest.raises(UploadError, match="Couldn't find remote"):
        upload_file(tmp_path / "a.html", "gd:d")


def test_check_destination_requires_rclone(monkeypatch):
    monkeypatch.setattr(uploader.shutil, "which", lambda name: None)
    with pytest.raises(UploadError, match="not installed"):
        check_destination("gd:d")


def test_check_destination_creates_folder(monkeypatch):
    calls = []
    monkeypatch.setattr(uploader.shutil, "which", lambda name: "/usr/bin/rclone")
    monkeypatch.setattr(uploader.subprocess, "run", lambda a, **k: calls.append(a) or _completed())
    check_destination("gd:d")
    assert calls == [["rclone", "mkdir", "gd:d"]]


@pytest.mark.parametrize(
    ("dest", "expected"),
    [("gd:", "gd:a.html"), ("gd:dir", "gd:dir/a.html"), ("gd:dir/", "gd:dir/a.html")],
)
def test_upload_target_path(monkeypatch, tmp_path: Path, dest, expected):
    monkeypatch.setattr(uploader.subprocess, "run", lambda *a, **k: _completed())
    assert upload_file(tmp_path / "a.html", dest) == expected
