from pathlib import Path

import httpx
import pytest

from python_stt.core.downloader import (
    convert_to_direct_url,
    download_media,
    extract_gdrive_file_id,
    get_filename_from_url,
    is_url,
    parse_filename_from_headers,
    resolve_media_source,
)


def test_is_url():
    assert is_url("https://example.com/video.mp4") is True
    assert is_url("http://example.com/video.mp4") is True
    assert is_url("/path/to/local/file.mp4") is False
    assert is_url("file.mp4") is False


def test_extract_gdrive_file_id():
    url1 = "https://drive.google.com/file/d/1KPldIQlOJJjC9ld93ILQW0KtsQt6QZUb/view"
    assert extract_gdrive_file_id(url1) == "1KPldIQlOJJjC9ld93ILQW0KtsQt6QZUb"

    url2 = "https://drive.google.com/open?id=1a2b3c4d5e"
    assert extract_gdrive_file_id(url2) == "1a2b3c4d5e"

    assert extract_gdrive_file_id("https://example.com/video.mp4") is None


def test_convert_to_direct_url():
    gdrive_url = "https://drive.google.com/file/d/1KPldIQlOJJjC9ld93ILQW0KtsQt6QZUb/view"
    direct = convert_to_direct_url(gdrive_url)
    assert "drive.usercontent.google.com/download?id=1KPldIQlOJJjC9ld93ILQW0KtsQt6QZUb" in direct

    plain_url = "https://example.com/video.mp4"
    assert convert_to_direct_url(plain_url) == plain_url


def test_parse_filename_from_headers():
    headers_std = httpx.Headers({"content-disposition": 'attachment; filename="my_video.mp4"'})
    assert parse_filename_from_headers(headers_std) == "my_video.mp4"

    headers_rfc = httpx.Headers(
        {"content-disposition": "attachment; filename*=UTF-8''special%20video.mp4"}
    )
    assert parse_filename_from_headers(headers_rfc) == "special video.mp4"


def test_get_filename_from_url():
    assert get_filename_from_url("https://example.com/folder/sample.mp4") == "sample.mp4"
    assert (
        get_filename_from_url("https://example.com/folder/sample%20video.mp4") == "sample video.mp4"
    )
    assert get_filename_from_url("https://example.com/no-extension") == "downloaded_video.mp4"


def test_resolve_media_source_local(tmp_path: Path):
    test_file = tmp_path / "local_video.mp4"
    test_file.write_bytes(b"dummy video content")

    scratch_dir = tmp_path / "scratch"
    resolved_path, display_name, is_temp = resolve_media_source(str(test_file), scratch_dir)

    assert resolved_path == test_file
    assert display_name == "local_video.mp4"
    assert is_temp is False


def test_resolve_media_source_missing_local():
    with pytest.raises(FileNotFoundError):
        resolve_media_source("/non/existent/file.mp4", Path("/tmp"))


def test_download_media_mock(monkeypatch, tmp_path: Path):
    url = "https://example.com/test.mp4"
    content = b"fake-video-bytes"

    class MockResponse:
        status_code = 200
        headers = httpx.Headers(
            {
                "content-type": "video/mp4",
                "content-disposition": 'attachment; filename="renamed_test.mp4"',
            }
        )

        def raise_for_status(self):
            pass

        def iter_bytes(self, chunk_size=131072):
            yield content

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        def stream(self, method, request_url):
            assert method == "GET"
            assert request_url == url
            return MockResponse()

    monkeypatch.setattr(httpx, "Client", MockClient)

    downloaded = download_media(url, tmp_path)
    assert downloaded.exists()
    assert downloaded.name == "renamed_test.mp4"
    assert downloaded.read_bytes() == content


def test_download_media_html_error(monkeypatch, tmp_path: Path):
    url = "https://example.com/page"

    class MockHtmlResponse:
        status_code = 200
        headers = httpx.Headers({"content-type": "text/html; charset=utf-8"})

        def raise_for_status(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        def stream(self, method, request_url):
            return MockHtmlResponse()

    monkeypatch.setattr(httpx, "Client", MockClient)

    with pytest.raises(ValueError, match="HTML page instead of a media file"):
        download_media(url, tmp_path)


def test_download_media_reports_progress(monkeypatch, tmp_path: Path):
    chunks = [b"a" * 10, b"b" * 5]

    class MockResponse:
        headers = httpx.Headers({"content-type": "video/mp4", "content-length": "15"})

        def raise_for_status(self):
            pass

        def iter_bytes(self, chunk_size=131072):
            yield from chunks

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def stream(self, method, request_url):
            return MockResponse()

    monkeypatch.setattr(httpx, "Client", MockClient)

    calls: list[tuple[int, int | None]] = []
    download_media(
        "https://example.com/v.mp4", tmp_path, lambda done, total: calls.append((done, total))
    )

    assert calls == [(0, 15), (10, 15), (15, 15)]
