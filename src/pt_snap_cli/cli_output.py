"""Shared CLI output and JSON error adaptation; no product decisions live here."""

from __future__ import annotations

import shutil
import textwrap
from contextvars import ContextVar
from typing import NoReturn, cast

import typer
from typer.models import OptionInfo

from pt_snap_cli.core import (
    DatabaseOverview,
    PeakMemoryReport,
    SkillInstallReport,
    SkillListing,
    classify_error,
    dumps_json,
    json_error,
)
from pt_snap_cli.core.error_codes import ERROR
from pt_snap_cli.core.models import SKILL_RESTART_ACTIONS, SKILL_RESTART_HINT
from pt_snap_cli.core.skill_service import (
    format_skill_install_target,
    format_skill_location,
    human_skill_summary,
)

# Typer 0.27+ vendors Click, so its context cannot be read via click.get_current_context.
JSON_MODE: ContextVar[bool] = ContextVar("pt_snap_json_mode", default=False)


def json_mode() -> bool:
    return JSON_MODE.get()


def _set_json_mode(value: bool) -> bool:
    _ = JSON_MODE.set(bool(value))
    return value


def json_flag() -> OptionInfo:
    return cast(
        OptionInfo,
        typer.Option("--json", help="Emit machine-readable JSON", callback=_set_json_mode),
    )


def emit_json(payload: object) -> None:
    try:
        typer.echo(dumps_json(payload))
    except TypeError as exc:
        error(
            str(exc),
            code=ERROR,
            hint="Result contained a value that cannot be serialized to JSON.",
        )


def error(
    message: str,
    *,
    code: str | None = None,
    hint: str | None = None,
    extra_lines: tuple[str, ...] = (),
    text_prefix: str = "Error: ",
) -> NoReturn:
    if json_mode():
        typer.echo(dumps_json(json_error(code or ERROR, message, hint)), err=True)
        raise typer.Exit(1) from None
    typer.secho(f"{text_prefix}{message}", fg=typer.colors.RED)
    for line in extra_lines:
        typer.echo(line)
    raise typer.Exit(1) from None


def error_from_exc(
    exc: BaseException,
    *,
    extra_lines: tuple[str, ...] = (),
    text_prefix: str = "Error: ",
) -> NoReturn:
    code, hint = classify_error(exc)
    error(str(exc), code=code, hint=hint, extra_lines=extra_lines, text_prefix=text_prefix)


def echo_callstack_layout(layout: str | None, error: str | None = None) -> None:
    if layout == "v1":
        typer.echo("Callstack layout: v1 (inline text)")
    elif layout == "v2":
        typer.echo("Callstack layout: v2 (deduplicated)")
    elif error:
        typer.secho(f"Warning: {error}", fg=typer.colors.YELLOW)


def print_peak_memory_report(report: PeakMemoryReport) -> None:
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


def print_skill_listings(listings: list[SkillListing]) -> None:
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
                textwrap.fill(summary, width=width, initial_indent="  ", subsequent_indent="  ")
            )


def print_skill_mutation_report(report: SkillInstallReport) -> None:
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


def print_database_overview(overview: DatabaseOverview) -> None:
    inspection = overview.metadata
    typer.echo(f"Database: {overview.db_path}")
    typer.echo(f"Focus source: {overview.focus_source}")
    typer.echo(f"Import metadata: {inspection.status}")
    if inspection.reason is not None:
        typer.echo(f"Metadata reason: {inspection.reason}")
    if not overview.devices:
        typer.echo("Devices: none")
        return
    typer.echo("Devices:")
    for device in overview.devices:
        if device.first_event_id is None or device.last_event_id is None:
            typer.echo(f"  {device.device_id}: no events")
        else:
            typer.echo(
                f"  {device.device_id}: events {device.first_event_id}..{device.last_event_id}"
            )
