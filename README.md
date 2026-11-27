# python-stt

Speech-to-text command line application built with [Typer](https://typer.tiangolo.com/). It transcribes audio/video (local file or public URL) with [faster-whisper](https://github.com/SYSTRAN/faster-whisper) and generates an HTML transcript.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Internet access on the first run (the Whisper model is downloaded and cached automatically)

## Setup

```bash
git clone git@github.com:Brenofil/python-stt.git
cd python-stt
uv sync
```

`uv sync` creates a `.venv` and installs the project and its dependencies, including the dev tools. The `stt` command is registered by `pyproject.toml`.

## Running the CLI

Pick one of the options below. All of them run the same application.

**1. With `uv run` (no activation needed)**

```bash
uv run stt --help
```

**2. With the virtual environment activated**

```bash
source .venv/bin/activate
stt --help
```

**3. As a Python module**

```bash
uv run python -m python_stt --help
```

**4. Installed globally** (the `stt` command is then available from any directory, and code changes are picked up because the install is editable)

```bash
uv tool install --editable .
stt --help
```

To remove it: `uv tool uninstall python-stt`. If `stt` is not found after installing, run `uv tool update-shell` and restart your shell.

## Hugging Face token (optional)

The Whisper model is downloaded from the Hugging Face Hub on the first run. To avoid the "unauthenticated requests" warning and get faster downloads, copy `.env.example` to `.env` and set your token:

```bash
cp .env.example .env
# then edit .env and set HF_TOKEN=hf_xxx
```

`.env` is git-ignored and is loaded automatically by `stt`. A variable already exported in your shell takes precedence.

## Transcribing a video

The examples below use the `stt` command. Prefix them with `uv run` if you have not activated the virtual environment or installed the tool.

**From a local file** (any audio/video format supported by ffmpeg/PyAV, e.g. mp4, mkv, mp3, wav):

```bash
stt transcribe path/to/video.mp4
```

**From a public URL** (direct links or Google Drive; Drive files must be shared as "Anyone with the link" can view):

```bash
stt transcribe "https://example.com/video.mp4"
stt transcribe "https://drive.google.com/file/d/<FILE_ID>/view"
```

The result is an HTML file saved to `./transcripts/<video-name>.html` (relative to the directory where you run the command). The `transcripts/` directory is created automatically and is listed in `.gitignore`, so transcripts are never committed.

While running, the CLI shows a spinner while the Whisper model loads, a download progress bar (size, speed, ETA) for URLs, and a transcription progress bar (processed audio time, elapsed, ETA) for each file.

### Batch mode (list of files/URLs)

Put one file path or URL per line in a `.txt` file. Blank lines and lines starting with `#` are ignored.

```text
# urls.txt
https://example.com/lecture1.mp4
https://drive.google.com/file/d/<FILE_ID>/view
/path/to/local/lecture3.mkv
```

```bash
stt transcribe --input-file urls.txt --model small --language pt
```

The Whisper model is loaded once and every item is processed in order. A failure on one item does not stop the run. When it finishes, a summary table is printed:

```text
Summary
+--------------+---------+
| File         | Status  |
+--------------+---------+
| lecture1.mp4 | Success |
| <FILE_ID>    | Error   |
+--------------+---------+
1 succeeded, 1 failed.
```

All transcripts are saved to `transcripts/` (or the directory given with `--output`). If two items have the same name, the later ones get a `-2`, `-3`... suffix instead of overwriting. The command exits with code 1 if any item failed.

### Options

| Option | Short | Default | Description |
| --- | --- | --- | --- |
| `--input-file PATH` | `-f` | none | Text file with one file/URL per line (batch mode). Use instead of `SOURCE`. |
| `--output PATH` | `-o` | `transcripts/<name>.html` | HTML file path, or a directory to save into (always a directory in batch mode). |
| `--model NAME` | `-m` | `base` | Whisper model: `tiny`, `base`, `small`, `medium`, `large-v3`. Larger is more accurate but slower. |
| `--language CODE` | `-l` | auto-detect | Spoken language, e.g. `en`, `pt`, `es`. |
| `--device NAME` | | `auto` | `auto`, `cpu` or `cuda`. |
| `--compute-type TYPE` | | `default` | `default`, `int8`, `float16` or `float32`. |
| `--engine NAME` | | `faster-whisper` | `faster-whisper` (CPU/NVIDIA) or `transformers` (PyTorch, for AMD GPUs via ROCm). |

Example:

```bash
stt transcribe lecture.mp4 --model small --language pt --output transcripts/lecture.html
```

> If you pass `--output` with a path outside `transcripts/`, make sure the file is not committed by accident.

### Other commands

```bash
stt --help                         # list all commands
stt --version                      # show the version
stt help [COMMAND]                 # help for the app or a specific command
stt config                         # not implemented yet
```

## Running in a container

`faster-whisper` (CTranslate2) cannot use AMD GPUs. For those, the `transformers` engine runs Whisper on PyTorch ROCm. Two images are provided; input files go in `./media` and transcripts are written to `./transcripts`.

**CPU** (any host):

```bash
docker compose run --rm stt-cpu transcribe /data/media/file.mp4 --model small --compute-type int8
```

**AMD GPU** (Ubuntu host with the `amdgpu` kernel driver; ROCm itself is inside the image):

```bash
docker compose run --rm stt-rocm transcribe /data/media/file.mp4 --engine transformers --model large-v3
```

`Dockerfile.rocm` sets `HSA_OVERRIDE_GFX_VERSION=11.0.0` so the RX 7600 (gfx1102) uses the gfx1100 kernels. It is a safety net, so remove it if your GPU is detected without it. The model cache lives in the `hf-cache` volume, and `HF_TOKEN` is read from `.env` when present. The user running Docker must have access to `/dev/kfd` and `/dev/dri` (groups `video` and `render`).

To use the `transformers` engine outside Docker: install a PyTorch build for your hardware, then `uv sync --extra gpu`.

## Development

```bash
uv run pytest          # tests
uv run ruff check .    # lint
uv run ruff format .   # format
```

## Project structure

```
.
├── pyproject.toml
├── src/python_stt/
│   ├── cli.py            # Typer app and command registration
│   ├── config.py         # settings
│   ├── commands/         # CLI commands (thin layer)
│   ├── core/             # business logic
│   └── integrations/     # external STT engines / services
├── tests/
└── docs/
```

## License

MIT, see [LICENSE](LICENSE).
