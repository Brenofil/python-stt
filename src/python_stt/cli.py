"""Typer application entry point. Sub-commands live in `python_stt.commands`."""

import typer

from python_stt import __version__
from python_stt.commands import config, help, transcribe

app = typer.Typer(
    name="stt",
    help="Speech-to-text command line application.",
    no_args_is_help=True,
)

app.command("config")(config.config)
app.command("transcribe")(transcribe.transcribe)
app.command("help")(help.show_help)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the version and exit.",
    ),
) -> None:
    """Global options shared by every command."""
