"""CLI entry point for pt-snap-analyzer."""

from pathlib import Path
from typing import Annotated

import typer

from pt_snap_analyzer import __version__
from pt_snap_analyzer.context import Context

app = typer.Typer(
    name="pt-snap",
    help="PyTorch Memory Snapshot Analysis Tool",
    add_completion=False,
)


def version_callback(value: bool) -> None:
    """Callback for --version flag."""
    if value:
        typer.echo(f"pt-snap-analyzer version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option("--version", "-v", help="Show version and exit", callback=version_callback),
    ] = None,
) -> None:
    """PyTorch Memory Snapshot Analysis Tool."""


@app.command("use")
def use_database(
    db_path: Annotated[Path, typer.Argument(help="Path to SQLite database file")],
) -> None:
    """Set the current analysis database.

    Validates the database and displays available devices.
    """
    if not db_path.exists():
        typer.secho(f"Error: Database file not found: {db_path}", fg=typer.colors.RED)
        raise typer.Exit(1)

    try:
        ctx = Context(db_path)
        typer.secho(f"Using database: {db_path}", fg=typer.colors.GREEN)
        devices = ctx.device_ids
        if devices:
            typer.echo(f"Available devices: {', '.join(map(str, devices))}")
        else:
            typer.echo("No devices found in database.")
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED)
        raise typer.Exit(1) from None


if __name__ == "__main__":
    app()
