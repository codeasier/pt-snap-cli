from __future__ import annotations

import copy
import os
import sqlite3
from pathlib import Path
from typing import Any

from pt_snap_cli.context import Context, DatabaseNotFoundError, SchemaVersionError
from pt_snap_cli.core.context_cache import ContextCache
from pt_snap_cli.core.errors import (
    DatabaseMissingError,
    DatabaseSchemaError,
    FocusNotConfiguredError,
    InvalidCategoryError,
    InvalidDeviceError,
    QueryExecutionError,
    QueryTimeoutError,
    TemplateNotFoundError,
    TemplateRenderError,
)
from pt_snap_cli.core.focus_service import FocusService
from pt_snap_cli.core.models import QueryResult, TemplateInfo, TemplateParameter, TemplateSummary
from pt_snap_cli.query.executor import QueryExecutionError as ExecutorQueryExecutionError
from pt_snap_cli.query.executor import QueryExecutor
from pt_snap_cli.query.executor import QueryTimeoutError as ExecutorQueryTimeoutError
from pt_snap_cli.query.executor import TemplateRenderError as ExecutorTemplateRenderError
from pt_snap_cli.query.registry import (
    discover_categories,
    get_query,
    get_template_info,
    list_by_category_with_details,
    list_queries_with_details,
)

QUERY_TIMEOUT_ENV = "PT_SNAP_QUERY_TIMEOUT"


def resolve_query_timeout(explicit: float | None) -> float | None:
    """Return a positive timeout in seconds, or ``None`` when unbounded.

    An explicit argument wins. ``<= 0`` disables the timeout. Otherwise
    ``PT_SNAP_QUERY_TIMEOUT`` is read. Row limits (``max_rows`` / ``LIMIT``)
    are not a substitute for this value.
    """
    if explicit is not None:
        if isinstance(explicit, bool):
            raise QueryExecutionError("Query timeout must be a number of seconds")
        return float(explicit) if explicit > 0 else None
    raw = os.environ.get(QUERY_TIMEOUT_ENV)
    if raw is None or raw.strip() == "":
        return None
    try:
        value = float(raw)
    except ValueError as exc:
        raise QueryExecutionError(
            f"{QUERY_TIMEOUT_ENV} must be a number of seconds, got {raw!r}"
        ) from exc
    return value if value > 0 else None


class QueryService:
    def __init__(
        self,
        focus_service: FocusService | None = None,
        *,
        context_cache: ContextCache | None = None,
    ) -> None:
        self._focus_service = focus_service or FocusService()
        # Cache Context instances across calls so long-lived SnapshotAnalyzer
        # owners skip the per-call schema validation and
        # SQLite connect/close handshake. See ContextCache for the LRU and
        # mtime invalidation semantics.
        self._context_cache = context_cache if context_cache is not None else ContextCache()
        self._executor: QueryExecutor | None = None
        self._executor_context: Context | None = None

    @property
    def context_cache(self) -> ContextCache:
        """Return the :class:`ContextCache` backing this service."""
        return self._context_cache

    def invalidate_context_cache(self, db_path: Path | str | None = None) -> None:
        """Drop a cached context (or all of them when ``db_path`` is None)."""
        self._context_cache.invalidate(db_path)

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
        summaries: list[TemplateSummary] = []
        for row in template_rows:
            template = get_query(row["name"])
            summaries.append(
                TemplateSummary(
                    name=row["name"],
                    description=row["description"],
                    category=template.category if template is not None else category,
                )
            )
        return summaries

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
                    choices=param_details.get("choices"),
                )
                for param_name, param_details in info["parameters"].items()
            },
            output_schema=copy.deepcopy(info["output_schema"]),
            semantics_version=info.get("semantics_version"),
            interpretation_limits=(
                [str(item) for item in info["interpretation_limits"]]
                if isinstance(info.get("interpretation_limits"), list)
                else []
            ),
        )

    def execute_query(
        self,
        template: str,
        params: dict[str, Any] | None = None,
        db_path: Path | str | None = None,
        device_id: int | None = None,
        start_dir: Path | None = None,
        max_rows: int | None = None,
        *,
        exact_total: bool = False,
        timeout_s: float | None = None,
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
        executor = self._get_executor(ctx)
        query_params = params or {}
        timeout_s = resolve_query_timeout(timeout_s)

        try:
            rows, has_more, _applied_limit = executor.execute_template_page(
                template,
                query_params,
                device_id=target_device,
                max_rows=max_rows,
                timeout_s=timeout_s,
            )
            offset = _validated_offset(template, query_params)
            returned = len(rows)
            if exact_total:
                total = executor.count_template(
                    template,
                    query_params,
                    device_id=target_device,
                    timeout_s=timeout_s,
                    ignore_row_window=True,
                )
                total_is_exact = True
            else:
                total = returned
                total_is_exact = (not has_more) and offset == 0
            truncated = has_more or offset > 0 or (exact_total and total > returned)
        except ExecutorTemplateRenderError as exc:
            raise TemplateRenderError(str(exc)) from exc
        except ExecutorQueryTimeoutError as exc:
            raise QueryTimeoutError(str(exc)) from exc
        except ExecutorQueryExecutionError as exc:
            if get_query(template) is None:
                raise TemplateNotFoundError(f"Template '{template}' not found") from exc
            raise QueryExecutionError(str(exc)) from exc

        template_obj = get_query(template)
        return QueryResult(
            total=total,
            returned=returned,
            device_id=target_device,
            rows=rows,
            template=template,
            semantics_version=template_obj.semantics_version if template_obj is not None else None,
            has_more=has_more,
            truncated=truncated,
            total_is_exact=total_is_exact,
            timeout_s=timeout_s,
        )

    def _get_executor(self, ctx: Context) -> QueryExecutor:
        """Reuse the executor while its cached database context remains valid.

        Packaged templates are served by the registry, so the executor needs no
        template directory of its own.
        """
        if self._executor is None or self._executor_context is not ctx:
            self._executor = QueryExecutor(ctx)
            self._executor_context = ctx
        return self._executor

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
            return self._context_cache.get(db_path)
        except DatabaseNotFoundError as exc:
            raise DatabaseMissingError(str(exc)) from exc
        except (SchemaVersionError, sqlite3.DatabaseError) as exc:
            raise DatabaseSchemaError(str(exc)) from exc


def _validated_offset(template: str, params: dict[str, Any]) -> int:
    template_obj = get_query(template)
    if template_obj is None or "offset" not in template_obj.parameters:
        return 0
    try:
        validated = template_obj.validate_params(params)
    except (TypeError, ValueError):
        return 0
    raw = validated.get("offset")
    return raw if isinstance(raw, int) and raw > 0 else 0
