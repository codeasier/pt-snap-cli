"""Budget messages retain one domain boundary across dataset execution paths."""

import sqlite3
import time
from contextlib import closing

import pytest

from pt_snap_cli.core.context_cache import ContextCache
from pt_snap_cli.core.dataset_lifecycle_connection import _AttachedSources
from pt_snap_cli.core.dataset_lifecycle_scratch import scratch_lifecycles
from pt_snap_cli.core.dataset_resolver import DatasetResolver
from pt_snap_cli.core.dataset_sources import DatasetSourceResolver, QueryBudget
from pt_snap_cli.core.errors import QueryExecutionError
from pt_snap_cli.core.query_service import QueryService
from tests.test_dataset_focus import make_dataset


def _budget(limit):
    limits = {"max_work_rows": 1} if limit == "rows" else {"max_work_bytes": 1}
    return QueryBudget(None, time.monotonic(), **limits)


@pytest.mark.parametrize("route", ["source", "attached", "scratch", "output"])
@pytest.mark.parametrize("limit", ["rows", "bytes"])
def test_same_budget_error_message_across_dataset_read_paths(tmp_path, route, limit):
    root = make_dataset(tmp_path / "dataset", devices=(0,), slices=1)
    path = root / "device_0/slice_00000.db"
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.executemany(
            "INSERT INTO block_0 VALUES (?,?,8,8,1,?,-1)", [(0, 100, 0), (1, 108, 1)]
        )
    dataset = DatasetResolver().inspect(root)
    with pytest.raises(QueryExecutionError) as expected:
        _budget(limit).consume([{"id": 0}, {"id": 1}])

    with closing(ContextCache()) as cache:
        sources = DatasetSourceResolver(dataset, 0, cache, _budget(limit))
        if route == "source":
            with pytest.raises(QueryExecutionError) as caught:
                sources.read(path, "SELECT id FROM trace_entry_0 WHERE id>=0 ORDER BY id")
        elif route == "attached":
            with _AttachedSources(sources) as database:
                with pytest.raises(QueryExecutionError) as caught:
                    database.read("SELECT id FROM s0.trace_entry_0 WHERE id>=0 ORDER BY id")
        elif route == "scratch":
            # Build the real private reducer first, then exhaust its read budget.
            sources.budget = QueryBudget(None, time.monotonic())
            with scratch_lifecycles(sources, sources.device.slices) as (database, _):
                sources.budget = _budget(limit)
                with pytest.raises(QueryExecutionError) as caught:
                    database.read("SELECT id FROM lifecycle_state ORDER BY id")
        else:
            with pytest.raises(QueryExecutionError) as caught:
                sources.budget.consume([{"id": 0}, {"id": 1}])

    assert type(caught.value) is QueryExecutionError
    assert str(caught.value) == str(expected.value)
    assert "no partial global result" in str(caught.value)
    if route in {"attached", "scratch"}:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            database.connection.execute("SELECT 1")


def test_final_output_budget_failure_is_preserved_before_dataset_early_return(
    tmp_path, monkeypatch
):
    root = make_dataset(tmp_path / "dataset", devices=(0,), slices=1)
    consume_source = DatasetSourceResolver._consume
    consume_budget = QueryBudget.consume
    reading_source = False
    failures = []

    def source_consume(sources, rows):
        nonlocal reading_source
        reading_source = True
        try:
            consume_source(sources, rows)
        finally:
            reading_source = False

    def budget_consume(budget, rows):
        # Let the real source reads finish, then fail final result accounting.
        if not reading_source and rows:
            budget.max_work_rows = budget.work_rows
        try:
            consume_budget(budget, rows)
        except QueryExecutionError as exc:
            failures.append(exc)
            raise

    monkeypatch.setattr(DatasetSourceResolver, "_consume", source_consume)
    monkeypatch.setattr(QueryBudget, "consume", budget_consume)
    with closing(QueryService()) as service:
        with pytest.raises(QueryExecutionError) as caught:
            service.execute_query("allocation", db_path=root)
    assert len(failures) == 1
    assert caught.value is failures[0]
    assert "no partial global result" in str(caught.value)
