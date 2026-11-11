# python-stt

Speech-to-text command line application built with [Typer](https://typer.tiangolo.com/).

> Status: project skeleton. Commands and integrations are not implemented yet.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)

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

## Usage

The examples below use the `stt` command. Prefix them with `uv run` if you have not activated the virtual environment or installed the tool.

```bash
stt --help                         # list all commands
stt --version                      # show the version
stt help [COMMAND]                 # help for the app or a specific command
stt config                         # not implemented yet
stt transcribe path/to/audio.wav   # not implemented yet
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
