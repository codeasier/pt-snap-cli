"""Query completeness, pagination, and timeout tests for issue #140."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from pt_snap_cli.cli import app
from pt_snap_cli.config import Config
from pt_snap_cli.context import Context
from pt_snap_cli.core.errors import InvalidParameterError, QueryTimeoutError
from pt_snap_cli.core.query_service import QUERY_TIMEOUT_ENV, QueryService, resolve_query_timeout
from pt_snap_cli.query.config import QueryParameter, QueryTemplate
from pt_snap_cli.query.executor import (
    QueryExecutor,
    bump_trailing_limit,
    trailing_sql_limit,
)
from pt_snap_cli.query.executor import (
    QueryTimeoutError as ExecutorQueryTimeoutError,
)
from pt_snap_cli.query.registry import QueryRegistry, _load_all_templates, register_query

runner = CliRunner()


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PT_SNAP_DB_PATH", raising=False)
    monkeypatch.delenv(QUERY_TIMEOUT_ENV, raising=False)
    QueryRegistry.reset()
    _load_all_templates()
    yield
    QueryRegistry.reset()


def _trace_db(tmp_path: Path, rows: list[tuple[int, int, int]]) -> Path:
    db_path = tmp_path / "page.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE dictionary (`table` TEXT, `column` TEXT, `key` TEXT, `value` TEXT)")
    conn.execute("""
        CREATE TABLE trace_entry_0 (
            id INTEGER PRIMARY KEY,
            action INTEGER,
            address INTEGER,
            size INTEGER,
            stream INTEGER,
            allocated INTEGER,
            active INTEGER,
            reserved INTEGER,
            callstack TEXT
        )
        """)
    conn.execute("""
        CREATE TABLE block_0 (
            id INTEGER PRIMARY KEY,
            address INTEGER,
            size INTEGER,
            requestedSize INTEGER,
            state INTEGER,
            allocEventId INTEGER,
            freeEventId INTEGER
        )
        """)
    conn.executemany(
        """
        INSERT INTO trace_entry_0
          (id, action, address, size, stream, allocated, active, reserved, callstack)
        VALUES (?, 4, ?, ?, 0, 0, 0, 0, 'frame')
        """,
        rows,
    )
    conn.executemany(
        """
        INSERT INTO block_0
          (id, address, size, requestedSize, state, allocEventId, freeEventId)
        VALUES (?, ?, ?, ?, 1, ?, -1)
        """,
        [(event_id, address, size, size, event_id) for event_id, address, size in rows],
    )
    conn.commit()
    conn.close()
    return db_path


def _ranked_callstack_db(tmp_path: Path, dynamic_count: int = 4) -> Path:
    """v1 SnapshotDB with ``dynamic_count`` live callstack groups plus specials."""
    db_path = tmp_path / "ranked.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE dictionary (`table` TEXT, `column` TEXT, `key` TEXT, `value` TEXT)")
    conn.execute("""
        CREATE TABLE trace_entry_0 (
            id INTEGER PRIMARY KEY,
            action INTEGER,
            address INTEGER,
            size INTEGER,
            stream INTEGER,
            allocated INTEGER,
            active INTEGER,
            reserved INTEGER,
            callstack TEXT
        )
        """)
    conn.execute("""
        CREATE TABLE block_0 (
            id INTEGER PRIMARY KEY,
            address INTEGER,
            size INTEGER,
            requestedSize INTEGER,
            state INTEGER,
            allocEventId INTEGER,
            freeEventId INTEGER
        )
        """)
    traces = [
        (event_id, 2, 0x1000 * event_id, 1000 * event_id, 0, 0, 0, 0, f"stack_{event_id}.py:1")
        for event_id in range(1, dynamic_count + 1)
    ]
    conn.executemany(
        """
        INSERT INTO trace_entry_0
          (id, action, address, size, stream, allocated, active, reserved, callstack)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        traces,
    )
    blocks = [(-10, 0xA000, 50, 50, 1, -1, -1)]
    blocks.append((-11, 0xB000, 40, 40, 1, -1, 100))
    blocks.extend(
        (event_id, 0x1000 * event_id, 1000 * event_id, 1000 * event_id, 1, event_id, -1)
        for event_id in range(1, dynamic_count + 1)
    )
    conn.executemany(
        """
        INSERT INTO block_0
          (id, address, size, requestedSize, state, allocEventId, freeEventId)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        blocks,
    )
    conn.commit()
    conn.close()
    return db_path


def test_trailing_limit_helpers_probe_finite_limits_only() -> None:
    sql = "SELECT id FROM t ORDER BY id LIMIT 5 OFFSET 2"
    assert trailing_sql_limit(sql) == 5
    assert bump_trailing_limit(sql) == "SELECT id FROM t ORDER BY id LIMIT 6 OFFSET 2"
    assert bump_trailing_limit("SELECT id FROM t LIMIT -1") == "SELECT id FROM t LIMIT -1"
    assert bump_trailing_limit("SELECT id FROM t") == "SELECT id FROM t"


def test_default_total_is_returned_count_and_extra_row_sets_has_more(tmp_path: Path) -> None:
    db_path = _trace_db(tmp_path, [(1, 0x1000, 100), (2, 0x2000, 100), (3, 0x3000, 50)])
    Config().write_project_focus(db_path, device_id=0)

    limited = QueryService().execute_query(
        "event", params={"order_by": "id", "order_dir": "ASC"}, max_rows=2
    )
    assert [row["id"] for row in limited.rows] == [1, 2]
    assert limited.returned == 2
    assert limited.total == 2
    assert limited.has_more is True
    assert limited.truncated is True
    assert limited.total_is_exact is False

    complete = QueryService().execute_query(
        "event", params={"order_by": "id", "order_dir": "ASC"}, max_rows=3
    )
    assert complete.returned == 3
    assert complete.total == 3
    assert complete.has_more is False
    assert complete.truncated is False
    assert complete.total_is_exact is True


def test_exact_total_is_opt_in_count(tmp_path: Path) -> None:
    db_path = _trace_db(tmp_path, [(1, 0x1000, 100), (2, 0x2000, 100), (3, 0x3000, 50)])
    Config().write_project_focus(db_path, device_id=0)

    result = QueryService().execute_query(
        "event",
        params={"order_by": "size", "order_dir": "DESC", "limit": 1, "offset": 1},
        exact_total=True,
    )
    assert result.returned == 1
    assert result.total == 3
    assert result.total_is_exact is True
    assert result.has_more is True
    assert result.truncated is True


def test_event_and_block_stable_sort_pagination(tmp_path: Path) -> None:
    db_path = _trace_db(
        tmp_path,
        [
            (1, 0x1000, 100),
            (2, 0x2000, 100),
            (3, 0x3000, 100),
            (4, 0x4000, 50),
        ],
    )
    Config().write_project_focus(db_path, device_id=0)
    params = {"order_by": "size", "order_dir": "DESC", "limit": 2}

    first = QueryService().execute_query("event", params={**params, "offset": 0})
    second = QueryService().execute_query("event", params={**params, "offset": 2})
    first_ids = [row["id"] for row in first.rows]
    second_ids = [row["id"] for row in second.rows]
    assert first.has_more is True
    assert second.has_more is False
    assert first_ids == [3, 2]
    assert second_ids == [1, 4]
    assert set(first_ids).isdisjoint(second_ids)

    block_first = QueryService().execute_query("block", params={**params, "offset": 0})
    block_second = QueryService().execute_query("block", params={**params, "offset": 2})
    assert [row["id"] for row in block_first.rows] == [3, 2]
    assert [row["id"] for row in block_second.rows] == [1, 4]
    assert block_first.has_more is True
    assert block_second.truncated is True


def test_query_timeout_is_independent_of_row_limit(tmp_path: Path) -> None:
    db_path = tmp_path / "slow.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE dictionary (`table` TEXT, `column` TEXT, `key` TEXT, `value` TEXT)")
    conn.execute("CREATE TABLE trace_entry_0 (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()
    Config().write_project_focus(db_path, device_id=0)
    register_query(
        QueryTemplate(
            name="slow_count",
            query=(
                "WITH RECURSIVE t(x) AS ("
                "SELECT 1 UNION ALL SELECT x+1 FROM t WHERE x < 20000000"
                ") SELECT COUNT(*) AS n FROM t"
            ),
        )
    )

    with pytest.raises(QueryTimeoutError, match="timed out after 0.05"):
        QueryService().execute_query("slow_count", max_rows=1, timeout_s=0.05)


def test_executor_timeout_uses_progress_handler(tmp_path: Path) -> None:
    db_path = tmp_path / "exec.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE dictionary (`table` TEXT, `column` TEXT, `key` TEXT, `value` TEXT)")
    conn.commit()
    conn.close()
    executor = QueryExecutor(Context(db_path))
    sql = (
        "WITH RECURSIVE t(x) AS ("
        "SELECT 1 UNION ALL SELECT x+1 FROM t WHERE x < 20000000"
        ") SELECT COUNT(*) AS n FROM t"
    )
    with pytest.raises(ExecutorQueryTimeoutError, match="timed out"):
        executor.execute(sql, timeout_s=0.05)


def test_resolve_query_timeout_prefers_explicit_then_env(monkeypatch: pytest.MonkeyPatch) -> None:
    assert resolve_query_timeout(None) is None
    assert resolve_query_timeout(0) is None
    assert resolve_query_timeout(2.5) == 2.5
    monkeypatch.setenv(QUERY_TIMEOUT_ENV, "1.5")
    assert resolve_query_timeout(None) == 1.5
    assert resolve_query_timeout(0) is None
    monkeypatch.setenv(QUERY_TIMEOUT_ENV, "abc")
    with pytest.raises(InvalidParameterError, match=QUERY_TIMEOUT_ENV):
        resolve_query_timeout(None)


def test_cli_json_has_more_and_exact_total(tmp_path: Path) -> None:
    db_path = _trace_db(tmp_path, [(1, 0x1000, 10), (2, 0x2000, 20), (3, 0x3000, 30)])
    limited = runner.invoke(
        app,
        [
            "query",
            str(db_path),
            "--template-use",
            "event",
            "--params",
            '{"order_by":"id","order_dir":"ASC"}',
            "-n",
            "1",
            "--json",
        ],
    )
    assert limited.exit_code == 0, limited.stdout
    payload = json.loads(limited.stdout)
    assert payload["ok"] is True
    assert payload["returned"] == 1
    assert payload["total"] == 1
    assert payload["has_more"] is True
    assert payload["truncated"] is True
    assert payload["total_is_exact"] is False

    exact = runner.invoke(
        app,
        [
            "query",
            str(db_path),
            "--template-use",
            "event",
            "--params",
            '{"order_by":"id","order_dir":"ASC"}',
            "-n",
            "1",
            "--exact-total",
            "--json",
        ],
    )
    assert exact.exit_code == 0, exact.stdout
    exact_payload = json.loads(exact.stdout)
    assert exact_payload["total"] == 3
    assert exact_payload["returned"] == 1
    assert exact_payload["has_more"] is True
    assert exact_payload["total_is_exact"] is True


def test_cli_json_timeout_error(tmp_path: Path) -> None:
    db_path = tmp_path / "timeout.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE dictionary (`table` TEXT, `column` TEXT, `key` TEXT, `value` TEXT)")
    conn.execute("CREATE TABLE trace_entry_0 (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()
    register_query(
        QueryTemplate(
            name="slow_count",
            query=(
                "WITH RECURSIVE t(x) AS ("
                "SELECT 1 UNION ALL SELECT x+1 FROM t WHERE x < 20000000"
                ") SELECT x FROM t"
            ),
        )
    )
    result = runner.invoke(
        app,
        [
            "query",
            str(db_path),
            "--template-use",
            "slow_count",
            "--timeout",
            "0.05",
            "--json",
        ],
    )
    assert result.exit_code == 1
    assert result.stdout == ""
    payload = json.loads(result.stderr)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "QUERY_TIMEOUT"


def test_top_n_window_is_not_reported_complete_by_default(tmp_path: Path) -> None:
    db_path = _ranked_callstack_db(tmp_path, dynamic_count=4)
    Config().write_project_focus(db_path, device_id=0)
    params = {"event_id": 10, "include_static": True, "top_n": 2}

    limited = QueryService().execute_query("active_memory_callstack_at_event", params=params)
    dynamic = [row for row in limited.rows if row["category"] == "dynamic_live_at_event"]
    specials = [row for row in limited.rows if row["category"] != "dynamic_live_at_event"]
    assert len(dynamic) == 2
    assert len(specials) == 2
    assert limited.returned == 4
    assert limited.total == 4
    assert limited.has_more is True
    assert limited.truncated is True
    assert limited.total_is_exact is False

    exact = QueryService().execute_query(
        "active_memory_callstack_at_event", params=params, exact_total=True
    )
    assert exact.returned == 4
    assert exact.total == 6
    assert exact.has_more is True
    assert exact.truncated is True
    assert exact.total_is_exact is True

    complete = QueryService().execute_query(
        "active_memory_callstack_at_event",
        params={**params, "top_n": 10},
    )
    assert complete.returned == 6
    assert complete.has_more is False
    assert complete.truncated is False
    assert complete.total_is_exact is True

    exact_full_window = QueryService().execute_query(
        "active_memory_callstack_at_event",
        params={**params, "top_n": 4},
        exact_total=True,
    )
    assert exact_full_window.returned == 6
    assert exact_full_window.total == 6
    assert exact_full_window.has_more is False
    assert exact_full_window.truncated is False
    assert exact_full_window.total_is_exact is True


def test_inner_top_n_without_category_uses_row_count(tmp_path: Path) -> None:
    db_path = _trace_db(tmp_path, [(1, 0x1000, 100), (2, 0x2000, 100), (3, 0x3000, 50)])
    Config().write_project_focus(db_path, device_id=0)
    register_query(
        QueryTemplate(
            name="inner_top_n",
            query=(
                "WITH x AS (SELECT id FROM trace_entry_0 ORDER BY id "
                "LIMIT {{ top_n|int }}) SELECT * FROM x"
            ),
            parameters={"top_n": QueryParameter(name="top_n", type="int", default=20)},
        )
    )

    capped = QueryService().execute_query("inner_top_n", params={"top_n": 2})
    assert [row["id"] for row in capped.rows] == [1, 2]
    assert capped.has_more is True
    assert capped.truncated is True
    assert capped.total_is_exact is False

    short = QueryService().execute_query("inner_top_n", params={"top_n": 5})
    assert short.returned == 3
    assert short.has_more is False
    assert short.truncated is False
    assert short.total_is_exact is True


def test_allocation_and_leak_detection_stable_id_tie_break(tmp_path: Path) -> None:
    db_path = _trace_db(
        tmp_path,
        [
            (1, 0x1000, 100),
            (2, 0x2000, 100),
            (3, 0x3000, 100),
            (4, 0x4000, 50),
        ],
    )
    Config().write_project_focus(db_path, device_id=0)
    params = {"order_by": "allocated", "order_dir": "DESC", "limit": 2}

    first = QueryService().execute_query("allocation", params={**params, "offset": 0})
    second = QueryService().execute_query("allocation", params={**params, "offset": 2})
    assert [row["id"] for row in first.rows] == [4, 3]
    assert [row["id"] for row in second.rows] == [2, 1]
    assert first.has_more is True
    assert {row["id"] for row in first.rows}.isdisjoint({row["id"] for row in second.rows})

    leak_db = tmp_path / "leak_ties.db"
    conn = sqlite3.connect(str(leak_db))
    conn.execute("CREATE TABLE dictionary (`table` TEXT, `column` TEXT, `key` TEXT, `value` TEXT)")
    conn.execute("CREATE TABLE trace_entry_0 (id INTEGER PRIMARY KEY)")
    conn.execute("""
        CREATE TABLE block_0 (
            id INTEGER PRIMARY KEY,
            address INTEGER,
            size INTEGER,
            requestedSize INTEGER,
            state INTEGER,
            allocEventId INTEGER,
            freeEventId INTEGER
        )
        """)
    conn.executemany(
        """
        INSERT INTO block_0
          (id, address, size, requestedSize, state, allocEventId, freeEventId)
        VALUES (?, ?, ?, ?, 1, ?, -1)
        """,
        [(1, 0x1000, 100, 100, 1), (2, 0x2000, 100, 100, 2), (3, 0x3000, 50, 50, 3)],
    )
    conn.commit()
    conn.close()
    Config().write_project_focus(leak_db, device_id=0)

    leak_first = QueryService().execute_query("leak_detection", max_rows=1)
    leak_rest = QueryService().execute_query("leak_detection", max_rows=2)
    assert [row["id"] for row in leak_first.rows] == [2]
    assert leak_first.has_more is True
    assert [row["id"] for row in leak_rest.rows] == [2, 1]


def test_exact_total_count_is_subject_to_timeout(tmp_path: Path) -> None:
    db_path = _trace_db(tmp_path, [(1, 0x1000, 100)])
    Config().write_project_focus(db_path, device_id=0)
    register_query(
        QueryTemplate(
            name="slow_when_unlimited",
            query=(
                "WITH RECURSIVE t(x) AS ("
                "SELECT 1 UNION ALL SELECT x+1 FROM t WHERE x < "
                "CASE WHEN {{ limit|int }} < 0 THEN 20000000 ELSE 10 END"
                ") SELECT x FROM t LIMIT {{ limit|int }}"
            ),
            parameters={"limit": QueryParameter(name="limit", type="int", default=-1)},
        )
    )

    with pytest.raises(QueryTimeoutError, match="timed out after"):
        QueryService().execute_query(
            "slow_when_unlimited",
            max_rows=1,
            exact_total=True,
            timeout_s=0.05,
        )


def test_exact_total_count_shares_query_timeout(tmp_path: Path) -> None:
    db_path = _trace_db(tmp_path, [(1, 0x1000, 100)])
    Config().write_project_focus(db_path, device_id=0)
    counted = {"called": False}

    def _slow_page(*_args: object, **_kwargs: object) -> tuple[list[dict[str, int]], bool, None]:
        time.sleep(0.08)
        return ([{"id": 1}], False, None)

    def _count(*_args: object, **_kwargs: object) -> int:
        counted["called"] = True
        return 1

    with (
        patch.object(QueryExecutor, "execute_template_page", _slow_page),
        patch.object(QueryExecutor, "count_template", _count),
    ):
        with pytest.raises(QueryTimeoutError, match="timed out after 0.05"):
            QueryService().execute_query("event", exact_total=True, timeout_s=0.05)
    assert counted["called"] is False


def test_cli_json_timeout_env_and_invalid_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "timeout.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE dictionary (`table` TEXT, `column` TEXT, `key` TEXT, `value` TEXT)")
    conn.execute("CREATE TABLE trace_entry_0 (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()
    register_query(
        QueryTemplate(
            name="slow_count",
            query=(
                "WITH RECURSIVE t(x) AS ("
                "SELECT 1 UNION ALL SELECT x+1 FROM t WHERE x < 20000000"
                ") SELECT x FROM t"
            ),
        )
    )
    monkeypatch.setenv(QUERY_TIMEOUT_ENV, "0.05")
    timed_out = runner.invoke(
        app,
        ["query", str(db_path), "--template-use", "slow_count", "--json"],
    )
    assert timed_out.exit_code == 1
    assert timed_out.stdout == ""
    timeout_payload = json.loads(timed_out.stderr)
    assert timeout_payload["error"]["code"] == "QUERY_TIMEOUT"

    monkeypatch.setenv(QUERY_TIMEOUT_ENV, "abc")
    invalid = runner.invoke(
        app,
        ["query", str(db_path), "--template-use", "event", "--json"],
    )
    assert invalid.exit_code == 1
    assert invalid.stdout == ""
    invalid_payload = json.loads(invalid.stderr)
    assert invalid_payload["error"]["code"] == "INVALID_PARAMETER"
