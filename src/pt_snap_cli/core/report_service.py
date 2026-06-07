from __future__ import annotations

from pathlib import Path
from typing import Literal

from pt_snap_cli.core.focus_service import FocusService
from pt_snap_cli.core.models import PeakMemoryReport
from pt_snap_cli.core.query_service import QueryService

PeakMetric = Literal["active", "allocated", "reserved"]

_EVENT_ID_BY_METRIC = {
    "active": "peak_active_event_id",
    "allocated": "peak_allocated_event_id",
    "reserved": "peak_reserved_event_id",
}


class ReportService:
    def __init__(self, focus_service: FocusService | None = None) -> None:
        self._focus_service = focus_service or FocusService()
        self._query_service = QueryService(self._focus_service)

    def peak_memory_report(
        self,
        db_path: Path | str | None = None,
        device_id: int | None = None,
        metric: PeakMetric = "active",
        include_static: bool = True,
        limit: int = 20,
        start_dir: Path | None = None,
    ) -> PeakMemoryReport:
        if metric not in _EVENT_ID_BY_METRIC:
            raise ValueError(
                f"Invalid metric '{metric}'. Must be one of: active, allocated, reserved"
            )

        peak_result = self._query_service.execute_query(
            "memory_peak",
            db_path=db_path,
            device_id=device_id,
            start_dir=start_dir,
        )
        peak = peak_result.rows[0] if peak_result.rows else {}
        event_id = peak.get(_EVENT_ID_BY_METRIC[metric])

        if event_id is None:
            return PeakMemoryReport(
                device_id=peak_result.device_id,
                metric=metric,
                event_id=None,
                peak=peak,
                allocator_gap=None,
                callstack_groups=[],
            )

        gap_result = self._query_service.execute_query(
            "allocator_gap",
            db_path=db_path,
            device_id=device_id,
            start_dir=start_dir,
        )
        callstack_result = self._query_service.execute_query(
            "active_memory_callstack_at_event",
            params={
                "event_id": event_id,
                "include_static": include_static,
                "top_n": limit,
            },
            db_path=db_path,
            device_id=device_id,
            start_dir=start_dir,
        )

        return PeakMemoryReport(
            device_id=peak_result.device_id,
            metric=metric,
            event_id=event_id,
            peak=peak,
            allocator_gap=gap_result.rows[0] if gap_result.rows else None,
            callstack_groups=callstack_result.rows,
        )
