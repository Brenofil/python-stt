"""Upload generated reports to a remote (e.g. Google Drive) with rclone."""

import shutil
import subprocess
from pathlib import Path


class UploadError(RuntimeError):
    pass


def _run(args: list[str]) -> None:
    try:
        proc = subprocess.run(args, capture_output=True, text=True, check=False)
    except OSError as e:
        raise UploadError(f"Cannot run rclone: {e}") from e
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        raise UploadError(detail[-1] if detail else f"rclone exited with {proc.returncode}")


def check_destination(dest: str) -> None:
    """Fail fast: make sure rclone exists and ``dest`` is reachable (creates the folder)."""
    if shutil.which("rclone") is None:
        raise UploadError("rclone is not installed or not on PATH.")
    _run(["rclone", "mkdir", dest])


def upload_file(path: Path, dest: str) -> str:
    """Copy ``path`` into the rclone folder ``dest`` and return the remote file location."""
    # A bare remote ("gdrive:") must not get a "/" or it would point at the filesystem root.
    target = f"{dest}{path.name}" if dest.endswith((":", "/")) else f"{dest}/{path.name}"
    _run(["rclone", "copyto", str(path), target])
    return target
