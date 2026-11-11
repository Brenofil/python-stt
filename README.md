# python-stt

Speech-to-text command line application built with [Typer](https://typer.tiangolo.com/).

> Status: project skeleton. Commands and integrations are not implemented yet.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)

## Setup

```bash
uv sync
```

## Usage

```bash
uv run stt --help
uv run stt --version
uv run stt transcribe path/to/audio.wav   # not implemented yet
```

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
