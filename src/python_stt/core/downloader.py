import re
from collections.abc import Callable
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import httpx


def is_url(source: str) -> bool:
    """Check if the given source string is an HTTP/HTTPS URL."""
    try:
        parsed = urlparse(source)
        return parsed.scheme in ("http", "https")
    except Exception:
        return False


def extract_gdrive_file_id(url: str) -> str | None:
    """Extract file ID from various Google Drive URL formats."""
    # Pattern: /file/d/<file_id>
    match = re.search(r"/file/d/([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1)

    # Pattern: id=<file_id>
    parsed = urlparse(url)
    if "drive.google.com" in parsed.netloc or "docs.google.com" in parsed.netloc:
        query_params = parse_qs(parsed.query)
        if "id" in query_params:
            return query_params["id"][0]

    return None


def convert_to_direct_url(url: str) -> str:
    """Transform Google Drive viewer/sharing URLs into direct download links."""
    file_id = extract_gdrive_file_id(url)
    if file_id:
        return (
            f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"
        )
    return url


def parse_filename_from_headers(headers: httpx.Headers) -> str | None:
    """Extract filename from Content-Disposition header if available."""
    cd = headers.get("content-disposition", "")
    if not cd:
        return None

    # Handle RFC 5987 filename*=UTF-8''filename.ext
    rfc_match = re.search(r"filename\*=UTF-8''([^;]+)", cd, re.IGNORECASE)
    if rfc_match:
        return unquote(rfc_match.group(1))

    # Handle standard filename="filename.ext" or filename=filename.ext
    std_match = re.search(r'filename="?([^";]+)"?', cd, re.IGNORECASE)
    if std_match:
        return std_match.group(1).strip()

    return None


def get_filename_from_url(url: str, default: str = "downloaded_video.mp4") -> str:
    """Extract filename from URL path, or return default."""
    parsed = urlparse(url)
    path = unquote(parsed.path)
    name = Path(path).name
    if not name or "." not in name:
        return default
    return name


def download_media(
    url: str,
    destination_dir: Path,
    on_progress: Callable[[int, int | None], None] | None = None,
) -> Path:
    """
    Download media from a public URL (including Google Drive links) to a destination directory.

    ``on_progress(downloaded_bytes, total_bytes)`` is called as data arrives. ``total_bytes``
    is None when the server does not send a Content-Length header.
    """
    destination_dir.mkdir(parents=True, exist_ok=True)
    direct_url = convert_to_direct_url(url)
    initial_filename = get_filename_from_url(url)

    # Generous timeout for large video downloads (5 min read timeout per chunk)
    timeout = httpx.Timeout(connect=30.0, read=300.0, write=30.0, pool=30.0)

    with httpx.Client(follow_redirects=True, timeout=timeout) as client:
        with client.stream("GET", direct_url) as response:
            response.raise_for_status()

            # Check if response returned HTML (e.g. permission denied or web page)
            content_type = response.headers.get("content-type", "").lower()
            if "text/html" in content_type:
                raise ValueError(
                    "The URL returned an HTML page instead of a media file. "
                    "Ensure the Google Drive file is shared with 'Anyone with the link' as Viewer."
                )

            header_filename = parse_filename_from_headers(response.headers)
            filename = header_filename or initial_filename
            if not filename or "." not in filename:
                filename = "downloaded_video.mp4"

            destination = destination_dir / filename

            content_length = response.headers.get("content-length", "")
            total = int(content_length) if content_length.isdigit() else None
            downloaded = 0
            if on_progress:
                on_progress(downloaded, total)

            with open(destination, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=128 * 1024):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if on_progress:
                        on_progress(downloaded, total)

    return destination


def resolve_media_source(
    source: str,
    scratch_dir: Path,
    on_progress: Callable[[int, int | None], None] | None = None,
) -> tuple[Path, str, bool]:
    """
    Resolves source (URL or local path) to a local Path.
    Returns (local_file_path, display_name, is_temporary).
    """
    if is_url(source):
        downloaded_file = download_media(source, scratch_dir, on_progress)
        return downloaded_file, downloaded_file.name, True

    local_path = Path(source)
    if not local_path.exists():
        raise FileNotFoundError(f"File not found: {source}")
    if not local_path.is_file():
        raise ValueError(f"Source must be a file, not a directory: {source}")

    return local_path, local_path.name, False
