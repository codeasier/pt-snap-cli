"""CLI entry point for pt-snap-cli."""

from __future__ import annotations

import json
import shlex
import shutil
import sys
import textwrap
from collections.abc import Mapping, Sequence
from contextvars import ContextVar
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any, Literal, NoReturn, cast

import typer
from typer.exceptions import Abort, Exit

try:
    from typer._click.exceptions import ClickException
except ImportError:  # typer < 0.27
    from click.exceptions import ClickException

try:
    from click.exceptions import Abort as ClickAbort
except ImportError:  # pragma: no cover
    ClickAbort = Abort

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
    FocusState,
    ImportExecutionError,
    ImportMetadataService,
    ImportOptions,
    ImportResult,
    ImportService,
    ImportToolMissingError,
    InvalidCategoryError,
    InvalidDeviceError,
    InvalidSkillTargetError,
    JsonValue,
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
    SplitResult,
    SplitService,
    TemplateInfo,
    TemplateNotFoundError,
    TemplateRenderError,
    classify_error,
    dumps_json,
    json_error,
    json_success,
)
from pt_snap_cli.core.error_codes import DATABASE_NOT_FOUND, ERROR, INVALID_PARAMETER
from pt_snap_cli.core.models import SKILL_RESTART_ACTIONS, SKILL_RESTART_HINT
from pt_snap_cli.core.skill_service import (
    format_skill_install_target,
    format_skill_location,
    human_skill_summary,
    parse_host_option,
)
from pt_snap_cli.query.config import OUTPUT_COLUMN_OPTIONAL
from pt_snap_cli.query.executor import reported_sql_limit
from pt_snap_cli.query.registry import discover_categories, get_query

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


# Typer 0.27+ vendors Click as typer._click. Reading click.get_current_context()
# therefore misses the live command and would keep JSON errors on stdout.
_JSON_MODE: ContextVar[bool] = ContextVar("pt_snap_json_mode", default=False)


def _json_mode() -> bool:
    return _JSON_MODE.get()


def _set_json_mode(value: bool) -> bool:
    _JSON_MODE.set(bool(value))
    return value


def _json_flag() -> Any:
    return typer.Option(
        "--json",
        help="Emit machine-readable JSON",
        callback=_set_json_mode,
    )


def _emit_json(payload: object) -> None:
    try:
        typer.echo(dumps_json(payload))
    except TypeError as exc:
        _error(
            str(exc),
            code=ERROR,
            hint="Result contained a value that cannot be serialized to JSON.",
        )


def _focus_fields(state: FocusState) -> dict[str, object]:
    db_path = str(state.db_path) if state.db_path is not None else None
    return {
        "configured": state.db_path is not None,
        "db_path": db_path,
        "focus_source": state.source,
        "focus_file": str(state.focus_file) if state.focus_file is not None else None,
        "device_id": state.device_id,
        "available_devices": list(state.available_devices),
        "callstack_layout": state.callstack_layout,
        "callstack_layout_error": state.callstack_layout_error,
        "db_exists": bool(state.db_path is not None and state.db_path.exists()),
    }


def _focus_json(state: FocusState, *, action: str, **extra: object) -> dict[str, JsonValue]:
    return json_success(action=action, **_focus_fields(state), **extra)


def _import_json(result: ImportResult) -> dict[str, JsonValue]:
    focus_state = _focus_fields(result.focus_state) if result.focus_state is not None else None
    return json_success(
        db_path=str(result.db_path),
        device_id=result.device_id,
        reused=result.reused,
        cache_miss_reason=result.cache_miss_reason,
        metadata=asdict(result.metadata),
        focus_state=focus_state,
        focus_source=result.focus_state.source if result.focus_state is not None else None,
    )


def _split_json(result: SplitResult) -> dict[str, JsonValue]:
    return json_success(
        output=str(result.output),
        files=[str(path) for path in result.files],
        devices=list(result.devices),
        format=result.format,
    )


def _template_info_dict(info: TemplateInfo) -> dict[str, object]:
    return {
        "name": info.name,
        "description": info.description,
        "category": info.category,
        "devices": info.devices,
        "parameters": {
            param_name: {
                "type": param.type,
                "default": param.default,
                "required": param.required,
                "description": param.description,
                "choices": param.choices,
            }
            for param_name, param in info.parameters.items()
        },
        "output_schema": info.output_schema,
        "semantics_version": info.semantics_version,
        "interpretation_limits": list(info.interpretation_limits),
    }


def _effective_query_params(
    template: str,
    params: dict[str, object],
    max_rows: int | None = None,
) -> dict[str, object]:
    query_template = get_query(template)
    if query_template is None:
        return params
    try:
        validated = dict(query_template.validate_params(params))
    except (TypeError, ValueError) as exc:
        raise TemplateRenderError(
            f"Failed to validate parameters for template '{template}': {exc}"
        ) from exc
    sql_limit = reported_sql_limit(validated, max_rows, parameters=query_template.parameters)
    if sql_limit is not None:
        validated["limit"] = sql_limit
    return validated


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
        _error(
            "--dir cannot be combined with --target.",
            code=INVALID_PARAMETER,
            hint="Use either --dir or --target.",
        )
    if project:
        _error(
            "--dir cannot be combined with --project.",
            code=INVALID_PARAMETER,
            hint="Use either --dir or --project.",
        )
    if user:
        _error(
            "--dir cannot be combined with --user.",
            code=INVALID_PARAMETER,
            hint="Use either --dir or --user.",
        )
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
    _JSON_MODE.set(False)


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
    json_output: Annotated[bool, _json_flag()] = False,
) -> None:
    """Set the current analysis focus (database and optional device)."""
    focus_service = _focus_service()

    if db_path is None and device is None:
        try:
            state = focus_service.get_focus()
        except FocusFileInvalidError as e:
            _error_from_exc(e)

        if json_output:
            _emit_json(_focus_json(state, action="read"))
            raise typer.Exit()
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
        _error(
            "--session and --global cannot be used together.",
            code=INVALID_PARAMETER,
            hint="Choose either --session or --global.",
        )
    if session and device is not None:
        _error(
            "--device cannot be used with --session; session focus exports only a database path.",
            code=INVALID_PARAMETER,
            hint="Omit --device; session focus exports only PT_SNAP_DB_PATH.",
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
            _error_from_exc(e)

        if json_output:
            _emit_json(_focus_json(state, action="set_device"))
            raise typer.Exit()
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
            export_line = f"export {ENV_DB_PATH}={shlex.quote(str(state.db_path))}"
            if json_output:
                _emit_json(
                    _focus_json(
                        state,
                        action="validate_session",
                        session_applied=False,
                        env={
                            "name": ENV_DB_PATH,
                            "value": str(state.db_path),
                            "export": export_line,
                        },
                    )
                )
                return
            typer.echo(export_line)
            return
        if global_focus:
            state = focus_service.set_global_focus(focus_db_path, device)
            action = "set_global"
            if not json_output:
                typer.secho(f"Using global database: {state.db_path}", fg=typer.colors.GREEN)
        else:
            state = focus_service.set_project_focus(focus_db_path, device)
            action = "set_project"
            if not json_output:
                typer.secho(f"Using project database: {state.db_path}", fg=typer.colors.GREEN)
                if state.focus_file:
                    typer.echo(f"Focus file: {state.focus_file}")
        if json_output:
            _emit_json(_focus_json(state, action=action))
            return
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
        _error_from_exc(e)


@app.command("import")
def import_snapshot(
    snapshot_file: Annotated[Path, typer.Argument(help="Path to .pkl snapshot")],
    output_dir: Annotated[Path | None, typer.Option("--output-dir", "-o")] = None,
    device: Annotated[int | None, typer.Option("--device", "-d")] = None,
    no_focus: Annotated[bool, typer.Option("--no-focus", help="Skip focus update")] = False,
    force: Annotated[bool, typer.Option("--force", help="Rebuild even when cache matches")] = False,
    json_output: Annotated[bool, _json_flag()] = False,
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
        _error_from_exc(e)

    if json_output:
        _emit_json(_import_json(result))
        return

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
    json_output: Annotated[bool, _json_flag()] = False,
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
        _error_from_exc(exc)

    if json_output:
        _emit_json(_split_json(result))
        return

    typer.echo(f"Split: {result.output}")
    typer.echo(f"Devices: {', '.join(map(str, result.devices))}")
    typer.echo(f"Files: {len(result.files)}")


@app.command("metadata")
def show_database_metadata(
    db_path: Annotated[
        Path | None, typer.Argument(help="Path to database file (optional if configured)")
    ] = None,
    json_output: Annotated[bool, _json_flag()] = False,
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
        _error_from_exc(e)

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
    exact_total: Annotated[
        bool,
        typer.Option(
            "--exact-total",
            help="Compute an exact matching-row total with a COUNT query (default: total equals returned rows)",
        ),
    ] = False,
    timeout: Annotated[
        float | None,
        typer.Option(
            "--timeout",
            help="Query execution timeout in seconds (separate from -n; <= 0 disables; default: PT_SNAP_QUERY_TIMEOUT or unlimited)",
        ),
    ] = None,
    json_output: Annotated[bool, _json_flag()] = False,
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
            listed: list[dict[str, object]] = []
            any_found = False
            for cat in filter_cats:
                details = query_service.list_templates(cat, validate_category=False)
                if details:
                    any_found = True
                    if json_output:
                        listed.extend(
                            {
                                "name": info.name,
                                "description": info.description,
                                "category": info.category,
                            }
                            for info in details
                        )
                        continue
                    typer.secho(f"{category_labels[cat]}:", fg=typer.colors.GREEN, bold=True)
                    for info in details:
                        typer.secho(f"  {info.name}", fg=typer.colors.GREEN, bold=True)
                        typer.echo(f"    {info.description}")
                    typer.echo()
            if json_output:
                _emit_json(json_success(category=category, templates=listed))
                raise typer.Exit()
            if not any_found:
                typer.echo("No query templates available.")
        except InvalidCategoryError as e:
            _error_from_exc(e)
        raise typer.Exit()

    if template_info:
        try:
            info = query_service.get_template_info(template_info)
        except TemplateNotFoundError as e:
            _error_from_exc(e)

        if json_output:
            _emit_json(json_success(template=info.name, **_template_info_dict(info)))
            raise typer.Exit()

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
        _error(
            "--template-use is required when not using --list or --template-info",
            code=INVALID_PARAMETER,
            hint="Pass --template-use, --list, or --template-info.",
        )

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
            exact_total=exact_total,
            timeout_s=timeout,
        )
        if json_output:
            resolved = focus_service.resolve_focus(
                explicit_db_path=db_path,
                explicit_device_id=device,
            )
            _emit_json(
                json_success(
                    db_path=str(resolved.db_path) if resolved.db_path is not None else None,
                    focus_source=resolved.source,
                    device_id=result.device_id,
                    template=result.template,
                    effective_params=_effective_query_params(
                        template_use, query_params, max_rows=max_rows
                    ),
                    semantics_version=result.semantics_version,
                    total=result.total,
                    returned=result.returned,
                    has_more=result.has_more,
                    truncated=result.truncated,
                    total_is_exact=result.total_is_exact,
                    timeout_s=result.timeout_s,
                    rows=result.rows,
                )
            )
            return
        if result.rows:
            typer.echo(f"Found {result.total} results, showing {result.returned}:")
            for row in result.rows:
                typer.echo(f"  {row}")
            if result.has_more:
                if result.total_is_exact and result.total > result.returned:
                    typer.echo(
                        f"  ... and {result.total - result.returned} more (use -n to show more)"
                    )
                else:
                    typer.echo("  ... more available (use -n, offset, top_n, or --exact-total)")
        else:
            typer.echo("No results found.")
    except FocusFileInvalidError as e:
        _error_from_exc(e)
    except FocusNotConfiguredError as e:
        _error_from_exc(
            e,
            extra_lines=(
                "Use 'pt-snap focus <database_path>' to set a project database, or provide db_path argument.",
            ),
        )
    except DatabaseMissingError:
        try:
            state = focus_service.get_focus(explicit_db_path=db_path, explicit_device_id=device)
        except FocusFileInvalidError:
            state = None
        source = state.source if state is not None else "configured"
        path = state.db_path if state is not None else db_path
        extra = []
        if state is not None and state.focus_file:
            extra.append(f"Focus file: {state.focus_file}")
        extra.append(
            "Use 'pt-snap focus <new_database_path>' to set a new project database, or provide db_path argument."
        )
        _error(
            f"Database from {source} focus not found: {path}",
            code=DATABASE_NOT_FOUND,
            hint="Use 'pt-snap focus <new_database_path>' or pass a database path that exists.",
            extra_lines=tuple(extra),
        )
    except InvalidDeviceError as e:
        if str(e) == "No devices found in database." and not json_output:
            typer.echo("No devices found in database.")
            raise typer.Exit() from None
        _error_from_exc(e)
    except TemplateNotFoundError as e:
        _error_from_exc(e, text_prefix="Error executing query: ")
    except (
        TemplateRenderError,
        QueryExecutionError,
        DatabaseSchemaError,
        json.JSONDecodeError,
    ) as e:
        _error_from_exc(e, text_prefix="Error executing query: ")


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
    json_output: Annotated[bool, _json_flag()] = False,
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
        _error(str(e), code=INVALID_PARAMETER, hint="Use --metric active, allocated, or reserved.")
    except FocusFileInvalidError as e:
        _error_from_exc(e)
    except FocusNotConfiguredError as e:
        _error_from_exc(
            e,
            extra_lines=(
                "Use 'pt-snap focus <database_path>' to set a project database, or provide db_path argument.",
            ),
        )
    except DatabaseMissingError:
        try:
            state = focus_service.get_focus(explicit_db_path=db_path, explicit_device_id=device)
        except FocusFileInvalidError:
            state = None
        source = state.source if state is not None else "configured"
        path = state.db_path if state is not None else db_path
        extra = []
        if state is not None and state.focus_file:
            extra.append(f"Focus file: {state.focus_file}")
        extra.append(
            "Use 'pt-snap focus <new_database_path>' to set a new project database, or provide db_path argument."
        )
        _error(
            f"Database from {source} focus not found: {path}",
            code=DATABASE_NOT_FOUND,
            hint="Use 'pt-snap focus <new_database_path>' or pass a database path that exists.",
            extra_lines=tuple(extra),
        )
    except InvalidDeviceError as e:
        _error_from_exc(e)
    except (
        TemplateNotFoundError,
        TemplateRenderError,
        QueryExecutionError,
        DatabaseSchemaError,
    ) as e:
        _error_from_exc(e, text_prefix="Error generating report: ")

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
    json_output: Annotated[bool, _json_flag()] = False,
) -> None:
    """List bundled agent skills and whether they are installed."""
    if project and user:
        _error(
            "--project and --user cannot be used together.",
            code=INVALID_PARAMETER,
            hint="Choose either --project or --user.",
        )
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
        _error_from_exc(e)

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
    json_output: Annotated[bool, _json_flag()] = False,
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
        _error_from_exc(e)

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
    json_output: Annotated[bool, _json_flag()] = False,
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
        _error_from_exc(e)

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
    json_output: Annotated[bool, _json_flag()] = False,
) -> None:
    """Remove bundled agent skills.

    Without --target, --project, or --dir, remove every SKILL.md copy that
    `pt-snap skill list` would report. A same-named path without SKILL.md
    aborts the whole uninstall. Use those flags to limit destinations.
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
        _error_from_exc(e)

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
    json_output: Annotated[bool, _json_flag()] = False,
) -> None:
    """Show or manage pt-snap configuration."""
    focus_service = _focus_service()
    config_path = str(focus_service.get_global_config_path())

    if show_path:
        if json_output:
            _emit_json(json_success(action="path", path=config_path))
        else:
            typer.echo(f"Config file: {focus_service.get_global_config_path()}")
        raise typer.Exit()

    if clear:
        focus_service.clear_global_focus()
        if json_output:
            _emit_json(json_success(action="clear", cleared=True, path=config_path))
        else:
            typer.secho("Configuration cleared.", fg=typer.colors.GREEN)
        raise typer.Exit()

    current_config = focus_service.show_global_config()
    if json_output:
        _emit_json(json_success(action="show", path=config_path, config=current_config))
        return
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


def _error(
    message: str,
    *,
    code: str | None = None,
    hint: str | None = None,
    extra_lines: tuple[str, ...] = (),
    text_prefix: str = "Error: ",
) -> NoReturn:
    if _json_mode():
        typer.echo(dumps_json(json_error(code or ERROR, message, hint)), err=True)
        raise typer.Exit(1) from None
    typer.secho(f"{text_prefix}{message}", fg=typer.colors.RED)
    for line in extra_lines:
        typer.echo(line)
    raise typer.Exit(1) from None


def _error_from_exc(
    exc: BaseException,
    *,
    extra_lines: tuple[str, ...] = (),
    text_prefix: str = "Error: ",
) -> NoReturn:
    code, hint = classify_error(exc)
    _error(str(exc), code=code, hint=hint, extra_lines=extra_lines, text_prefix=text_prefix)


# Flag-only options used when a parse failure happens before the --json callback.
# A following --json is treated as a value of the previous option otherwise.
_FLAG_ONLY_OPTIONS = frozenset(
    {
        "--json",
        "--version",
        "-v",
        "--session",
        "--global",
        "--no-focus",
        "--force",
        "--list",
        "--project",
        "--user",
        "--clear",
        "--path",
        "--help",
        "-h",
        "--include-static",
        "--exclude-static",
        "--exact-total",
    }
)


def _argv_token_takes_value(token: str | None) -> bool:
    """True when the next argv token would be this option's value."""
    if token is None or token in _FLAG_ONLY_OPTIONS or "=" in token:
        return False
    try:
        _ = float(token)
    except ValueError:
        return token.startswith("-")
    return False


def _argv_requests_json(argv: Sequence[str]) -> bool:
    """Best-effort pre-parse scan for a ``--json`` flag.

    ContextVar state is not set when Click fails before the option callback.
    Tokens after ``--`` are ignored. ``--json`` immediately after a
    value-taking option is treated as that option's value, not as the flag.
    ``--opt=value`` and numeric tokens such as ``-1`` do not consume the
    next argument.
    """
    previous: str | None = None
    for arg in argv:
        if arg == "--":
            break
        if arg == "--json" and not _argv_token_takes_value(previous):
            return True
        previous = arg
    return False


def _json_requested() -> bool:
    return _json_mode() or _argv_requests_json(sys.argv[1:])


def _emit_aborted() -> None:
    if _json_requested():
        typer.echo(
            dumps_json(
                json_error(
                    ERROR,
                    "Aborted!",
                    "The command was interrupted before it finished.",
                )
            ),
            err=True,
        )
        return
    typer.echo("Aborted!", err=True)


def _safe_call() -> int:
    try:
        # Typer 0.27's non-standalone _main catches Exit and returns the
        # code. Discarding that value made every domain _error() exit 0.
        rv = app(standalone_mode=False)
        code = rv if isinstance(rv, int) else 0
    except ClickException as exc:
        if _json_requested():
            typer.echo(
                dumps_json(
                    json_error(
                        INVALID_PARAMETER,
                        exc.format_message(),
                        "Fix the command-line usage and retry. Use --help for options.",
                    )
                ),
                err=True,
            )
            return exc.exit_code
        exc.show()
        return exc.exit_code
    except Exit as exc:
        code = int(exc.exit_code)
    except (Abort, ClickAbort):
        _emit_aborted()
        return 1
    except KeyError as e:
        if str(e) in ("'COMP_WORDS'", "'COMP_LINE'", "'COMP_POINT'"):
            return 1
        raise
    if code == 130:
        _emit_aborted()
    return code


if __name__ == "__main__":
    sys.exit(_safe_call())
