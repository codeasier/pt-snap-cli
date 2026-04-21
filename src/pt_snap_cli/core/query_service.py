from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from pt_snap_cli.context import Context, DatabaseNotFoundError, SchemaVersionError
from pt_snap_cli.core.errors import (
    DatabaseMissingError,
    DatabaseSchemaError,
    FocusNotConfiguredError,
    InvalidCategoryError,
    InvalidDeviceError,
    QueryExecutionError,
    TemplateNotFoundError,
    TemplateRenderError,
)
from pt_snap_cli.core.focus_service import FocusService
from pt_snap_cli.core.models import QueryResult, TemplateInfo, TemplateParameter, TemplateSummary
from pt_snap_cli.query.executor import QueryExecutionError as ExecutorQueryExecutionError
from pt_snap_cli.query.executor import QueryExecutor
from pt_snap_cli.query.executor import TemplateRenderError as ExecutorTemplateRenderError
from pt_snap_cli.query.registry import (
    discover_categories,
    get_query,
    get_template_info,
    list_by_category_with_details,
    list_queries_with_details,
)


class QueryService:
    def __init__(self, focus_service: FocusService | None = None) -> None:
        self._focus_service = focus_service or FocusService()

    def list_templates(
        self,
        category: str | None = None,
        validate_category: bool = True,
    ) -> list[TemplateSummary]:
        if category is not None and validate_category:
            categories = discover_categories()
            if category not in categories:
                raise InvalidCategoryError(
                    f"Invalid category '{category}'. Must be one of: {', '.join(categories)}"
                )

        template_rows = (
            list_by_category_with_details(category)
            if category is not None
            else list_queries_with_details()
        )
        return [
            TemplateSummary(
                name=row["name"],
                description=row["description"],
                category=(
                    get_query(row["name"]).category
                    if get_query(row["name"]) is not None
                    else category
                ),
            )
            for row in template_rows
        ]

    def get_template_info(self, name: str) -> TemplateInfo:
        template = get_query(name)
        if template is None:
            raise TemplateNotFoundError(f"Template '{name}' not found")

        info = get_template_info(name)
        if info is None:
            raise TemplateNotFoundError(f"Template '{name}' not found")

        devices = info["devices"]
        if isinstance(devices, list):
            devices = ", ".join(devices)

        return TemplateInfo(
            name=info["name"],
            description=info["description"],
            category=template.category,
            devices=devices,
            parameters={
                param_name: TemplateParameter(
                    type=param_details["type"],
                    default=param_details["default"],
                    required=param_details["required"],
                    description=param_details["description"],
                )
                for param_name, param_details in info["parameters"].items()
            },
            output_schema=info["output_schema"],
        )

    def execute_query(
        self,
        template: str,
        params: dict[str, Any] | None = None,
        db_path: Path | str | None = None,
        device_id: int | None = None,
        start_dir: Path | None = None,
        max_rows: int | None = None,
    ) -> QueryResult:
        resolved = self._focus_service.resolve_focus(
            explicit_db_path=db_path,
            explicit_device_id=device_id,
            start_dir=start_dir,
        )
        if resolved.db_path is None:
            raise FocusNotConfiguredError("No database path specified and no database configured.")

        ctx = self._validated_context(resolved.db_path)
        target_device = self._resolve_device_id(ctx, resolved.device_id, device_id)
        executor = QueryExecutor(
            ctx, template_dir=Path(__file__).parent.parent / "query" / "templates"
        )

        try:
            rows = executor.execute_template(template, params or {}, device_id=target_device)
        except ExecutorTemplateRenderError as exc:
            raise TemplateRenderError(str(exc)) from exc
        except ExecutorQueryExecutionError as exc:
            if get_query(template) is None:
                raise TemplateNotFoundError(f"Template '{template}' not found") from exc
            raise QueryExecutionError(str(exc)) from exc

        if max_rows is None or max_rows <= 0:
            limited_rows = rows
        else:
            limited_rows = rows[:max_rows]

        return QueryResult(
            total=len(rows),
            returned=len(limited_rows),
            device_id=target_device,
            rows=limited_rows,
        )

    def _resolve_device_id(
        self,
        ctx: Context,
        focused_device_id: int | None,
        explicit_device_id: int | None,
    ) -> int | None:
        if explicit_device_id is not None:
            if explicit_device_id not in ctx.device_ids:
                raise InvalidDeviceError(
                    f"Device {explicit_device_id} not found. Available: {ctx.device_ids}"
                )
            return explicit_device_id

        if focused_device_id is not None:
            if focused_device_id not in ctx.device_ids:
                raise InvalidDeviceError(
                    f"Device {focused_device_id} not found. Available: {ctx.device_ids}"
                )
            return focused_device_id

        if not ctx.device_ids:
            raise InvalidDeviceError("No devices found in database.")
        return ctx.device_ids[0]

    def _validated_context(self, db_path: Path) -> Context:
        try:
            return Context(db_path)
        except DatabaseNotFoundError as exc:
            raise DatabaseMissingError(str(exc)) from exc
        except (SchemaVersionError, sqlite3.DatabaseError) as exc:
            raise DatabaseSchemaError(str(exc)) from exc
