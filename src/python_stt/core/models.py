from dataclasses import dataclass, field
from datetime import datetime


def format_timestamp(seconds: float) -> str:
    """Format seconds into HH:MM:SS or MM:SS string."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str

    @property
    def start_formatted(self) -> str:
        return format_timestamp(self.start)

    @property
    def end_formatted(self) -> str:
        return format_timestamp(self.end)


MIN_BLOCK_SECONDS = 60.0
MAX_BLOCK_SECONDS = 300.0

_SENTENCE_ENDINGS = (".", "?", "!", "…", "。", "？", "！")
_TRAILING_CLOSERS = "\"'”’)]»"


def _ends_sentence(text: str) -> bool:
    return text.rstrip().rstrip(_TRAILING_CLOSERS).endswith(_SENTENCE_ENDINGS)


def merge_segments(
    segments: list[TranscriptSegment],
    min_seconds: float = MIN_BLOCK_SECONDS,
    max_seconds: float = MAX_BLOCK_SECONDS,
) -> list[TranscriptSegment]:
    """Group consecutive Whisper segments into longer, human-readable blocks.

    A block is closed at the first sentence end once it spans at least ``min_seconds``.
    It is also closed early if adding the next segment would exceed ``max_seconds``.
    """
    merged: list[TranscriptSegment] = []
    current: TranscriptSegment | None = None

    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue

        if current is not None and seg.end - current.start > max_seconds:
            merged.append(current)
            current = None

        if current is None:
            current = TranscriptSegment(start=seg.start, end=seg.end, text=text)
        else:
            current.end = seg.end
            current.text = f"{current.text} {text}"

        if current.end - current.start >= min_seconds and _ends_sentence(current.text):
            merged.append(current)
            current = None

    if current is not None:
        merged.append(current)
    return merged


@dataclass
class TranscriptionResult:
    source_name: str
    source_url_or_path: str
    language: str
    language_probability: float
    duration: float
    segments: list[TranscriptSegment] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def display_segments(self) -> list[TranscriptSegment]:
        """Segments merged into longer blocks for the HTML report."""
        return merge_segments(self.segments)

    @property
    def full_text(self) -> str:
        return " ".join(seg.text.strip() for seg in self.segments if seg.text.strip())

    @property
    def duration_formatted(self) -> str:
        return format_timestamp(self.duration)
