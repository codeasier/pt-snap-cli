"""Operation-local reuse preserves real read accounting and source identity."""

import json
import sqlite3
import time
from contextlib import closing

import pytest

from pt_snap_cli.core.context_cache import ContextCache
from pt_snap_cli.core.dataset_resolver import DatasetResolver
from pt_snap_cli.core.dataset_sources import DatasetSourceResolver, QueryBudget
from pt_snap_cli.core.errors import QueryExecutionError
from pt_snap_cli.core.query_service import QueryService
from tests.test_dataset_focus import make_dataset


def dataset(tmp_path, count, stack="shared", blocks=False):
    root = make_dataset(tmp_path / "dataset", devices=(0,), slices=1)
    manifest = json.loads((root / "manifest.json").read_text())
    manifest["eventsPerSlice"] = count
    manifest["devices"]["0"]["eventCount"] = count
    manifest["devices"]["0"]["slices"][0]["endEventId"] = count - 1
    (root / "manifest.json").write_text(json.dumps(manifest))
    with closing(sqlite3.connect(root / "device_0/slice_00000.db")) as conn, conn:
        conn.execute("DELETE FROM trace_entry_0")
        conn.executemany(
            "INSERT INTO trace_entry_0 VALUES (?,4,?,8,0,8,8,16,?)",
            ((i, i * 8, stack) for i in range(count)),
        )
        if blocks:
            conn.executemany(
                "INSERT INTO block_0 VALUES (?,?,8,8,1,?,-1)",
                ((i, i * 8, i) for i in range(count)),
            )
    return root


@pytest.mark.parametrize("template", ["callstack_analysis", "event"])
def test_sixty_thousand_events_are_not_read_twice(tmp_path, template):
    root = dataset(tmp_path, 60_000)
    budget = QueryBudget(None, time.monotonic())
    service = QueryService()
    try:
        result = service.execute_query(
            template,
            params=(
                {"min_count": 1}
                if template == "callstack_analysis"
                else {
                    "order_by": "callstack",
                    "limit": 1,
                }
            ),
            db_path=root,
            _budget=budget,
        )
    finally:
        service.close()
    assert result.returned == 1
    assert budget.work_rows == 60_001
    if template == "callstack_analysis":
        assert result.rows[0]["alloc_count"] == 60_000


def test_target_and_distinct_events_reuse_only_identical_sources(tmp_path):
    root = dataset(tmp_path, 4)
    resolved = DatasetResolver().inspect(root)
    budget = QueryBudget(None, time.monotonic())
    with closing(ContextCache()) as cache:
        sources = DatasetSourceResolver(resolved, 0, cache, budget)
        sources.target(3)
        first = sources.events([0, 1, 2, 3])
        reads, work = sources.query_count, budget.work_rows
        repeated = sources.events([3, 2, 1, 0, 3])
        assert sources.query_count == reads
        assert budget.work_rows == work == 4
        assert repeated[3] is first[3]
        assert first[0].event["id"] != first[1].event["id"]
        assert first[0].stack_id == first[1].stack_id


@pytest.mark.parametrize("count, succeeds", [(49_999, True), (50_000, False)])
def test_distinct_block_and_allocation_work_still_counts(tmp_path, count, succeeds):
    root = dataset(tmp_path, count, blocks=True)
    budget = QueryBudget(None, time.monotonic())
    service = QueryService()
    try:
        if succeeds:
            result = service.execute_query(
                "active_memory_callstack_at_event",
                params={"event_id": count - 1},
                db_path=root,
                _budget=budget,
            )
            assert result.returned == 1
            assert budget.work_rows == 2 * count + 1
        else:
            with pytest.raises(QueryExecutionError, match="work budget exceeded"):
                service.execute_query(
                    "active_memory_callstack_at_event",
                    params={"event_id": count - 1},
                    db_path=root,
                    _budget=budget,
                )
            assert budget.work_rows == 100_001
    finally:
        service.close()


@pytest.mark.parametrize("count, succeeds", [(3_000, True), (5_000, False)])
def test_long_distinct_source_payload_remains_budgeted(tmp_path, count, succeeds):
    root = dataset(tmp_path, count, stack="x" * 16_384, blocks=True)
    budget = QueryBudget(None, time.monotonic())
    with closing(QueryService()) as service:
        if succeeds:
            result = service.execute_query(
                "active_memory_callstack_at_event",
                params={"event_id": count - 1},
                db_path=root,
                _budget=budget,
            )
            assert result.returned == 1
            assert budget.work_rows == 2 * count + 1
        else:
            with pytest.raises(QueryExecutionError, match="work budget exceeded"):
                service.execute_query(
                    "active_memory_callstack_at_event",
                    params={"event_id": count - 1},
                    db_path=root,
                    _budget=budget,
                )
            assert budget.work_rows < budget.max_work_rows
            assert budget.work_bytes > budget.max_work_bytes
