from pathlib import Path
from typing import Annotated

import typer


def transcribe(
    audio_file: Annotated[
        Path,
        typer.Argument(
            exists=True, dir_okay=False, readable=True, help="Audio file to transcribe."
        ),
    ],
) -> None:
    """Transcribe an audio file to text."""
    raise NotImplementedError("transcribe is not implemented yet")
