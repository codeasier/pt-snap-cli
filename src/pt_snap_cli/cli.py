"""CLI entry point for pt-snap-cli."""

from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Annotated

import typer

from pt_snap_cli import __version__
from pt_snap_cli.completion import complete_categories, complete_device_ids, complete_template_names
from pt_snap_cli.config import ENV_DB_PATH
from pt_snap_cli.core import (
    DatabaseMissingError,
    DatabaseSchemaError,
    FocusFileInvalidError,
    FocusNotConfiguredError,
    FocusService,
    InvalidCategoryError,
    InvalidDeviceError,
    QueryExecutionError,
    QueryService,
    TemplateNotFoundError,
    TemplateRenderError,
)
from pt_snap_cli.query.registry import discover_categories

app = typer.Typer(
    name="pt-snap",
    help="PyTorch Memory Snapshot Analysis Tool",
    add_completion=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _focus_service() -> FocusService:
    return FocusService()


def _query_service() -> QueryService:
    return QueryService(_focus_service())


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"pt-snap-cli version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option("--version", "-v", help="Show version and exit", callback=version_callback),
    ] = None,
) -> None:
    """PyTorch Memory Snapshot Analysis Tool."""


@app.command("focus")
def focus_database(
    db_path: Annotated[Path | None, typer.Argument(help="Path to SQLite database file")] = None,
    device: Annotated[
        int | None,
        typer.Option(
            "--device", "-d", help="Device ID to focus on", autocompletion=complete_device_ids
        ),
    ] = None,
    session: Annotated[
        bool, typer.Option("--session", help="Print a shell export for this session only")
    ] = False,
    global_focus: Annotated[
        bool, typer.Option("--global", help="Store the focus in legacy global config")
    ] = False,
) -> None:
    """Set the current analysis focus (database and optional device)."""
    focus_service = _focus_service()

    if db_path is None and device is None:
        try:
            state = focus_service.get_focus()
        except FocusFileInvalidError as e:
            _error(str(e))

        if state.db_path:
            typer.echo(f"Current database ({state.source}): {state.db_path}")
            if state.focus_file:
                typer.echo(f"Focus file: {state.focus_file}")
            if state.device_id is not None:
                typer.echo(f"Focused device: {state.device_id}")
            if not state.db_path.exists():
                typer.secho("Warning: Database file does not exist!", fg=typer.colors.YELLOW)
        else:
            typer.echo("No current focus set.")
            typer.echo("Usage: pt-snap focus <database_path> [--device <id>] [--session|--global]")
        raise typer.Exit()

    if session and global_focus:
        _error("--session and --global cannot be used together.")

    if db_path is None and device is not None:
        try:
            state = focus_service.set_device(device)
        except (
            FocusFileInvalidError,
            FocusNotConfiguredError,
            DatabaseMissingError,
            InvalidDeviceError,
        ) as e:
            _error(str(e))

        typer.secho(f"Focused device ({state.source}): {device}", fg=typer.colors.GREEN)
        if state.source == "project" and state.focus_file:
            typer.echo(f"Focus file: {state.focus_file}")
        raise typer.Exit()

    try:
        if session:
            state = focus_service.validate_session_db(db_path)
            typer.echo(f"export {ENV_DB_PATH}={shlex.quote(str(state.db_path))}")
            return
        if global_focus:
            state = focus_service.set_global_focus(db_path, device)
            typer.secho(f"Using global database: {state.db_path}", fg=typer.colors.GREEN)
        else:
            state = focus_service.set_project_focus(db_path, device)
            typer.secho(f"Using project database: {state.db_path}", fg=typer.colors.GREEN)
            if state.focus_file:
                typer.echo(f"Focus file: {state.focus_file}")
        if device is not None:
            typer.echo(f"Focused device: {device}")
        if state.available_devices:
            typer.echo(f"Available devices: {', '.join(map(str, state.available_devices))}")
        else:
            typer.echo("No devices found in database.")
    except (
        DatabaseMissingError,
        DatabaseSchemaError,
        InvalidDeviceError,
        FocusFileInvalidError,
    ) as e:
        _error(str(e))


@app.command("query")
def query_database(
    db_path: Annotated[
        Path | None, typer.Argument(help="Path to database file (optional if configured)")
    ] = None,
    template_use: Annotated[
        str | None,
        typer.Option(
            "--template-use",
            help="Query template name to execute",
            autocompletion=complete_template_names,
        ),
    ] = None,
    params: Annotated[str | None, typer.Option(help="Query parameters as JSON string")] = None,
    device: Annotated[
        int | None,
        typer.Option(
            help="Device ID to query",
            autocompletion=complete_device_ids,
        ),
    ] = None,
    list_templates: Annotated[
        bool, typer.Option("--list", help="List all available query templates")
    ] = False,
    category: Annotated[
        str | None,
        typer.Option(
            "--category",
            help="Filter templates by category",
            autocompletion=complete_categories,
        ),
    ] = None,
    template_info: Annotated[
        str | None,
        typer.Option(
            "--template-info",
            help="Show detailed information about a template (including parameters and output schema)",
            autocompletion=complete_template_names,
        ),
    ] = None,
    max_rows: Annotated[
        int | None,
        typer.Option(
            "-n",
            help="Maximum number of result rows to display (<= 0 for unlimited, default: unlimited)",
        ),
    ] = None,
) -> None:
    """Execute queries on the memory snapshot database."""
    focus_service = _focus_service()
    query_service = _query_service()

    if category is not None and not list_templates and not template_use and not template_info:
        list_templates = True

    if list_templates:
        try:
            categories = discover_categories()
            category_labels = {
                cat: cat.replace("_", " ").title() + " Queries" for cat in categories
            }
            if category is not None:
                filter_cats = [category]
                query_service.list_templates(category)
            else:
                filter_cats = categories
            any_found = False
            for cat in filter_cats:
                details = query_service.list_templates(cat, validate_category=False)
                if details:
                    any_found = True
                    typer.secho(f"{category_labels[cat]}:", fg=typer.colors.GREEN, bold=True)
                    for info in details:
                        typer.secho(f"  {info.name}", fg=typer.colors.GREEN, bold=True)
                        typer.echo(f"    {info.description}")
                    typer.echo()
            if not any_found:
                typer.echo("No query templates available.")
        except InvalidCategoryError as e:
            _error(str(e))
        raise typer.Exit()

    if template_info:
        try:
            info = query_service.get_template_info(template_info)
        except TemplateNotFoundError:
            typer.secho(f"Error: Template '{template_info}' not found", fg=typer.colors.RED)
            raise typer.Exit() from None

        typer.secho(f"Template: {info.name}", fg=typer.colors.GREEN, bold=True)
        typer.echo(f"Description: {info.description}")
        typer.echo()
        typer.echo("Parameters:")
        if info.parameters:
            for param_name, param_details in info.parameters.items():
                required_str = " (required)" if param_details.required else " (optional)"
                default_str = (
                    f" [default: {param_details.default}]"
                    if param_details.default is not None
                    else ""
                )
                typer.secho(
                    f"  {param_name}: {param_details.type}{required_str}{default_str}",
                    fg=typer.colors.YELLOW,
                )
                typer.echo(f"    {param_details.description}")
        else:
            typer.echo("  None")
        typer.echo()
        typer.echo("Output Schema:")
        if info.output_schema:
            for col in info.output_schema:
                typer.echo(f"  {col['column']}: {col['type']}")
        else:
            typer.echo("  Dynamic (depends on query)")
        typer.echo()
        typer.echo("Example Usage:")
        example_params = {}
        for param_name, param_details in info.parameters.items():
            if param_details.type == "int":
                example_params[param_name] = (
                    param_details.default if param_details.default is not None else 0
                )
            elif param_details.type == "float":
                example_params[param_name] = (
                    param_details.default if param_details.default is not None else 0.0
                )
            elif param_details.type == "str":
                example_params[param_name] = (
                    param_details.default if param_details.default is not None else "example"
                )
            elif param_details.type == "bool":
                example_params[param_name] = True
        if example_params:
            typer.echo(
                f"  pt-snap query {db_path or '<configured_db>'} --template-use {info.name} --params '{json.dumps(example_params)}'"
            )
        else:
            typer.echo(f"  pt-snap query {db_path or '<configured_db>'} --template-use {info.name}")
        raise typer.Exit()

    if not template_use:
        _error("--template-use is required when not using --list or --template-info")

    try:
        query_params = json.loads(params) if params else {}
        result = query_service.execute_query(
            template=template_use,
            params=query_params,
            db_path=db_path,
            device_id=device,
            max_rows=max_rows,
        )
        if result.rows:
            typer.echo(f"Found {result.total} results, showing {result.returned}:")
            for row in result.rows:
                typer.echo(f"  {row}")
            if result.returned < result.total:
                typer.echo(f"  ... and {result.total - result.returned} more (use -n to show more)")
        else:
            typer.echo("No results found.")
    except FocusFileInvalidError as e:
        _error(str(e))
    except FocusNotConfiguredError:
        typer.secho(
            "Error: No database path specified and no database configured.", fg=typer.colors.RED
        )
        typer.echo(
            "Use 'pt-snap focus <database_path>' to set a project database, or provide db_path argument."
        )
        raise typer.Exit(1) from None
    except DatabaseMissingError:
        try:
            state = focus_service.get_focus(explicit_db_path=db_path, explicit_device_id=device)
        except FocusFileInvalidError:
            state = None
        source = state.source if state is not None else "configured"
        path = state.db_path if state is not None else db_path
        typer.secho(f"Error: Database from {source} focus not found: {path}", fg=typer.colors.RED)
        if state is not None and state.focus_file:
            typer.echo(f"Focus file: {state.focus_file}")
        typer.echo(
            "Use 'pt-snap focus <new_database_path>' to set a new project database, or provide db_path argument."
        )
        raise typer.Exit(1) from None
    except InvalidDeviceError as e:
        if str(e) == "No devices found in database.":
            typer.echo("No devices found in database.")
            raise typer.Exit() from None
        _error(str(e))
    except TemplateNotFoundError as e:
        typer.secho(f"Error executing query: {e}", fg=typer.colors.RED)
        raise typer.Exit(1) from None
    except (
        TemplateRenderError,
        QueryExecutionError,
        DatabaseSchemaError,
        json.JSONDecodeError,
    ) as e:
        typer.secho(f"Error executing query: {e}", fg=typer.colors.RED)
        raise typer.Exit(1) from None


@app.command("config")
def show_config(
    clear: Annotated[bool, typer.Option("--clear", help="Clear all configuration")] = False,
    show_path: Annotated[bool, typer.Option("--path", help="Show config file path")] = False,
) -> None:
    """Show or manage pt-snap configuration."""
    focus_service = _focus_service()

    if show_path:
        typer.echo(f"Config file: {focus_service.get_global_config_path()}")
        raise typer.Exit()

    if clear:
        focus_service.clear_global_focus()
        typer.secho("Configuration cleared.", fg=typer.colors.GREEN)
        raise typer.Exit()

    current_config = focus_service.show_global_config()
    if not current_config:
        typer.echo("No configuration set.")
    else:
        typer.echo("Current configuration:")
        for key, value in current_config.items():
            typer.echo(f"  {key}: {value}")


def _error(message: str) -> None:
    typer.secho(f"Error: {message}", fg=typer.colors.RED)
    raise typer.Exit(1) from None


def _safe_call() -> int:
    try:
        app()
        return 0
    except KeyError as e:
        if str(e) in ("'COMP_WORDS'", "'COMP_LINE'", "'COMP_POINT'"):
            return 1
        raise


if __name__ == "__main__":
    import sys

    sys.exit(_safe_call())
