from typer.testing import CliRunner

from python_stt import __version__
from python_stt.cli import app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_help_lists_commands():
    result = runner.invoke(app, ["help"])
    assert result.exit_code == 0
    for name in ("config", "transcribe", "help"):
        assert name in result.output


def test_help_for_command():
    result = runner.invoke(app, ["help", "transcribe"])
    assert result.exit_code == 0
    assert "audio_file" in result.output


def test_help_unknown_command():
    result = runner.invoke(app, ["help", "nope"])
    assert result.exit_code == 2
