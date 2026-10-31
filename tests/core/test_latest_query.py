"""Latest-only coordination does not publish superseded or reset work."""

import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Event

import pytest

from pt_snap_cli.api import SnapshotAnalyzer
from pt_snap_cli.core.errors import QueryCancelledError
from pt_snap_cli.core.latest_query import LatestQuery
from pt_snap_cli.core.validation_budget import validation_progress
from pt_snap_cli.query.config import QueryParameter, QueryTemplate
from pt_snap_cli.query.executor import QueryExecutor


def test_cancel_discards_result_and_next_query_can_run():
    queries = LatestQuery()
    with pytest.raises(QueryCancelledError):
        with queries.run() as cancelled:
            assert not cancelled()
            queries.cancel()
            assert cancelled()
    with queries.run() as cancelled:
        assert not cancelled()


def test_query_failure_does_not_poison_future_queries():
    queries = LatestQuery()
    with pytest.raises(ValueError):
        with queries.run():
            raise ValueError("query failed")
    with queries.run() as cancelled:
        assert not cancelled()


def test_queued_obsolete_request_is_skipped():
    queries = LatestQuery()
    entered = []
    queries._work.acquire()

    def run(number):
        with queries.run():
            entered.append(number)

    def wait_for_token(previous):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            with queries._state:
                token = queries._active
            if token is not None and token is not previous:
                return token
            Event().wait(0.005)
        pytest.fail("The request did not register its cancellation token")

    with ThreadPoolExecutor(max_workers=2) as pool:
        try:
            first = pool.submit(run, 1)
            token = wait_for_token(None)
            second = pool.submit(run, 2)
            wait_for_token(token)
        finally:
            queries._work.release()
        with pytest.raises(QueryCancelledError):
            first.result(timeout=3)
        second.result(timeout=3)
    assert entered == [2]


def test_independent_services_do_not_cancel_each_other():
    first, second = LatestQuery(), LatestQuery()
    with first.run() as cancelled:
        with pytest.raises(QueryCancelledError):
            with second.run():
                second.cancel()
                assert not cancelled()


def test_cancellation_during_dataset_validation_preserves_error_and_cleans_handler():
    class Budget:
        def __init__(self):
            self.checks = 0

        def remaining(self):
            self.checks += 1
            if self.checks >= 3:
                raise QueryCancelledError("cancelled during validation")
            return None

    with closing(sqlite3.connect(":memory:")) as conn:
        with pytest.raises(QueryCancelledError, match="during validation"):
            with validation_progress(conn, Budget()):
                conn.execute(
                    "WITH RECURSIVE n(x) AS (VALUES(0) UNION ALL SELECT x+1 FROM n WHERE x<100000000) "
                    "SELECT SUM(x) FROM n"
                ).fetchall()
        assert conn.execute("SELECT 1").fetchone() == (1,)


@pytest.mark.parametrize("timeout", [0, 30])
def test_standalone_tree_interrupts_sql_and_preserves_runtime_templates(
    tmp_path, monkeypatch, timeout
):
    path = tmp_path / "standalone.db"
    with closing(sqlite3.connect(path)) as conn:
        conn.executescript(
            "CREATE TABLE dictionary (id INTEGER);" "CREATE TABLE trace_entry_0 (id INTEGER);"
        )
    started = Event()
    execute = QueryExecutor.execute

    def observed(self, sql, *args, **kwargs):
        if "WITH RECURSIVE" in sql:
            started.set()
        return execute(self, sql, *args, **kwargs)

    monkeypatch.setattr(QueryExecutor, "execute", observed)
    template = "active_memory_frame_tree_at_event"
    with SnapshotAnalyzer(path) as analyzer, ThreadPoolExecutor(max_workers=2) as pool:
        source = analyzer._query_service._get_executor(analyzer.context_cache.get(path))
        source.register_template(
            QueryTemplate(
                name=template,
                parameters={"event_id": QueryParameter(name="event_id", type="int", required=True)},
                query="{% if event_id == 1 %}"
                "WITH RECURSIVE n(x) AS (VALUES(0) UNION ALL SELECT x+1 FROM n WHERE x<100000000) "
                "SELECT SUM(x) AS value FROM n"
                "{% else %}SELECT 7 AS value{% endif %}",
            )
        )
        old = pool.submit(analyzer.execute_query, template, {"event_id": 1}, timeout_s=timeout)
        assert started.wait(3)
        new = pool.submit(analyzer.execute_query, template, {"event_id": 2})
        with pytest.raises(QueryCancelledError):
            old.result(timeout=5)
        assert new.result(timeout=5)["rows"] == [{"value": 7}]
        assert analyzer.execute_query(template, {"event_id": 2})["rows"] == [{"value": 7}]
