"""Report command group, backed by the shared report service."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Literal

import typer

from pt_snap_cli.cli_output import (
    error as _error,
)
from pt_snap_cli.cli_output import (
    error_from_exc as _error_from_exc,
)
from pt_snap_cli.cli_output import (
    json_flag as _json_flag,
)
from pt_snap_cli.cli_output import (
    print_peak_memory_report as _print_peak_memory_report,
)
from pt_snap_cli.completion import complete_device_ids
from pt_snap_cli.core import (
    DatabaseMissingError,
    DatabaseSchemaError,
    FocusFileInvalidError,
    FocusNotConfiguredError,
    FocusService,
    InvalidDeviceError,
    InvalidParameterError,
    QueryExecutionError,
    ReportService,
    TemplateNotFoundError,
    TemplateRenderError,
)
from pt_snap_cli.core.error_codes import DATABASE_NOT_FOUND, INVALID_PARAMETER

report_app = typer.Typer(help="Generate memory analysis reports")


@report_app.command("peak-memory")
def report_peak_memory(
    db_path: Annotated[
        Path | None, typer.Argument(help="Path to database file (optional if configured)")
    ] = None,
    device: Annotated[
        int | None,
        typer.Option(
            "--device", "-d", help="Device ID to report", autocompletion=complete_device_ids
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
    limit: Annotated[
        int,
        typer.Option(
            "--limit", "-n", help="Maximum dynamic callstack groups (static/preexisting are extra)"
        ),
    ] = 20,
    stack_bytes: Annotated[
        int,
        typer.Option(
            "--stack-bytes",
            help="Opt-in UTF-8 byte budget per callstack (0: identity only; negative: full text). Not a response byte cap or token budget.",
        ),
    ] = -1,
    start_id: Annotated[
        int | None, typer.Option("--start-id", help="First real event ID in peak range")
    ] = None,
    end_id: Annotated[
        int | None, typer.Option("--end-id", help="Last real event ID in peak range")
    ] = None,
    timeout: Annotated[
        float | None,
        typer.Option("--timeout", help="One report-wide deadline in seconds; <=0 disables"),
    ] = None,
    json_output: Annotated[bool, _json_flag()] = False,
) -> None:
    """Generate a peak memory attribution report."""
    focus_service = FocusService()
    report_service = ReportService(focus_service)
    try:
        report = report_service.peak_memory_report(
            db_path=db_path,
            device_id=device,
            metric=metric,
            include_static=include_static,
            limit=limit,
            stack_bytes=stack_bytes,
            start_id=start_id,
            end_id=end_id,
            timeout_s=timeout,
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
        extra: list[str] = []
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
        InvalidParameterError,
        QueryExecutionError,
        DatabaseSchemaError,
    ) as e:
        _error_from_exc(e, text_prefix="Error generating report: ")
    finally:
        report_service.close()

    if json_output:
        typer.echo(json.dumps(asdict(report), indent=2))
        return
    _print_peak_memory_report(report)
