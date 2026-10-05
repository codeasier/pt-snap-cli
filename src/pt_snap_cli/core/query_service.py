from __future__ import annotations

import copy
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

from pt_snap_cli.context import Context, DatabaseNotFoundError, SchemaVersionError
from pt_snap_cli.core.context_cache import ContextCache
from pt_snap_cli.core.dataset_attribution import event_attribution, summarize_dataset_stacks
from pt_snap_cli.core.dataset_contract import QueryScope
from pt_snap_cli.core.dataset_resolver import DatasetResolver, ResolvedDataset
from pt_snap_cli.core.dataset_sources import DatasetSourceResolver, QueryBudget
from pt_snap_cli.core.errors import (
    DatabaseMissingError,
    DatabaseSchemaError,
    FocusNotConfiguredError,
    InvalidCategoryError,
    InvalidDeviceError,
    InvalidParameterError,
    QueryExecutionError,
    QueryTimeoutError,
    TemplateNotFoundError,
    TemplateRenderError,
)
from pt_snap_cli.core.focus_service import FocusService
from pt_snap_cli.core.models import QueryResult, TemplateInfo, TemplateParameter, TemplateSummary
from pt_snap_cli.core.stack_summary import summarize_stacks
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
            raise InvalidParameterError("Query timeout must be a number of seconds")
        return float(explicit) if explicit > 0 else None
    raw = os.environ.get(QUERY_TIMEOUT_ENV)
    if raw is None or raw.strip() == "":
        return None
    try:
        value = float(raw)
    except ValueError as exc:
        raise InvalidParameterError(
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
        self._owns_context_cache: bool = context_cache is None
        self._executor: QueryExecutor | None = None
        self._executor_context: Context | None = None

    @property
    def context_cache(self) -> ContextCache:
        """Return the :class:`ContextCache` backing this service."""
        return self._context_cache

    def close(self) -> None:
        """Release owned connections and executor references; allow later reuse.

        An injected cache is borrowed and must be closed by its owner.
        """
        self._executor = None
        self._executor_context = None
        if self._owns_context_cache:
            self._context_cache.close()

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
            devices = ", ".join(str(item) for item in devices)

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

    def list_template_contracts(self, category: str | None = None) -> list[TemplateInfo]:
        """Return full template contracts, matching ``get_template_info`` per name."""
        return [self.get_template_info(item.name) for item in self.list_templates(category)]

    @staticmethod
    def template_info_to_dict(info: TemplateInfo) -> dict[str, Any]:
        """Serialize a template contract for CLI/API JSON adapters."""
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
        slice_index: int | None = None,
    ) -> QueryResult:
        timeout_s = resolve_query_timeout(timeout_s)
        started = time.monotonic()
        budget = QueryBudget(timeout_s, started)
        resolved = self._focus_service.resolve_focus(
            explicit_db_path=db_path,
            explicit_device_id=device_id,
            start_dir=start_dir,
        )
        if resolved.db_path is None:
            raise FocusNotConfiguredError("No database path specified and no database configured.")

        dataset = DatasetResolver().inspect(resolved.db_path)
        budget.remaining()
        scope: dict[str, object] | None = None
        query_params = params or {}
        sources: DatasetSourceResolver | None = None
        if dataset is not None:
            selected = dataset.device(device_id if device_id is not None else resolved.device_id)
            sources = DatasetSourceResolver(
                dataset, selected.device_id, self._context_cache, budget
            )
            if template in ("active_blocks_at_event", "active_memory_callstack_at_event"):
                template_obj = get_query(template)
                if template_obj is None:
                    raise TemplateNotFoundError(f"Template '{template}' not found")
                try:
                    validated = template_obj.validate_params(query_params)
                except (TypeError, ValueError) as exc:
                    raise TemplateRenderError(str(exc)) from exc
                if slice_index is not None:
                    dataset.paths(QueryScope("slice", selected.device_id, slice_index))
                result = event_attribution(
                    sources,
                    template,
                    validated,
                    max_rows,
                    exact_total,
                    slice_index,
                    template_obj.semantics_version,
                )
                stack_bytes = validated.get("stack_bytes")
                if isinstance(stack_bytes, int) and stack_bytes >= 0:
                    summarize_dataset_stacks(result.rows, stack_bytes)
                budget.remaining()
                return result
            member, query_params, scope = self._dataset_query(
                dataset, selected.device_id, template, query_params, slice_index
            )
            ctx = self._validated_context(
                member, generation=dataset.fingerprint, immutable=dataset.callstack_layout == "v1"
            )
            target_device = selected.device_id
        else:
            if slice_index is not None:
                raise InvalidParameterError("slice_index requires a manifest dataset.")
            ctx = self._validated_context(resolved.db_path)
            target_device = self._resolve_device_id(ctx, resolved.device_id, device_id)
        executor = self._get_executor(ctx)

        try:
            rows, has_more, _applied_limit = executor.execute_template_page(
                template,
                query_params,
                device_id=target_device,
                max_rows=max_rows,
                timeout_s=budget.remaining(),
            )
            offset = _validated_offset(template, query_params)
            rank_cap = _finite_top_n(template, query_params)
            if rank_cap is not None and _inner_rank_window_full(rows, rank_cap):
                has_more = True
            returned = len(rows)
            if exact_total:
                total = executor.count_template(
                    template,
                    query_params,
                    device_id=target_device,
                    timeout_s=_remaining_timeout(timeout_s, started),
                    ignore_row_window=True,
                )
                total_is_exact = True
                if offset == 0:
                    has_more = total > returned
            else:
                total = returned
                total_is_exact = (not has_more) and offset == 0
            truncated = has_more or offset > 0 or (exact_total and total > returned)
        except ExecutorTemplateRenderError as exc:
            raise TemplateRenderError(str(exc)) from exc
        except ExecutorQueryTimeoutError as exc:
            raise QueryTimeoutError(f"Query timed out after {timeout_s} seconds") from exc
        except ExecutorQueryExecutionError as exc:
            if get_query(template) is None:
                raise TemplateNotFoundError(f"Template '{template}' not found") from exc
            raise QueryExecutionError(str(exc)) from exc

        if sources is not None and scope is not None:
            event_sources = sources.events(row["id"] for row in rows)
            # Preserve the original default nine-column event payload. Explicit
            # stack summaries or a recognized frame reader add source details.
            event_template = get_query(template)
            detail_budget = (
                event_template.validate_params(query_params).get("stack_bytes", -1)
                if event_template
                else -1
            )
            detailed_rows = (
                rows if sources.dataset.ordered_frames_version == 1 or detail_budget >= 0 else []
            )
            for row in detailed_rows:
                source = event_sources[row["id"]]
                row.update(
                    {
                        "source_stack_id": source.stack_id,
                        "stack_id": source.stack_id,
                        "stack_kind": source.stack_kind,
                        "text_kind": source.text_kind,
                        "stack_event_id": row["id"] if source.stack_kind == "captured" else None,
                        "frames": source.frames,
                        "frames_status": source.frames_status,
                    }
                )
            scope["source_coverage"] = {
                "range_complete": True,
                "event_position": "after",
                "coverage_scope": "returned_events",
                "events_resolved": len(event_sources),
                "ordered_frame_events": sum(s.frames is not None for s in event_sources.values()),
                "source_queries": sources.query_count,
            }
        template_obj = get_query(template)
        if template_obj is not None and "stack_bytes" in template_obj.parameters:
            stack_bytes = template_obj.validate_params(query_params)["stack_bytes"]
            if isinstance(stack_bytes, int) and stack_bytes >= 0:
                if sources is not None:
                    summarize_dataset_stacks(rows, stack_bytes)
                else:
                    summarize_stacks(rows, stack_bytes, ctx.callstack_layout)
        budget.remaining()
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
            scope=scope,
        )

    def _dataset_query(
        self,
        dataset: ResolvedDataset,
        device_id: int,
        template: str,
        params: dict[str, Any],
        slice_index: int | None,
    ) -> tuple[Path, dict[str, Any], dict[str, object]]:
        template_obj = get_query(template)
        if template_obj is None:
            raise TemplateNotFoundError(f"Template '{template}' not found")
        if template != "event":
            raise QueryExecutionError(
                "Dataset queries support event addressing and point-event active attribution; "
                "dataset-global cross-slice aggregation/list/peak/leak queries are not supported."
            )
        try:
            validated = template_obj.validate_params(params)
        except (TypeError, ValueError) as exc:
            raise TemplateRenderError(str(exc)) from exc
        device = dataset.device(device_id)
        if slice_index is not None:
            paths = dataset.paths(QueryScope("slice", device_id, slice_index))
            item = device.slices[slice_index]
            low, high = item.start_event_id, item.end_event_id
        else:
            low, high = device.slices[0].start_event_id, device.slices[-1].end_event_id
        event_id = validated.get("id")
        start = validated.get("min_id")
        end = validated.get("max_id")
        if event_id is not None:
            if (
                not isinstance(event_id, int)
                or isinstance(event_id, bool)
                or not low <= event_id <= high
            ):
                raise InvalidParameterError("Event ID must be a real ID within the selected scope.")
            low = high = event_id
        else:
            for value in (start, end):
                if value is not None and (
                    not isinstance(value, int)
                    or isinstance(value, bool)
                    or not low <= value <= high
                ):
                    raise InvalidParameterError(
                        "Event range must lie within the selected real scope."
                    )
            low = start if isinstance(start, int) else low
            high = end if isinstance(end, int) else high
        paths = dataset.paths(
            QueryScope("event_range", device_id, start_event_id=low, end_event_id=high)
        )
        if len(paths) != 1:
            raise QueryExecutionError(
                "Event range spans slices; cross-slice execution is not supported. "
                "Select a real id, a single-slice range, or --slice."
            )
        item = next(item for item in device.slices if dataset.root / item.file == paths[0])
        return (
            paths[0],
            {
                **params,
                "min_id": max(low, start) if isinstance(start, int) else low,
                "max_id": min(high, end) if isinstance(end, int) else high,
            },
            {
                "kind": "event_range",
                "device_id": device_id,
                "slice_index": item.index,
                "first_event_id": low,
                "last_event_id": high,
                "db_path": str(paths[0]),
                "dataset_path": str(dataset.root),
                "fingerprint": dataset.fingerprint,
                "boundary_events_included": False,
            },
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

    def _validated_context(
        self, db_path: Path, *, generation: str | None = None, immutable: bool = False
    ) -> Context:
        try:
            if generation is not None:
                return self._context_cache.get(db_path, generation=generation, immutable=immutable)
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


def _finite_top_n(template: str, params: dict[str, Any]) -> int | None:
    """Return a declared non-negative ``top_n``, or ``None`` when unbounded."""
    template_obj = get_query(template)
    if template_obj is None or "top_n" not in template_obj.parameters:
        return None
    try:
        validated = template_obj.validate_params(params)
    except (TypeError, ValueError):
        return None
    raw = validated.get("top_n")
    return raw if isinstance(raw, int) and raw >= 0 else None


def _inner_rank_window_full(rows: list[dict[str, Any]], rank_cap: int) -> bool:
    """True when a finite ``top_n`` window is full and may have dropped rows.

    ``active_memory_callstack_at_event`` applies ``top_n`` only to dynamic
    groups. Other ``top_n`` templates treat every returned row as ranked.
    This is a cap-hit check, not an extra-row probe: an exact match of
    ``rank_cap`` is treated as possibly incomplete unless ``exact_total``
    later proves ``total == returned``.
    """
    if not rows:
        return False
    if any("category" in row for row in rows):
        ranked = sum(1 for row in rows if row.get("category") == "dynamic_live_at_event")
    else:
        ranked = len(rows)
    return ranked >= rank_cap


def _remaining_timeout(timeout_s: float | None, started: float) -> float | None:
    """Return leftover seconds from a single QueryService call budget."""
    if timeout_s is None:
        return None
    left = timeout_s - (time.monotonic() - started)
    if left <= 0:
        raise QueryTimeoutError(f"Query timed out after {timeout_s} seconds")
    return left
