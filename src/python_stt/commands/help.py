from typing import Annotated

import typer


def show_help(
    ctx: typer.Context,
    command: Annotated[str | None, typer.Argument(help="Command to show help for.")] = None,
) -> None:
    """Show help for the application or for a specific command."""
    root_ctx = ctx.find_root()
    if command is None:
        typer.echo(root_ctx.get_help())
        return

    sub = root_ctx.command.get_command(root_ctx, command)
    if sub is None:
        typer.echo(f"Unknown command: {command}", err=True)
        raise typer.Exit(code=2)
    typer.echo(typer.Context(sub, info_name=command, parent=root_ctx).get_help())
