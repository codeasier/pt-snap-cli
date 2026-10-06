from __future__ import annotations

import time
from pathlib import Path
from typing import Literal, cast

from pt_snap_cli.core.dataset_sources import QueryBudget
from pt_snap_cli.core.focus_service import FocusService
from pt_snap_cli.core.models import PeakMemoryReport, QueryResult
from pt_snap_cli.core.query_service import QueryService, resolve_query_timeout

PeakMetric = Literal["active", "allocated", "reserved"]

_EVENT_ID_BY_METRIC = {
    "active": "peak_active_event_id",
    "allocated": "peak_allocated_event_id",
    "reserved": "peak_reserved_event_id",
}

_ACTIVE_COUNTER_BY_METRIC = {
    "active": "peak_active",
    "allocated": "active_at_allocated_peak",
    "reserved": "active_at_reserved_peak",
}


class ReportService:
    def __init__(self, focus_service: FocusService | None = None) -> None:
        self._focus_service = focus_service or FocusService()
        self._query_service = QueryService(self._focus_service)

    def close(self) -> None:
        """Release connections owned by this report service; allow later reuse."""
        self._query_service.close()

    def event_attribution(
        self,
        event_id: int,
        db_path: Path | str | None = None,
        device_id: int | None = None,
        *,
        include_static: bool = True,
        limit: int = 20,
        stack_bytes: int = -1,
        start_dir: Path | None = None,
        timeout_s: float | None = None,
        _budget: QueryBudget | None = None,
    ) -> QueryResult:
        """Reuse core point-event attribution, also for externally selected peaks.

        Dataset-global peak selection is a separate contract; this method does
        not silently choose a local shard peak or invent an event for empty data.
        """
        return self._query_service.execute_query(
            "active_memory_callstack_at_event",
            params={
                "event_id": event_id,
                "include_static": include_static,
                "min_size": 0,
                "top_n": limit,
                "stack_bytes": stack_bytes,
            },
            db_path=db_path,
            device_id=device_id,
            start_dir=start_dir,
            timeout_s=timeout_s,
            _budget=_budget,
        )

    def peak_memory_report(
        self,
        db_path: Path | str | None = None,
        device_id: int | None = None,
        metric: PeakMetric = "active",
        include_static: bool = True,
        limit: int = 20,
        start_dir: Path | None = None,
        stack_bytes: int = -1,
        *,
        start_id: int | None = None,
        end_id: int | None = None,
        timeout_s: float | None = None,
    ) -> PeakMemoryReport:
        if metric not in _EVENT_ID_BY_METRIC:
            raise ValueError(
                f"Invalid metric '{metric}'. Must be one of: active, allocated, reserved"
            )

        budget = QueryBudget(resolve_query_timeout(timeout_s), time.monotonic())
        range_params = {"start_id": start_id, "end_id": end_id}
        peak_result = self._query_service.execute_query(
            "memory_peak",
            params=range_params,
            _budget=budget,
            db_path=db_path,
            device_id=device_id,
            start_dir=start_dir,
        )
        peak = peak_result.rows[0] if peak_result.rows else {}
        # memory_peak selects an INTEGER event ID (or NULL for an empty trace).
        event_id = cast(int | None, peak.get(_EVENT_ID_BY_METRIC[metric]))
        attribution_params: dict[str, object] = {
            "event_id": event_id,
            "include_static": include_static,
            "min_size": 0,
            "top_n": limit,
            **({"stack_bytes": stack_bytes} if stack_bytes >= 0 else {}),
        }

        if event_id is None:
            return PeakMemoryReport(
                device_id=peak_result.device_id,
                metric=metric,
                event_id=None,
                peak=peak,
                allocator_gap=None,
                callstack_groups=[],
                total_is_exact=True,
                effective_params=attribution_params,
                scope=peak_result.scope,
                timeout_s=budget.timeout_s,
            )

        gap_result = self._query_service.execute_query(
            "allocator_gap",
            params=range_params,
            _budget=budget,
            db_path=db_path,
            device_id=device_id,
            start_dir=start_dir,
        )
        callstack_result = self.event_attribution(
            event_id,
            db_path,
            device_id,
            include_static=include_static,
            limit=limit,
            stack_bytes=stack_bytes,
            start_dir=start_dir,
            _budget=budget,
        )

        gap = gap_result.rows[0] if gap_result.rows else None
        # allocator_gap supplies the active counter at this metric's event,
        # not the independently occurring active high-water value.
        active_bytes = cast(int | None, (gap or {}).get(_ACTIVE_COUNTER_BY_METRIC[metric]))
        # No caller-side max_rows cap: these are all rows in the SQL percentage
        # denominator, including static/preexisting groups outside top_n.
        included_bytes = sum(cast(int, row["size_bytes"]) for row in callstack_result.rows)
        coverage = (
            included_bytes * 100.0 / active_bytes
            if active_bytes is not None and active_bytes > 0
            else None
        )

        return PeakMemoryReport(
            device_id=peak_result.device_id,
            metric=metric,
            event_id=event_id,
            peak=peak,
            allocator_gap=gap,
            callstack_groups=callstack_result.rows,
            has_more=callstack_result.has_more,
            truncated=callstack_result.truncated,
            total_is_exact=callstack_result.total_is_exact,
            effective_params=attribution_params,
            included_bytes=included_bytes,
            active_bytes_at_event=active_bytes,
            coverage_percent=coverage,
            scope=peak_result.scope,
            timeout_s=budget.timeout_s,
            source_coverage=cast(
                dict[str, object] | None, (callstack_result.scope or {}).get("source_coverage")
            ),
        )
