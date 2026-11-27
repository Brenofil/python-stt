# python-stt

Speech-to-text command line application built with [Typer](https://typer.tiangolo.com/). It transcribes audio/video (local file or public URL) with [faster-whisper](https://github.com/SYSTRAN/faster-whisper) and generates an HTML transcript and a PDF copy of it.

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

## PDF export

Every transcript is also saved as a PDF next to the HTML (`transcripts/<name>.html` and `transcripts/<name>.pdf`). Disable it with `--no-pdf`. PDFs are rendered with [WeasyPrint](https://weasyprint.org/), which needs the Pango library on the OS. The Docker images include it. For a local install:

```bash
sudo apt install libpango-1.0-0 libpangoft2-1.0-0 fonts-dejavu-core   # Debian/Ubuntu
brew install pango                                                  # macOS (Homebrew)
```

On macOS, if the import still fails, run with `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`. If Pango is missing the HTML is still written, the PDF is skipped with a clear message, and the exit code is 1.

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
| `--pdf / --no-pdf` | | `--pdf` | Also write a PDF next to each HTML report (same name, `.pdf`). A PDF failure never loses the HTML; the run just exits with code 1. |
| `--upload-to DEST` | | none | rclone destination (e.g. `gdrive:stt-transcripts`). Uploads the HTML and the PDF right after they are generated. Also read from `STT_UPLOAD_TO`. |

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

If the GPU runs out of memory (`HIP out of memory`, common on 8 GB cards with `large-v3`), lower the number of 30s chunks decoded at once with `STT_BATCH_SIZE` (default `2`; try `1`), for example in `.env`. You can also set `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` to reduce fragmentation, or use `--model medium`.

The image sets no `HSA_OVERRIDE_GFX_VERSION`: the PyTorch ROCm wheels include native kernels for the RX 7600 (gfx1102), and forcing a different version made the GPU crash with `HSA_STATUS_ERROR_INVALID_ISA`. Check your card is listed with `docker compose run --rm --entrypoint python stt-rocm -c "import torch; print(torch.cuda.get_arch_list())"`; only if it is not, pass `-e HSA_OVERRIDE_GFX_VERSION=<version>` at run time. The model cache lives in the `hf-cache` volume, and `HF_TOKEN` is read from `.env` when present. The container runs as root, so it can open the GPU devices without extra groups (named groups such as `render` do not exist inside the image, and listing them in compose makes Docker fail).

**Batch mode** reads a list file that compose mounts read-only at `/data/urls.txt`. `urls.txt` is git-ignored: copy [`urls.example.txt`](urls.example.txt) to `urls.txt` and edit it. To keep the list outside the repository, set `URLS_FILE` (shell or `.env`) to its path on the host:

```bash
cp urls.example.txt urls.txt           # or: export URLS_FILE=/home/you/private/urls.txt
docker compose run --rm stt-rocm transcribe --input-file /data/urls.txt --engine transformers --model large-v3 --language pt
```

The list file must exist before **any** `docker compose run`, even for commands that don't use it, because compose mounts it into every container. On Linux, compose stops with "bind source path does not exist" if it is missing. (Docker Desktop on macOS may instead create an empty directory with that name, so check it is a file.)

### Uploading transcripts to Google Drive (unattended runs)

With `--upload-to REMOTE:FOLDER` (or `STT_UPLOAD_TO` in `.env`), each HTML report and its PDF are uploaded with [rclone](https://rclone.org/) **right after it is generated**, so you can start a long batch, go to sleep, and find the files in Drive. The local copy in `./transcripts` is always kept. A failed upload does not stop the batch; it is reported in the log and the command exits with code 1 at the end. rclone is bundled in both images.

One-time setup (Drive needs a browser login, so authorise on a machine that has one). The target is a Drive folder you created in the web UI, so use the default `drive` scope: the narrower `drive.file` scope only sees files rclone created itself and cannot write into an existing folder. To contain the blast radius, pin the remote to that single folder with `root_folder_id`: rclone then cannot see anything outside it.

```bash
# 1. On a machine with a browser, run `rclone config` and create a remote named "gdrive":
#      Storage: drive      Scope: 1 (full access)
#      root_folder_id: <the ID at the end of the folder URL, after /folders/>
#    The folder ID is the last part of https://drive.google.com/drive/folders/<ID>.
# 2. Copy the resulting rclone.conf (path: `rclone config file`) to the server:
mkdir -p rclone-config && chmod 700 rclone-config
scp laptop:~/.config/rclone/rclone.conf rclone-config/ && chmod 600 rclone-config/rclone.conf
```

With `root_folder_id` set, the destination is relative to that folder, so use `--upload-to gdrive:` (the folder itself) or `gdrive:subfolder`.

`rclone-config/` is git-ignored and mounted into the container. Set `RCLONE_CONFIG_DIR` to use another host folder. The config holds a Drive token, so treat it like a password.

Run it (the destination is checked before the model loads, so a misconfigured remote fails in seconds, not after hours):

```bash
docker compose run --rm stt-rocm transcribe --input-file /data/urls.txt \
  --engine transformers --model large-v3 --language pt --upload-to gdrive:stt-transcripts
```

To survive an SSH disconnect, start it detached and follow the log:

```bash
docker compose run -d --rm --name stt-batch stt-rocm transcribe --input-file /data/urls.txt \
  --engine transformers --model large-v3 --upload-to gdrive:stt-transcripts
docker logs -f stt-batch
```

---

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
