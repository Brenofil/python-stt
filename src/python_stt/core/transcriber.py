from collections.abc import Callable
from pathlib import Path

from faster_whisper import WhisperModel

from python_stt.core.models import TranscriptionResult, TranscriptSegment

ENGINES = ("faster-whisper", "transformers")


class Transcriber:
    def __init__(
        self,
        model_size: str = "base",
        device: str = "auto",
        compute_type: str = "default",
        engine: str = "faster-whisper",
    ):
        if engine not in ENGINES:
            raise ValueError(f"Unknown engine '{engine}'. Choose one of: {', '.join(ENGINES)}.")
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.engine = engine
        self._model: WhisperModel | None = None

    def load(self) -> None:
        """Load (and download, on first use) the Whisper model."""
        _ = self.model

    @property
    def model(self) -> WhisperModel:
        if self._model is None:
            if self.engine == "transformers":
                from python_stt.core.transformers_engine import TransformersWhisperModel

                model_cls = TransformersWhisperModel
            else:
                model_cls = WhisperModel
            self._model = model_cls(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
        return self._model

    def transcribe(
        self,
        media_path: Path,
        source_name: str,
        source_url_or_path: str,
        language: str | None = None,
        beam_size: int = 5,
        vad_filter: bool = True,
        on_progress: Callable[[float, float], None] | None = None,
    ) -> TranscriptionResult:
        """Transcribe an audio or video file and return a TranscriptionResult.

        ``on_progress(processed_seconds, total_seconds)`` is called after each segment.
        """
        segments_gen, info = self.model.transcribe(
            str(media_path),
            language=language,
            beam_size=beam_size,
            vad_filter=vad_filter,
        )

        total = float(info.duration)
        if on_progress:
            on_progress(0.0, total)

        segments: list[TranscriptSegment] = []
        for seg in segments_gen:
            segments.append(TranscriptSegment(start=seg.start, end=seg.end, text=seg.text.strip()))
            if on_progress:
                on_progress(min(seg.end, total), total)

        if on_progress:
            on_progress(total, total)

        return TranscriptionResult(
            source_name=source_name,
            source_url_or_path=source_url_or_path,
            language=info.language,
            language_probability=info.language_probability,
            duration=info.duration,
            segments=segments,
        )
