import typer


def config(
    show: bool = typer.Option(False, "--show", help="Show the current configuration."),
) -> None:
    """View or change the application configuration."""
    raise NotImplementedError("config is not implemented yet")
