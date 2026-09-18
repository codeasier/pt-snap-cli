"""CLI entry point for pt-snap-cli."""

from __future__ import annotations

import json
import shlex
import shutil
import textwrap
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any, Literal, NoReturn, cast

import typer

from pt_snap_cli import __version__
from pt_snap_cli.completion import (
    complete_categories,
    complete_device_ids,
    complete_skill_names,
    complete_skill_targets,
    complete_template_names,
)
from pt_snap_cli.config import ENV_DB_PATH
from pt_snap_cli.core import (
    DatabaseMissingError,
    DatabaseSchemaError,
    FocusFileInvalidError,
    FocusNotConfiguredError,
    FocusService,
    ImportExecutionError,
    ImportMetadataService,
    ImportOptions,
    ImportService,
    ImportToolMissingError,
    InvalidCategoryError,
    InvalidDeviceError,
    InvalidSkillTargetError,
    PeakMemoryReport,
    QueryExecutionError,
    QueryService,
    ReportService,
    SkillCatalogError,
    SkillInstallError,
    SkillInstallReport,
    SkillListing,
    SkillNotFoundError,
    SkillService,
    SnapshotFileInvalidError,
    SplitError,
    SplitOptions,
    SplitService,
    TemplateNotFoundError,
    TemplateRenderError,
)
from pt_snap_cli.core.models import SKILL_RESTART_ACTIONS, SKILL_RESTART_HINT
from pt_snap_cli.core.skill_service import (
    format_skill_install_target,
    format_skill_location,
    human_skill_summary,
    parse_host_option,
)
from pt_snap_cli.query.config import OUTPUT_COLUMN_OPTIONAL
from pt_snap_cli.query.registry import discover_categories

AGENT_HELP_EPILOG = (
    "Agents: prefer --json where supported. "
    "Start with the pt-snap-helper skill; "
    "check availability with pt-snap skill list --json."
)

app = typer.Typer(
    name="pt-snap",
    help="PyTorch Memory Snapshot Analysis Tool",
    epilog=AGENT_HELP_EPILOG,
    add_completion=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
report_app = typer.Typer(help="Generate memory analysis reports")
skill_app = typer.Typer(help="Manage bundled agent skills", no_args_is_help=True)
app.add_typer(report_app, name="report")
app.add_typer(skill_app, name="skill")


def _focus_service() -> FocusService:
    return FocusService()


def _query_service() -> QueryService:
    return QueryService(_focus_service())


def _echo_output_schema_column(column: Mapping[str, Any]) -> None:
    typer.echo(f"  {column['column']}: {column['type']}")
    for key in OUTPUT_COLUMN_OPTIONAL:
        if key not in column:
            continue
        value = column[key]
        if key == "interpretation_limits":
            typer.echo("    interpretation_limits:")
            for item in value:
                typer.echo(f"      - {item}")
        else:
            typer.echo(f"    {key}: {value}")


def _skill_service() -> SkillService:
    return SkillService()


def _skill_dest_dir(
    dest_dir: Path | None,
    target: str | None,
    *,
    project: bool = False,
    user: bool = False,
) -> Path | None:
    if dest_dir is None:
        return None
    if target:
        _error("--dir cannot be combined with --target.")
    if project:
        _error("--dir cannot be combined with --project.")
    if user:
        _error("--dir cannot be combined with --user.")
    return dest_dir


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"pt-snap-cli version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    _: Annotated[
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
            _echo_callstack_layout(state.callstack_layout, state.callstack_layout_error)
            if not state.db_path.exists():
                typer.secho("Warning: Database file does not exist!", fg=typer.colors.YELLOW)
        else:
            typer.echo("No current focus set.")
            typer.echo("Usage: pt-snap focus <database_path> [--device <id>] [--session|--global]")
        raise typer.Exit()

    if session and global_focus:
        _error("--session and --global cannot be used together.")
    if session and device is not None:
        _error(
            "--device cannot be used with --session; session focus exports only a database path."
        )

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
        _echo_callstack_layout(state.callstack_layout, state.callstack_layout_error)
        raise typer.Exit()

    try:
        focus_db_path = db_path
        if focus_db_path is None:
            raise AssertionError("db_path must be provided when setting focus")
        if session:
            state = focus_service.validate_session_db(focus_db_path)
            typer.echo(f"export {ENV_DB_PATH}={shlex.quote(str(state.db_path))}")
            return
        if global_focus:
            state = focus_service.set_global_focus(focus_db_path, device)
            typer.secho(f"Using global database: {state.db_path}", fg=typer.colors.GREEN)
        else:
            state = focus_service.set_project_focus(focus_db_path, device)
            typer.secho(f"Using project database: {state.db_path}", fg=typer.colors.GREEN)
            if state.focus_file:
                typer.echo(f"Focus file: {state.focus_file}")
        if device is not None:
            typer.echo(f"Focused device: {device}")
        if state.available_devices:
            typer.echo(f"Available devices: {', '.join(map(str, state.available_devices))}")
        else:
            typer.echo("No devices found in database.")
        _echo_callstack_layout(state.callstack_layout, state.callstack_layout_error)
    except (
        DatabaseMissingError,
        DatabaseSchemaError,
        InvalidDeviceError,
        FocusFileInvalidError,
    ) as e:
        _error(str(e))


@app.command("import")
def import_snapshot(
    snapshot_file: Annotated[Path, typer.Argument(help="Path to .pkl snapshot")],
    output_dir: Annotated[Path | None, typer.Option("--output-dir", "-o")] = None,
    device: Annotated[int | None, typer.Option("--device", "-d")] = None,
    no_focus: Annotated[bool, typer.Option("--no-focus", help="Skip focus update")] = False,
    force: Annotated[bool, typer.Option("--force", help="Rebuild even when cache matches")] = False,
) -> None:
    """Import a PyTorch memory snapshot into a SQLite database."""
    try:
        result = ImportService().import_snapshot(
            ImportOptions(
                snapshot_file=snapshot_file,
                output_dir=output_dir,
                device=device,
                set_focus=not no_focus,
                force=force,
            )
        )
    except (
        ImportToolMissingError,
        ImportExecutionError,
        SnapshotFileInvalidError,
    ) as e:
        _error(str(e))

    action = "Reused" if result.reused else "Imported"
    typer.echo(f"{action}: {result.db_path}")
    if result.cache_miss_reason is not None:
        typer.echo(f"Cache miss: {result.cache_miss_reason}")
    if result.focus_state is not None and result.focus_state.focus_file is not None:
        typer.echo(f"Focus: {result.focus_state.focus_file}")


@app.command("split")
def split_snapshot(
    snapshot_file: Annotated[
        Path,
        typer.Argument(
            help="Path to .pkl or .pickle snapshot",
            metavar="SNAPSHOT_PATH",
        ),
    ],
    output: Annotated[Path, typer.Option("--output", "-o", help="New output directory")],
    device: Annotated[int | None, typer.Option("--device", "-d")] = None,
    slices: Annotated[int | None, typer.Option("--slices", "-s")] = None,
    max_entries: Annotated[int | None, typer.Option("--max-entries", "-m")] = None,
    output_format: Annotated[
        str,
        typer.Option(
            "--format",
            help="Output format: pickle or json",
            metavar="{pickle,json}",
        ),
    ] = "pickle",
) -> None:
    """Split a snapshot into independently replayable device slices."""
    try:
        result = SplitService().split(
            SplitOptions(
                snapshot_file=snapshot_file,
                output=output,
                device=device,
                slices=slices,
                max_entries=max_entries,
                format=output_format,
            )
        )
    except SplitError as exc:
        _error(str(exc))

    typer.echo(f"Split: {result.output}")
    typer.echo(f"Devices: {', '.join(map(str, result.devices))}")
    typer.echo(f"Files: {len(result.files)}")


@app.command("metadata")
def show_database_metadata(
    db_path: Annotated[
        Path | None, typer.Argument(help="Path to database file (optional if configured)")
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON")] = False,
) -> None:
    """Show import metadata for a SnapshotDB."""
    focus_service = _focus_service()
    try:
        resolved = focus_service.resolve_focus(explicit_db_path=db_path)
        if resolved.db_path is None:
            raise FocusNotConfiguredError("No database path specified and no database configured.")
        service = ImportMetadataService()
        inspection = service.inspect(resolved.db_path)
    except (
        FocusFileInvalidError,
        FocusNotConfiguredError,
        DatabaseMissingError,
        DatabaseSchemaError,
    ) as e:
        _error(str(e))

    if json_output:
        typer.echo(json.dumps(service.inspection_to_dict(inspection), indent=2))
        return

    typer.echo(f"Database: {inspection.db_path}")
    typer.echo(f"Status: {inspection.status}")
    if inspection.reason is not None:
        typer.echo(f"Reason: {inspection.reason}")
    if inspection.metadata is not None:
        typer.echo("Metadata:")
        for key, value in cast(Mapping[str, object], asdict(inspection.metadata)).items():
            typer.echo(f"  {key}: {value}")


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
            help="Show detailed information about a template (including parameters, output schema, and field semantics)",
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
                _ = query_service.list_templates(category)
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
        except TemplateNotFoundError as e:
            _error(str(e))

        typer.secho(f"Template: {info.name}", fg=typer.colors.GREEN, bold=True)
        typer.echo(f"Description: {info.description}")
        typer.echo(f"Category: {info.category}")
        typer.echo(f"Devices: {info.devices}")
        typer.echo(
            "Semantics Version: "
            f"{info.semantics_version if info.semantics_version is not None else 'none'}"
        )
        typer.echo()
        typer.echo("Parameters:")
        if info.parameters:
            for param_name, param_details in info.parameters.items():
                required_str = " (required)" if param_details.required else " (optional)"
                choices_str = (
                    f" [choices: {', '.join(str(choice) for choice in param_details.choices)}]"
                    if param_details.choices
                    else ""
                )
                default_str = (
                    f" [default: {param_details.default}]"
                    if param_details.default is not None
                    else ""
                )
                typer.secho(
                    f"  {param_name}: {param_details.type}{required_str}{choices_str}{default_str}",
                    fg=typer.colors.YELLOW,
                )
                typer.echo(f"    {param_details.description}")
        else:
            typer.echo("  None")
        typer.echo()
        typer.echo("Output Schema:")
        if info.output_schema:
            for col in info.output_schema:
                _echo_output_schema_column(col)
        else:
            typer.echo("  Dynamic (depends on query)")
        if info.interpretation_limits:
            typer.echo()
            typer.echo("Interpretation Limits:")
            for limit in info.interpretation_limits:
                typer.echo(f"  - {limit}")
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
                if param_details.default is not None:
                    example_params[param_name] = param_details.default
                elif param_details.choices:
                    example_params[param_name] = param_details.choices[0]
                else:
                    example_params[param_name] = "example"
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
        loaded_params = (  # pyright: ignore[reportUnknownVariableType]
            json.loads(params) if params else {}
        )
        if not isinstance(loaded_params, dict):
            raise TemplateRenderError("Query parameters must be a JSON object.")
        query_params = cast(dict[str, object], loaded_params)
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


@report_app.command("peak-memory")
def report_peak_memory(
    db_path: Annotated[
        Path | None, typer.Argument(help="Path to database file (optional if configured)")
    ] = None,
    device: Annotated[
        int | None,
        typer.Option(
            "--device",
            "-d",
            help="Device ID to report",
            autocompletion=complete_device_ids,
        ),
    ] = None,
    metric: Annotated[
        Literal["active", "allocated", "reserved"],
        typer.Option(help="Peak metric to report: active, allocated, or reserved"),
    ] = "active",
    include_static: Annotated[
        bool,
        typer.Option("--include-static/--exclude-static", help="Include static memory group"),
    ] = True,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Maximum callstack groups")] = 20,
    json_output: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON")] = False,
) -> None:
    """Generate a peak memory attribution report."""
    focus_service = _focus_service()
    report_service = ReportService(focus_service)
    try:
        report = report_service.peak_memory_report(
            db_path=db_path,
            device_id=device,
            metric=metric,
            include_static=include_static,
            limit=limit,
        )
    except ValueError as e:
        _error(str(e))
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
        _error(str(e))
    except (
        TemplateNotFoundError,
        TemplateRenderError,
        QueryExecutionError,
        DatabaseSchemaError,
    ) as e:
        typer.secho(f"Error generating report: {e}", fg=typer.colors.RED)
        raise typer.Exit(1) from None

    if json_output:
        typer.echo(json.dumps(asdict(report), indent=2))
        return

    _print_peak_memory_report(report)


def _print_peak_memory_report(report: PeakMemoryReport) -> None:
    typer.secho("Peak memory report", fg=typer.colors.GREEN, bold=True)
    typer.echo(f"Device: {report.device_id}")
    typer.echo(f"Metric: {report.metric}")
    typer.echo(f"Event ID: {report.event_id}")
    typer.echo()

    typer.secho("Peak counters:", fg=typer.colors.GREEN, bold=True)
    if report.peak:
        typer.echo(
            f"  allocated: {report.peak.get('peak_allocated')} at event {report.peak.get('peak_allocated_event_id')}"
        )
        typer.echo(
            f"  active: {report.peak.get('peak_active')} at event {report.peak.get('peak_active_event_id')}"
        )
        typer.echo(
            f"  reserved: {report.peak.get('peak_reserved')} at event {report.peak.get('peak_reserved_event_id')}"
        )
    else:
        typer.echo("  No peak counters found.")
    typer.echo()

    typer.secho("Allocator gap:", fg=typer.colors.GREEN, bold=True)
    if report.allocator_gap:
        gap = report.allocator_gap
        typer.echo(
            f"  active peak event: {gap.get('peak_active_event_id')} reserved-active gap={gap.get('reserved_active_gap_at_active_peak')}"
        )
        typer.echo(
            f"  allocated peak event: {gap.get('peak_allocated_event_id')} reserved-allocated gap={gap.get('reserved_allocated_gap_at_allocated_peak')}"
        )
        typer.echo(
            f"  reserved peak event: {gap.get('peak_reserved_event_id')} reserved-active gap={gap.get('reserved_active_gap_at_reserved_peak')}"
        )
        typer.echo(f"  all peaks same event: {bool(gap.get('all_peaks_same_event'))}")
    else:
        typer.echo("  No allocator gap data found.")
    typer.echo()

    typer.secho("Active memory by callstack:", fg=typer.colors.GREEN, bold=True)
    if not report.callstack_groups:
        typer.echo("  No active memory callstack groups found.")
        return
    for index, row in enumerate(report.callstack_groups, start=1):
        typer.echo(
            f"  [{index}] {row.get('category')} {row.get('size_bytes')} bytes, {row.get('block_count')} blocks ({row.get('percent_of_active_blocks')}%)"
        )
        typer.echo(f"      {row.get('callstack')}")


@skill_app.command("list")
def skill_list(
    target: Annotated[
        str | None,
        typer.Option(
            "--target",
            "-t",
            help="Comma-separated hosts to inspect: agents,claude,cursor,codex",
            autocompletion=complete_skill_targets,
        ),
    ] = None,
    project: Annotated[
        bool, typer.Option("--project", help="Inspect only project-local skill directories")
    ] = False,
    user: Annotated[
        bool, typer.Option("--user", help="Inspect only user-level skill directories")
    ] = False,
    dest_dir: Annotated[
        Path | None,
        typer.Option(
            "--dir",
            help="Inspect this skills directory instead of built-in agent/Claude/Cursor/Codex paths",
        ),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON")] = False,
) -> None:
    """List bundled agent skills and whether they are installed."""
    if project and user:
        _error("--project and --user cannot be used together.")
    custom_dir = _skill_dest_dir(dest_dir, target, project=project, user=user)
    service = _skill_service()
    try:
        listings = service.list_skills(
            hosts=None if custom_dir is not None else parse_host_option(target),
            scopes=(
                None
                if custom_dir is not None
                else (("project",) if project else (("user",) if user else None))
            ),
            dest_dir=custom_dir,
        )
    except (SkillCatalogError, InvalidSkillTargetError) as e:
        _error(str(e))

    if json_output:
        typer.echo(json.dumps(service.listing_to_dict(listings), indent=2))
        return

    if not listings:
        typer.echo("No bundled agent skills are available.")
        return

    _print_skill_listings(listings)


@skill_app.command("install")
def skill_install(
    names: Annotated[
        list[str] | None,
        typer.Argument(
            help="Skill names to install. Omit to install every bundled skill.",
            autocompletion=complete_skill_names,
        ),
    ] = None,
    target: Annotated[
        str | None,
        typer.Option(
            "--target",
            "-t",
            help="Comma-separated hosts: agents,claude,cursor,codex (default: agents,claude)",
            autocompletion=complete_skill_targets,
        ),
    ] = None,
    project: Annotated[
        bool, typer.Option("--project", help="Install into the current project")
    ] = False,
    force: Annotated[
        bool, typer.Option("--force", help="Replace existing skills that differ")
    ] = False,
    dest_dir: Annotated[
        Path | None,
        typer.Option(
            "--dir",
            help="Install into this skills directory (Windows, other agents, or a custom path)",
        ),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON")] = False,
) -> None:
    """Install bundled agent skills into shared agent, Claude, Cursor, Codex, or custom directories."""
    custom_dir = _skill_dest_dir(dest_dir, target, project=project)
    service = _skill_service()
    try:
        report = service.install_skills(
            names,
            hosts=None if custom_dir is not None else parse_host_option(target),
            scope="project" if project else "user",
            force=force,
            dest_dir=custom_dir,
        )
    except (
        SkillCatalogError,
        SkillNotFoundError,
        InvalidSkillTargetError,
        SkillInstallError,
    ) as e:
        _error(str(e))

    if json_output:
        typer.echo(json.dumps(service.install_report_to_dict(report), indent=2))
        return

    _print_skill_mutation_report(report)


@skill_app.command("upgrade")
def skill_upgrade(
    names: Annotated[
        list[str] | None,
        typer.Argument(
            help="Skill names to upgrade. Omit to upgrade every installed bundled skill.",
            autocompletion=complete_skill_names,
        ),
    ] = None,
    target: Annotated[
        str | None,
        typer.Option(
            "--target",
            "-t",
            help="Comma-separated hosts: agents,claude,cursor,codex (default: agents,claude)",
            autocompletion=complete_skill_targets,
        ),
    ] = None,
    project: Annotated[
        bool, typer.Option("--project", help="Upgrade skills in the current project")
    ] = False,
    dest_dir: Annotated[
        Path | None,
        typer.Option(
            "--dir",
            help="Upgrade skills in this directory instead of a built-in host",
        ),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON")] = False,
) -> None:
    """Replace outdated installed skills with the bundled copies."""
    custom_dir = _skill_dest_dir(dest_dir, target, project=project)
    service = _skill_service()
    try:
        report = service.upgrade_skills(
            names,
            hosts=None if custom_dir is not None else parse_host_option(target),
            scope="project" if project else "user",
            dest_dir=custom_dir,
        )
    except (
        SkillCatalogError,
        SkillNotFoundError,
        InvalidSkillTargetError,
        SkillInstallError,
    ) as e:
        _error(str(e))

    if json_output:
        typer.echo(json.dumps(service.install_report_to_dict(report), indent=2))
        return

    _print_skill_mutation_report(report)


@skill_app.command("uninstall")
def skill_uninstall(
    names: Annotated[
        list[str] | None,
        typer.Argument(
            help="Skill names to uninstall. Omit to uninstall every bundled skill.",
            autocompletion=complete_skill_names,
        ),
    ] = None,
    target: Annotated[
        str | None,
        typer.Option(
            "--target",
            "-t",
            help=(
                "Comma-separated hosts: agents,claude,cursor,codex. "
                "Defaults to agents,claude when --project is set"
            ),
            autocompletion=complete_skill_targets,
        ),
    ] = None,
    project: Annotated[
        bool, typer.Option("--project", help="Uninstall skills from the current project")
    ] = False,
    dest_dir: Annotated[
        Path | None,
        typer.Option(
            "--dir",
            help="Uninstall skills from this directory instead of a built-in host",
        ),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON")] = False,
) -> None:
    """Remove bundled agent skills.

    Without --target, --project, or --dir, remove every installed copy that
    `pt-snap skill list` would report. Use those flags to limit destinations.
    """
    custom_dir = _skill_dest_dir(dest_dir, target, project=project)
    service = _skill_service()
    try:
        unfiltered = custom_dir is None and target is None and not project
        report = service.uninstall_skills(
            names,
            hosts=None if custom_dir is not None else parse_host_option(target),
            scope="project" if project else "user",
            dest_dir=custom_dir,
            all_locations=unfiltered,
        )
    except (
        SkillCatalogError,
        SkillNotFoundError,
        InvalidSkillTargetError,
        SkillInstallError,
    ) as e:
        _error(str(e))

    if json_output:
        typer.echo(json.dumps(service.install_report_to_dict(report), indent=2))
        return

    _print_skill_mutation_report(report)


def _print_skill_listings(listings: list[SkillListing]) -> None:
    width = max(shutil.get_terminal_size((80, 24)).columns - 2, 40)
    width = min(width, 88)
    status_colors = {
        "installed": typer.colors.GREEN,
        "outdated": typer.colors.YELLOW,
        "missing": typer.colors.RED,
    }
    for index, item in enumerate(listings):
        if index:
            typer.echo()
        typer.secho(item.name, fg=typer.colors.GREEN, bold=True)
        locations = ", ".join(
            format_skill_location(location)
            for location in item.locations
            if location.status != "missing"
        )
        typer.echo("  Status     ", nl=False)
        typer.secho(item.status, fg=status_colors.get(item.status, typer.colors.WHITE))
        typer.echo(f"  Locations  {locations or '—'}")
        summary = human_skill_summary(item.description)
        if summary:
            typer.echo(
                textwrap.fill(
                    summary,
                    width=width,
                    initial_indent="  ",
                    subsequent_indent="  ",
                )
            )


def _print_skill_mutation_report(report: SkillInstallReport) -> None:
    if not report.results:
        typer.echo("No matching skills were found.")
        return

    messages = {
        "already_installed": "Already installed",
        "updated": "Updated",
        "installed": "Installed",
        "not_installed": "Not installed",
        "uninstalled": "Uninstalled",
    }
    for item in report.results:
        prefix = messages.get(item.action, item.action.capitalize())
        line = f"{prefix} {item.name} -> {format_skill_install_target(item)}"
        if item.action in {"installed", "updated", "uninstalled"}:
            typer.secho(line, fg=typer.colors.GREEN)
        else:
            typer.echo(line)
    if any(item.action in SKILL_RESTART_ACTIONS for item in report.results):
        typer.echo()
        typer.secho(SKILL_RESTART_HINT, fg=typer.colors.YELLOW)


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
        for key, value in cast(Mapping[str, object], current_config).items():
            typer.echo(f"  {key}: {value}")


def _echo_callstack_layout(layout: str | None, error: str | None = None) -> None:
    if layout == "v1":
        typer.echo("Callstack layout: v1 (inline text)")
    elif layout == "v2":
        typer.echo("Callstack layout: v2 (deduplicated)")
    elif error:
        typer.secho(f"Warning: {error}", fg=typer.colors.YELLOW)


def _error(message: str) -> NoReturn:
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
