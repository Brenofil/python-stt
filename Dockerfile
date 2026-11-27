# CPU image (faster-whisper). For AMD GPUs use Dockerfile.rocm.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

ENV PATH="/app/.venv/bin:$PATH" \
    HF_HOME=/cache/hf

# Inputs and outputs live in /data (mount it). Transcripts go to /data/transcripts.
WORKDIR /data
ENTRYPOINT ["stt"]
CMD ["--help"]
