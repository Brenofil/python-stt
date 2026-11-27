# CPU image (faster-whisper). For AMD GPUs use Dockerfile.rocm.
FROM python:3.12-slim

# PDF export (WeasyPrint): Pango for layout, DejaVu/Liberation for text incl. accents
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpango-1.0-0 libpangoft2-1.0-0 \
       fonts-dejavu-core fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
# rclone uploads finished transcripts (see --upload-to)
COPY --from=rclone/rclone:latest /usr/local/bin/rclone /usr/local/bin/rclone

WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

ENV PATH="/app/.venv/bin:$PATH" \
    HF_HOME=/cache/hf \
    RCLONE_CONFIG=/config/rclone/rclone.conf

# Inputs and outputs live in /data (mount it). Transcripts go to /data/transcripts.
WORKDIR /data
ENTRYPOINT ["stt"]
CMD ["--help"]
