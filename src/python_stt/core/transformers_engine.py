"""Whisper engine backed by Hugging Face transformers + PyTorch.

Exists so the app can run on AMD GPUs (PyTorch ROCm), which faster-whisper/CTranslate2 cannot use.
It mimics the ``WhisperModel.transcribe`` interface: it returns ``(segments_iterator, info)``.
torch and transformers are imported lazily because they are optional (``uv sync --extra gpu``).
"""

from collections.abc import Iterator
from types import SimpleNamespace

from faster_whisper import decode_audio

SAMPLE_RATE = 16000
CHUNK_SECONDS = 30
# The audio is fed to the pipeline in slices so progress can be reported between them.
SLICE_SECONDS = 300
BATCH_SIZE = 8


class TransformersWhisperModel:
    def __init__(self, model_size: str, device: str = "auto", compute_type: str = "default"):
        try:
            import torch
            from transformers import pipeline
        except ImportError as e:
            raise RuntimeError(
                "The 'transformers' engine needs the optional dependencies. Install them with "
                "`uv sync --extra gpu` and install a PyTorch build (ROCm for AMD GPUs)."
            ) from e

        # ROCm builds of PyTorch expose the AMD GPU through the "cuda" device name.
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        if compute_type == "default":
            compute_type = "float16" if device == "cuda" else "float32"

        dtypes = {"float16": torch.float16, "float32": torch.float32}
        if compute_type not in dtypes:
            raise ValueError(
                f"compute type '{compute_type}' is not supported by the 'transformers' engine "
                "(use 'float16' or 'float32')."
            )

        self._torch = torch
        self._device = device
        self._dtype = dtypes[compute_type]
        name = model_size if "/" in model_size else f"openai/whisper-{model_size}"
        self._pipe = pipeline(
            "automatic-speech-recognition",
            model=name,
            device=device,
            dtype=self._dtype,
            chunk_length_s=CHUNK_SECONDS,
            batch_size=BATCH_SIZE,
        )

    def transcribe(
        self,
        audio_path: str,
        language: str | None = None,
        beam_size: int = 5,
        vad_filter: bool = True,  # accepted for interface parity; not supported by this engine
    ) -> tuple[Iterator[SimpleNamespace], SimpleNamespace]:
        audio = decode_audio(audio_path, sampling_rate=SAMPLE_RATE)
        probability = 1.0
        if language is None:
            language, probability = self._detect_language(audio)
        info = SimpleNamespace(
            language=language,
            language_probability=probability,
            duration=len(audio) / SAMPLE_RATE,
        )
        return self._segments(audio, language, beam_size), info

    def _detect_language(self, audio) -> tuple[str, float]:
        """Detect the language from the first 30s, like Whisper does (softmax over lang tokens)."""
        torch = self._torch
        model = self._pipe.model
        features = self._pipe.feature_extractor(
            audio[: CHUNK_SECONDS * SAMPLE_RATE], sampling_rate=SAMPLE_RATE, return_tensors="pt"
        ).input_features.to(self._device, self._dtype)
        start_id = model.generation_config.decoder_start_token_id
        start = torch.tensor([[start_id]], device=self._device)
        with torch.no_grad():
            logits = model(input_features=features, decoder_input_ids=start).logits[0, -1]

        lang_to_id = model.generation_config.lang_to_id
        probs = torch.softmax(logits[list(lang_to_id.values())].float(), dim=-1)
        best = int(probs.argmax())
        return list(lang_to_id)[best].strip("<|>"), float(probs[best])

    def _segments(self, audio, language: str, beam_size: int) -> Iterator[SimpleNamespace]:
        generate_kwargs = {"language": language, "task": "transcribe", "num_beams": beam_size}
        step = SLICE_SECONDS * SAMPLE_RATE
        for offset in range(0, len(audio), step):
            piece = audio[offset : offset + step]
            base = offset / SAMPLE_RATE
            out = self._pipe(
                {"raw": piece, "sampling_rate": SAMPLE_RATE},
                return_timestamps=True,
                generate_kwargs=generate_kwargs,
            )
            for chunk in out["chunks"]:
                start, end = chunk["timestamp"]
                yield SimpleNamespace(
                    start=base + (start or 0.0),
                    end=base + (end if end is not None else len(piece) / SAMPLE_RATE),
                    text=chunk["text"],
                )
