"""CLI entry point for pt-snap-cli."""

from pathlib import Path
from typing import Annotated

import typer

from pt_snap_cli import __version__
from pt_snap_cli.completion import complete_categories, complete_device_ids, complete_template_names
from pt_snap_cli.config import ENV_DB_PATH, Config, ContextResolutionError
from pt_snap_cli.context import Context, DatabaseNotFoundError, SchemaVersionError

app = typer.Typer(
    name="pt-snap",
    help="PyTorch Memory Snapshot Analysis Tool",
    add_completion=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def version_callback(value: bool) -> None:
    """Callback for --version flag."""
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


@app.command("use")
def use_database(
    db_path: Annotated[Path | None, typer.Argument(help="Path to SQLite database file")] = None,
    session: Annotated[
        bool, typer.Option("--session", help="Print a shell export for this session only")
    ] = False,
    global_context: Annotated[
        bool, typer.Option("--global", help="Store the database in legacy global config")
    ] = False,
) -> None:
    """Set the current analysis database.

    Validates the database and saves the path to project context by default.
    After setting, you can use 'pt-snap query' without specifying db_path.

    Use --session for an isolated shell/agent override.
    Use --global for legacy user-wide configuration.
    If called without arguments, shows the effective database.
    """
    config = Config()

    if db_path is None:
        try:
            resolved = config.resolve_db_context()
        except ContextResolutionError as e:
            typer.secho(f"Error: {e}", fg=typer.colors.RED)
            raise typer.Exit(1) from None

        if resolved.db_path:
            typer.echo(f"Current database ({resolved.source}): {resolved.db_path}")
            if resolved.context_file:
                typer.echo(f"Context file: {resolved.context_file}")
            if not resolved.db_path.exists():
                typer.secho("Warning: Database file does not exist!", fg=typer.colors.YELLOW)
        else:
            typer.echo("No current database set.")
            typer.echo("Usage: pt-snap use <database_path> [--session|--global]")
        raise typer.Exit()

    if session and global_context:
        typer.secho("Error: --session and --global cannot be used together.", fg=typer.colors.RED)
        raise typer.Exit(1)

    if not db_path.exists():
        typer.secho(f"Error: Database file not found: {db_path}", fg=typer.colors.RED)
        raise typer.Exit(1)

    try:
        ctx = Context(db_path)
        resolved_db_path = db_path.expanduser().resolve()
        if session:
            import shlex

            typer.echo(f"export {ENV_DB_PATH}={shlex.quote(str(resolved_db_path))}")
            return
        if global_context:
            config.current_db_path = resolved_db_path
            typer.secho(f"Using global database: {resolved_db_path}", fg=typer.colors.GREEN)
        else:
            context_file = config.write_project_db_path(resolved_db_path)
            typer.secho(f"Using project database: {resolved_db_path}", fg=typer.colors.GREEN)
            typer.echo(f"Project context: {context_file}")
        devices = ctx.device_ids
        if devices:
            typer.echo(f"Available devices: {', '.join(map(str, devices))}")
        else:
            typer.echo("No devices found in database.")
    except (DatabaseNotFoundError, SchemaVersionError) as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED)
        raise typer.Exit(1) from None
    except Exception as e:
        typer.secho(f"Error: unexpected failure opening database: {e}", fg=typer.colors.RED)
        raise typer.Exit(1) from None


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
            help="Filter templates by category (basic, statistical, business)",
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
) -> None:
    """Execute queries on the memory snapshot database.

    The db_path argument is optional if you have configured a database with 'pt-snap use'.

    Use --list to see all supported query templates.
    Use --template-info {template_name} to see detailed template information.

    Examples:
        pt-snap use snapshot.pkl.db                    # Set project database
        pt-snap query --list                           # List templates
        pt-snap query --template-use leak_detection    # Query with resolved context
        pt-snap query --template-use active_blocks --device 0
        pt-snap query custom.db --template-use leak_detection  # Override with custom path
        pt-snap query --template-info leak_detection
        pt-snap query --list --category basic          # List only basic queries
    """
    from pt_snap_cli.query import QueryExecutor
    from pt_snap_cli.query.registry import (
        get_template_info,
        list_by_category_with_details,
    )

    # Implicit list mode when --category is provided without --template-use
    if category is not None and not list_templates and not template_use and not template_info:
        list_templates = True

    if list_templates:
        categories = ["basic", "statistical", "business"]
        category_labels = {
            "basic": "Basic Queries",
            "statistical": "Statistical Queries",
            "business": "Business Queries",
        }

        if category is not None and category not in categories:
            typer.secho(
                f"Error: Invalid category '{category}'. Must be one of: {', '.join(categories)}",
                fg=typer.colors.RED,
            )
            raise typer.Exit(1)

        filter_cats = [category] if category in categories else categories
        any_found = False

        for cat in filter_cats:
            details = list_by_category_with_details(cat)
            if details:
                any_found = True
                typer.secho(f"{category_labels[cat]}:", fg=typer.colors.GREEN, bold=True)
                for info in details:
                    typer.secho(f"  {info['name']}", fg=typer.colors.GREEN, bold=True)
                    typer.echo(f"    {info['description']}")
                typer.echo()

        if not any_found:
            typer.echo("No query templates available.")
        raise typer.Exit()

    if template_info:
        info = get_template_info(template_info)
        if info:
            typer.secho(f"Template: {info['name']}", fg=typer.colors.GREEN, bold=True)
            typer.echo(f"Description: {info['description']}")
            typer.echo()

            typer.echo("Parameters:")
            if info["parameters"]:
                for param_name, param_details in info["parameters"].items():
                    required_str = " (required)" if param_details["required"] else " (optional)"
                    default_str = (
                        f" [default: {param_details['default']}]"
                        if param_details["default"] is not None
                        else ""
                    )
                    typer.secho(
                        f"  {param_name}: {param_details['type']}{required_str}{default_str}",
                        fg=typer.colors.YELLOW,
                    )
                    typer.echo(f"    {param_details['description']}")
            else:
                typer.echo("  None")
            typer.echo()

            typer.echo("Output Schema:")
            if info["output_schema"]:
                for col in info["output_schema"]:
                    typer.echo(f"  {col['column']}: {col['type']}")
            else:
                typer.echo("  Dynamic (depends on query)")
            typer.echo()

            typer.echo("Example Usage:")
            example_params = {}
            for param_name, param_details in info["parameters"].items():
                if param_details["type"] == "int":
                    example_params[param_name] = (
                        param_details["default"] if param_details["default"] is not None else 0
                    )
                elif param_details["type"] == "float":
                    example_params[param_name] = (
                        param_details["default"] if param_details["default"] is not None else 0.0
                    )
                elif param_details["type"] == "str":
                    example_params[param_name] = (
                        param_details["default"]
                        if param_details["default"] is not None
                        else "example"
                    )
                elif param_details["type"] == "bool":
                    example_params[param_name] = True

            if example_params:
                import json

                params_str = json.dumps(example_params)
                typer.echo(
                    f"  pt-snap query {db_path or '<configured_db>'} --template-use {info['name']} --params '{params_str}'"
                )
            else:
                typer.echo(
                    f"  pt-snap query {db_path or '<configured_db>'} --template-use {info['name']}"
                )
        else:
            typer.secho(f"Error: Template '{template_info}' not found", fg=typer.colors.RED)
        raise typer.Exit()

    if not template_use:
        typer.secho(
            "Error: --template-use is required when not using --list or --template-info",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    config = Config()
    try:
        resolved = config.resolve_db_context(db_path)
    except ContextResolutionError as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED)
        raise typer.Exit(1) from None

    db_path = resolved.db_path
    if db_path is None:
        typer.secho(
            "Error: No database path specified and no database configured.",
            fg=typer.colors.RED,
        )
        typer.echo(
            "Use 'pt-snap use <database_path>' to set a project database, or provide db_path argument."
        )
        raise typer.Exit(1)
    if not db_path.exists():
        typer.secho(
            f"Error: Database from {resolved.source} context not found: {db_path}",
            fg=typer.colors.RED,
        )
        if resolved.context_file:
            typer.echo(f"Context file: {resolved.context_file}")
        typer.echo(
            "Use 'pt-snap use <new_database_path>' to set a new project database, or provide db_path argument."
        )
        raise typer.Exit(1)

    try:
        context = Context(db_path, devices=[device] if device is not None else None)
        executor = QueryExecutor(
            context, template_dir=Path(__file__).parent / "query" / "templates"
        )

        query_params = {}
        if params:
            import json

            query_params = json.loads(params)

        if device is not None:
            results = executor.execute_template(template_use, query_params, device_id=device)
        else:
            device_ids = context.device_ids
            if not device_ids:
                typer.echo("No devices found in database.")
                raise typer.Exit()
            default_device = device_ids[0]
            results = executor.execute_template(
                template_use, query_params, device_id=default_device
            )

        if results:
            typer.echo(f"Found {len(results)} results:")
            for row in results[:10]:
                typer.echo(f"  {row}")
            if len(results) > 10:
                typer.echo(f"  ... and {len(results) - 10} more")
        else:
            typer.echo("No results found.")

    except FileNotFoundError as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED)
        raise typer.Exit(1) from None
    except Exception as e:
        typer.secho(f"Error executing query: {e}", fg=typer.colors.RED)
        raise typer.Exit(1) from None


@app.command("config")
def show_config(
    clear: Annotated[bool, typer.Option("--clear", help="Clear all configuration")] = False,
    show_path: Annotated[bool, typer.Option("--path", help="Show config file path")] = False,
) -> None:
    """Show or manage pt-snap configuration.

    Shows current configuration including the configured database path.
    Use --clear to reset configuration.
    Use --path to see where configuration is stored.
    """
    config = Config()

    if show_path:
        typer.echo(f"Config file: {config.config_file}")
        raise typer.Exit()

    if clear:
        config.clear()
        typer.secho("Configuration cleared.", fg=typer.colors.GREEN)
        raise typer.Exit()

    current_config = config.show()
    if not current_config:
        typer.echo("No configuration set.")
    else:
        typer.echo("Current configuration:")
        for key, value in current_config.items():
            typer.echo(f"  {key}: {value}")


def _safe_call() -> int:
    """Wrapper for the console script entry point to handle completion errors.

    Returns:
        Exit code (0 for success, 1 for errors).
    """
    try:
        app()
        return 0
    except KeyError as e:
        # Click's shell completion can raise KeyError when COMP_WORDS or
        # COMP_LINE is not set in non-standard terminal environments.
        # Exit silently — printing to stdout causes the shell to try
        # executing the error message as a command.
        if str(e) in ("'COMP_WORDS'", "'COMP_LINE'", "'COMP_POINT'"):
            return 1
        raise


if __name__ == "__main__":
    import sys

    sys.exit(_safe_call())
