from python_stt.core.models import (
    TranscriptionResult,
    TranscriptSegment,
    format_timestamp,
    merge_segments,
)


def test_format_timestamp():
    assert format_timestamp(0) == "00:00"
    assert format_timestamp(65) == "01:05"
    assert format_timestamp(3665) == "01:01:05"


def test_transcription_result_properties():
    segments = [
        TranscriptSegment(start=0.0, end=4.5, text="Hello world."),
        TranscriptSegment(start=5.0, end=10.2, text="This is a test."),
    ]
    result = TranscriptionResult(
        source_name="video.mp4",
        source_url_or_path="https://example.com/video.mp4",
        language="en",
        language_probability=0.98,
        duration=10.2,
        segments=segments,
    )

    assert result.full_text == "Hello world. This is a test."
    assert result.duration_formatted == "00:10"
    assert segments[0].start_formatted == "00:00"
    assert segments[1].end_formatted == "00:10"


def _segs(count: int, step: float = 5.0, text: str = "word") -> list[TranscriptSegment]:
    return [
        TranscriptSegment(start=i * step, end=(i + 1) * step, text=f"{text}{i}")
        for i in range(count)
    ]


def test_merge_segments_closes_block_at_sentence_end_after_min_seconds():
    segments = _segs(30)  # 150s of 5s segments, no punctuation
    segments[13].text = "end of sentence."  # block reaches 70s here (>= 60s)
    merged = merge_segments(segments)

    assert len(merged) == 2
    assert merged[0].start == 0.0 and merged[0].end == 70.0
    assert merged[0].text.endswith("end of sentence.")
    assert merged[1].start == 70.0 and merged[1].end == 150.0


def test_merge_segments_ignores_sentence_end_before_min_seconds():
    segments = _segs(8)
    segments[1].text = "short."
    merged = merge_segments(segments)

    assert len(merged) == 1
    assert merged[0].end == 40.0


def test_merge_segments_never_exceeds_five_minutes():
    merged = merge_segments(_segs(300))  # 1500s, no punctuation at all

    assert len(merged) == 5
    assert all(m.end - m.start <= 300 for m in merged)
    assert all(a.end == b.start for a, b in zip(merged, merged[1:], strict=False))


def test_merge_segments_skips_empty_and_handles_empty_input():
    assert merge_segments([]) == []
    assert merge_segments([TranscriptSegment(0.0, 1.0, "   ")]) == []


def test_display_segments_does_not_mutate_original_segments():
    result = TranscriptionResult(
        source_name="v.mp4",
        source_url_or_path="v.mp4",
        language="en",
        language_probability=0.9,
        duration=150.0,
        segments=_segs(30),
    )
    before = [(s.start, s.end, s.text) for s in result.segments]

    assert len(result.display_segments) < len(result.segments)
    assert [(s.start, s.end, s.text) for s in result.segments] == before
