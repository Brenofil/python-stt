from typer.testing import CliRunner

from python_stt import __version__
from python_stt.cli import app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output
