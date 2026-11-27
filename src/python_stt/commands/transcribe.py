import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markup import escape
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from python_stt.core.downloader import is_url, resolve_media_source
from python_stt.core.html_generator import generate_html_report
from python_stt.core.models import TranscriptionResult
from python_stt.core.pdf_generator import PdfError, generate_pdf_report
from python_stt.core.transcriber import Transcriber
from python_stt.core.uploader import UploadError, check_destination, upload_file

DEFAULT_OUTPUT_DIR = "transcripts"

STATUS_SUCCESS = "Success"
STATUS_ERROR = "Error"


@dataclass
class _Outcome:
    name: str
    result: TranscriptionResult | None = None
    output_path: Path | None = None
    pdf_path: Path | None = None
    pdf_failed: bool = False
    upload_failed: bool = False

    @property
    def ok(self) -> bool:
        return self.result is not None


def _resolve_with_progress(source: str, scratch_dir: Path) -> tuple[Path, str, bool]:
    """Resolve a local path or download a URL, showing a progress bar for downloads."""
    if not is_url(source):
        return resolve_media_source(source, scratch_dir)

    with Progress(
        SpinnerColumn(),
        TextColumn("Downloading"),
        BarColumn(),
        TaskProgressColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        transient=True,
    ) as progress:
        task = progress.add_task("download", total=None)

        def on_progress(downloaded: int, total: int | None) -> None:
            progress.update(task, completed=downloaded, total=total)

        return resolve_media_source(source, scratch_dir, on_progress)


def _transcribe_with_progress(
    transcriber: Transcriber,
    display_name: str,
    **kwargs,
) -> TranscriptionResult:
    """Run the transcription with a progress bar based on processed audio seconds."""
    with Progress(
        SpinnerColumn(),
        TextColumn(f"Transcribing {escape(display_name)}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TextColumn("ETA"),
        TimeRemainingColumn(),
        transient=True,
    ) as progress:
        task = progress.add_task("transcribe", total=None)

        def on_progress(processed: float, total: float) -> None:
            progress.update(task, completed=processed, total=total or None)

        return transcriber.transcribe(on_progress=on_progress, **kwargs)


def _read_sources(input_file: Path) -> list[str]:
    """Read one source per line, ignoring blank lines and lines starting with '#'."""
    try:
        lines = input_file.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        typer.secho(f"Cannot read input file: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    sources = [line.strip() for line in lines]
    return [s for s in sources if s and not s.startswith("#")]


def _unique_path(path: Path, used: set[Path]) -> Path:
    """Avoid overwriting a file produced earlier in the same run (name collisions)."""
    candidate = path
    counter = 2
    while candidate in used:
        candidate = path.with_name(f"{path.stem}-{counter}{path.suffix}")
        counter += 1
    used.add(candidate)
    return candidate


def _process_source(
    source: str,
    output: Path | None,
    batch: bool,
    used_outputs: set[Path],
    transcriber: Transcriber,
    language: str | None,
    upload_to: str | None = None,
    make_pdf: bool = True,
) -> _Outcome:
    """Transcribe one source. Errors are reported to stderr and returned, never raised."""
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            if is_url(source):
                typer.echo(f"Downloading media from: {source}")
            local_path, display_name, _ = _resolve_with_progress(source, Path(temp_dir))
        except Exception as e:
            typer.secho(f"Error fetching media source: {e}", fg=typer.colors.RED, err=True)
            return _Outcome(name=source)

        base_name = Path(display_name).stem
        if batch:
            out_dir = output if output is not None else Path.cwd() / DEFAULT_OUTPUT_DIR
            output_path = _unique_path(out_dir / f"{base_name}.html", used_outputs)
        elif output is None:
            output_path = Path.cwd() / DEFAULT_OUTPUT_DIR / f"{base_name}.html"
        elif output.is_dir() or str(output).endswith(("/", "\\")):
            output_path = output / f"{base_name}.html"
        else:
            output_path = output

        typer.echo(f"Transcribing '{display_name}'...")
        try:
            result = _transcribe_with_progress(
                transcriber,
                display_name,
                media_path=local_path,
                source_name=display_name,
                source_url_or_path=source,
                language=language,
            )
            typer.echo(f"Generating HTML report at '{output_path}'...")
            generated_file = generate_html_report(result, output_path)
        except Exception as e:
            typer.secho(f"Transcription failed: {e}", fg=typer.colors.RED, err=True)
            return _Outcome(name=display_name)

        outcome = _Outcome(name=display_name, result=result, output_path=generated_file)
        if make_pdf:
            # A PDF problem never costs us the HTML: it is already written at this point.
            try:
                outcome.pdf_path = generate_pdf_report(generated_file)
                typer.echo(f"Generated PDF at '{outcome.pdf_path}'.")
            except PdfError as e:
                typer.secho(f"PDF not generated (HTML kept): {e}", fg=typer.colors.RED, err=True)
                outcome.pdf_failed = True
        if upload_to:
            # Reports are uploaded right away so finished work is safe if a later item fails.
            for path in (generated_file, outcome.pdf_path):
                if path is None:
                    continue
                try:
                    remote = upload_file(path, upload_to)
                    typer.echo(f"Uploaded to '{remote}'.")
                except UploadError as e:
                    typer.secho(
                        f"Upload failed (file kept locally): {e}", fg=typer.colors.RED, err=True
                    )
                    outcome.upload_failed = True
        return outcome


def _print_summary(outcomes: list[_Outcome]) -> None:
    width = max(len("File"), *(len(o.name) for o in outcomes))
    rule = f"+-{'-' * width}-+-{'-' * len(STATUS_SUCCESS)}-+"

    typer.echo("\nSummary")
    typer.echo(rule)
    typer.echo(f"| {'File'.ljust(width)} | {'Status'.ljust(len(STATUS_SUCCESS))} |")
    typer.echo(rule)
    for outcome in outcomes:
        status = STATUS_SUCCESS if outcome.ok else STATUS_ERROR
        color = typer.colors.GREEN if outcome.ok else typer.colors.RED
        cell = typer.style(status.ljust(len(STATUS_SUCCESS)), fg=color)
        typer.echo(f"| {outcome.name.ljust(width)} | {cell} |")
    typer.echo(rule)

    succeeded = sum(o.ok for o in outcomes)
    typer.echo(f"{succeeded} succeeded, {len(outcomes) - succeeded} failed.")
    pdf_failures = sum(o.pdf_failed for o in outcomes)
    if pdf_failures:
        typer.secho(f"{pdf_failures} PDF(s) could not be generated.", fg=typer.colors.RED)
    upload_failures = sum(o.upload_failed for o in outcomes)
    if upload_failures:
        typer.secho(f"{upload_failures} upload(s) failed.", fg=typer.colors.RED)


def transcribe(
    source: Annotated[
        str | None,
        typer.Argument(
            help=(
                "Audio/video file path or public HTTP/HTTPS URL to transcribe. "
                "Omit when using --input-file."
            ),
        ),
    ] = None,
    input_file: Annotated[
        Path | None,
        typer.Option(
            "--input-file",
            "-f",
            help=(
                "Text file with one file path or URL per line (blank lines and lines "
                "starting with '#' are ignored). Enables batch mode."
            ),
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help=(
                "Path to save the generated HTML transcript (a directory in batch mode). "
                f"Defaults to {DEFAULT_OUTPUT_DIR}/<filename>.html (git-ignored)."
            ),
        ),
    ] = None,
    model: Annotated[
        str,
        typer.Option(
            "--model",
            "-m",
            help="Whisper model size (tiny, base, small, medium, large-v3).",
        ),
    ] = "base",
    language: Annotated[
        str | None,
        typer.Option(
            "--language",
            "-l",
            help="Language spoken in the audio (e.g. 'en', 'pt', 'es'). Auto-detected if omitted.",
        ),
    ] = None,
    device: Annotated[
        str,
        typer.Option(
            "--device",
            help="Device to use for inference ('auto', 'cpu', 'cuda').",
        ),
    ] = "auto",
    compute_type: Annotated[
        str,
        typer.Option(
            "--compute-type",
            help="Compute type ('default', 'int8', 'float16', 'float32').",
        ),
    ] = "default",
    engine: Annotated[
        str,
        typer.Option(
            "--engine",
            help=(
                "Inference engine: 'faster-whisper' (CPU/NVIDIA) or 'transformers' "
                "(PyTorch; use it for AMD GPUs with ROCm, needs `uv sync --extra gpu`)."
            ),
        ),
    ] = "faster-whisper",
    pdf: Annotated[
        bool,
        typer.Option(
            "--pdf/--no-pdf",
            help="Also write a PDF next to each HTML report (same name, .pdf).",
        ),
    ] = True,
    upload_to: Annotated[
        str | None,
        typer.Option(
            "--upload-to",
            envvar="STT_UPLOAD_TO",
            help=(
                "rclone destination (e.g. 'gdrive:stt-transcripts'). Each report (HTML and "
                "PDF) is uploaded right after it is generated. Requires rclone configured."
            ),
        ),
    ] = None,
) -> None:
    """Transcribe audio/video from a local path, public URL, or a list file, into HTML reports."""
    if (source is None) == (input_file is None):
        raise typer.BadParameter("Provide either a SOURCE argument or --input-file, not both.")

    batch = input_file is not None
    sources = _read_sources(input_file) if input_file is not None else [source or ""]
    if not sources:
        typer.secho(f"No sources found in '{input_file}'.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    if upload_to:
        try:
            check_destination(upload_to)
        except UploadError as e:
            typer.secho(
                f"Cannot use upload destination '{upload_to}': {e}", fg=typer.colors.RED, err=True
            )
            raise typer.Exit(code=1) from e

    typer.echo(f"Loading Whisper model '{model}' on device '{device}' (engine: {engine})...")
    try:
        transcriber = Transcriber(
            model_size=model, device=device, compute_type=compute_type, engine=engine
        )
    except ValueError as e:
        raise typer.BadParameter(str(e)) from e
    try:
        with Console().status("Loading model (the first run downloads it)..."):
            transcriber.load()
    except Exception as e:
        typer.secho(f"Failed to load Whisper model: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    used_outputs: set[Path] = set()
    outcomes: list[_Outcome] = []
    for index, item in enumerate(sources, start=1):
        if batch:
            typer.echo(f"\n[{index}/{len(sources)}] {item}")
        outcomes.append(
            _process_source(
                item, output, batch, used_outputs, transcriber, language, upload_to, pdf
            )
        )

    if batch:
        _print_summary(outcomes)
        if not all(o.ok and not o.upload_failed and not o.pdf_failed for o in outcomes):
            raise typer.Exit(code=1)
        return

    outcome = outcomes[0]
    if outcome.result is None or outcome.output_path is None:
        raise typer.Exit(code=1)
    problem = outcome.upload_failed or outcome.pdf_failed

    result = outcome.result
    typer.secho(
        f"Transcription complete!\n"
        f"  - Detected Language: {result.language} ({result.language_probability * 100:.1f}%)\n"
        f"  - Duration: {result.duration_formatted}\n"
        f"  - Segments: {len(result.segments)}\n"
        f"  - HTML Output: {outcome.output_path.resolve()}"
        + (f"\n  - PDF Output: {outcome.pdf_path.resolve()}" if outcome.pdf_path else ""),
        fg=typer.colors.GREEN,
    )
    if problem:
        raise typer.Exit(code=1)
