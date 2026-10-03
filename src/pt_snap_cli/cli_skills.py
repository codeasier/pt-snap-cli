"""Skill command group; destination and mutation semantics belong to SkillService."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

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
    print_skill_listings as _print_skill_listings,
)
from pt_snap_cli.cli_output import (
    print_skill_mutation_report as _print_skill_mutation_report,
)
from pt_snap_cli.completion import complete_skill_names, complete_skill_targets
from pt_snap_cli.core import (
    InvalidSkillTargetError,
    SkillCatalogError,
    SkillInstallError,
    SkillNotFoundError,
    SkillService,
)
from pt_snap_cli.core.error_codes import INVALID_PARAMETER
from pt_snap_cli.core.skill_service import parse_host_option

skill_app = typer.Typer(help="Manage bundled agent skills", no_args_is_help=True)


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
    service = SkillService()
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
    service = SkillService()
    try:
        report = service.install_skills(
            names,
            hosts=None if custom_dir is not None else parse_host_option(target),
            scope="project" if project else "user",
            force=force,
            dest_dir=custom_dir,
        )
    except (SkillCatalogError, SkillNotFoundError, InvalidSkillTargetError, SkillInstallError) as e:
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
        typer.Option("--dir", help="Upgrade skills in this directory instead of a built-in host"),
    ] = None,
    json_output: Annotated[bool, _json_flag()] = False,
) -> None:
    """Replace outdated installed skills with the bundled copies."""
    custom_dir = _skill_dest_dir(dest_dir, target, project=project)
    service = SkillService()
    try:
        report = service.upgrade_skills(
            names,
            hosts=None if custom_dir is not None else parse_host_option(target),
            scope="project" if project else "user",
            dest_dir=custom_dir,
        )
    except (SkillCatalogError, SkillNotFoundError, InvalidSkillTargetError, SkillInstallError) as e:
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
            "--dir", help="Uninstall skills from this directory instead of a built-in host"
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
    service = SkillService()
    try:
        unfiltered = custom_dir is None and target is None and not project
        report = service.uninstall_skills(
            names,
            hosts=None if custom_dir is not None else parse_host_option(target),
            scope="project" if project else "user",
            dest_dir=custom_dir,
            all_locations=unfiltered,
        )
    except (SkillCatalogError, SkillNotFoundError, InvalidSkillTargetError, SkillInstallError) as e:
        _error_from_exc(e)
    if json_output:
        typer.echo(json.dumps(service.install_report_to_dict(report), indent=2))
        return
    _print_skill_mutation_report(report)
