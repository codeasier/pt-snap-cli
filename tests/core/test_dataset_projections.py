"""Per-template scan projections must not charge unrelated inline stack text."""

import sqlite3
import time
from contextlib import closing

import pytest

from pt_snap_cli.core.dataset_sources import QueryBudget
from pt_snap_cli.core.query_service import QueryService
from tests.test_dataset_focus import make_dataset


@pytest.mark.parametrize("template", ["memory_peak", "allocator_gap", "allocation"])
def test_counter_query_budget_is_independent_of_inline_stack_length(tmp_path, template):
    root = make_dataset(tmp_path / "dataset", devices=(0,), slices=3)
    observations = []
    for stack in ("x" * 16, "x" * 8192, "x" * 32768, "栈🙂" * 8192):
        for path in root.glob("device_0/*.db"):
            with closing(sqlite3.connect(path)) as conn, conn:
                conn.execute("UPDATE trace_entry_0 SET callstack=?", (stack,))
        service = QueryService()
        try:
            budget = QueryBudget(None, time.monotonic(), max_work_bytes=8192)
            result = service.execute_query(template, db_path=root, _budget=budget)
            observations.append((result.rows, budget.work_rows, budget.work_bytes))
        finally:
            service.close()
    assert all(item == observations[0] for item in observations)


@pytest.mark.parametrize("direction", ["ASC", "DESC"])
def test_event_projection_preserves_callstack_sort_and_paging(tmp_path, direction):
    root = make_dataset(tmp_path / "dataset", devices=(0,), slices=3)
    stacks = ["z" * 8192, None, "栈🙂" * 8192, "a" * 16384, "", "a" * 16384]
    for index, stack in enumerate(stacks):
        path = root / f"device_0/slice_{index // 2:05d}.db"
        with closing(sqlite3.connect(path)) as conn, conn:
            conn.execute("UPDATE trace_entry_0 SET callstack=? WHERE id=?", (stack, index))
    service = QueryService()
    try:
        params = {"order_by": "callstack", "order_dir": direction, "offset": 1, "limit": 3}
        result = service.execute_query("event", params, db_path=root, exact_total=True)
        expected = sorted(
            range(len(stacks)),
            key=lambda event: (stacks[event] is not None, stacks[event], event),
            reverse=direction == "DESC",
        )[1:4]
        assert [row["id"] for row in result.rows] == expected
        assert [row["callstack"] for row in result.rows] == [stacks[event] for event in expected]
        assert result.total == 6 and result.has_more and result.truncated
        assert all(len(row) == 9 for row in result.rows)
    finally:
        service.close()
