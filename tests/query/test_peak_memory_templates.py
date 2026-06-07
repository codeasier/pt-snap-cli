"""Tests for peak memory attribution query templates."""

import sqlite3
from pathlib import Path

import pytest

from pt_snap_cli.context import Context
from pt_snap_cli.query.executor import QueryExecutor
from pt_snap_cli.query.registry import (
    QueryRegistry,
    _load_all_templates,
    get_query,
    list_by_category,
)


@pytest.fixture(autouse=True)
def _reload_query_templates():
    QueryRegistry.reset()
    _load_all_templates()


@pytest.fixture
def peak_memory_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "peak_memory.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE dictionary (
            `table` TEXT,
            `column` TEXT,
            `key` TEXT,
            `value` TEXT
        )
    """)
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
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (1, 2, 0x1000, 1024, 0, 1024, 1024, 4096, "train.py:10"),
            (2, 2, 0x2000, 2048, 0, 3072, 3072, 4096, "freed.py:20"),
            (3, 3, 0x2000, 2048, 0, 1024, 1024, 8192, "free.py:30"),
            (4, 2, 0x4000, 4096, 0, 5120, 5120, 8192, "after.py:40"),
            (5, 2, 0x5000, 512, 0, 5632, 5632, 8192, None),
        ],
    )
    conn.executemany(
        """
        INSERT INTO block_0
          (id, address, size, requestedSize, state, allocEventId, freeEventId)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (-10, 0xA000, 8192, 8000, 1, -1, -1),
            (1, 0x1000, 1024, 1000, 1, 1, -1),
            (2, 0x2000, 2048, 2000, 0, 2, 3),
            (4, 0x4000, 4096, 4000, 1, 4, -1),
            (5, 0x5000, 512, 500, 1, 5, -1),
        ],
    )
    conn.commit()
    conn.close()
    return db_path


def _execute_template(db_path: Path, name: str, params: dict) -> list[dict]:
    context = Context(db_path)
    executor = QueryExecutor(context)
    return executor.execute_template(name, params=params, device_id=0)


def test_new_templates_are_registered_in_correct_categories() -> None:
    assert "active_blocks_at_event" in list_by_category("statistical")
    assert "allocator_gap" in list_by_category("statistical")
    assert "active_memory_callstack_at_event" in list_by_category("business")

    assert get_query("active_blocks_at_event") is not None
    assert get_query("allocator_gap") is not None
    assert get_query("active_memory_callstack_at_event") is not None


def test_active_blocks_at_event_includes_static_when_enabled(peak_memory_db: Path) -> None:
    rows = _execute_template(
        peak_memory_db,
        "active_blocks_at_event",
        {"event_id": 3, "include_static": True},
    )

    assert [row["id"] for row in rows] == [-10, 1]
    assert rows[0]["category"] == "static"
    assert rows[1]["category"] == "dynamic_live_at_event"


def test_active_blocks_at_event_excludes_static_when_disabled(peak_memory_db: Path) -> None:
    rows = _execute_template(
        peak_memory_db,
        "active_blocks_at_event",
        {"event_id": 3, "include_static": False},
    )

    assert [row["id"] for row in rows] == [1]


def test_active_blocks_at_event_applies_event_boundary_and_size_filter(
    peak_memory_db: Path,
) -> None:
    rows = _execute_template(
        peak_memory_db,
        "active_blocks_at_event",
        {
            "event_id": 5,
            "include_static": False,
            "min_size": 1000,
            "order_by": "id",
            "order_dir": "ASC",
        },
    )

    assert [row["id"] for row in rows] == [1, 4]


def test_active_memory_callstack_at_event_groups_dynamic_static_and_missing_callstacks(
    peak_memory_db: Path,
) -> None:
    rows = _execute_template(
        peak_memory_db,
        "active_memory_callstack_at_event",
        {"event_id": 5, "include_static": True, "top_n": -1},
    )

    by_callstack = {row["callstack"]: row for row in rows}
    assert by_callstack["[static] allocEventId=-1, freeEventId=-1"]["category"] == "static"
    assert by_callstack["[static] allocEventId=-1, freeEventId=-1"]["size_bytes"] == 8192
    assert by_callstack["after.py:40"]["category"] == "dynamic_live_at_event"
    assert by_callstack["after.py:40"]["size_bytes"] == 4096
    assert by_callstack["train.py:10"]["block_count"] == 1
    assert by_callstack["[missing callstack]"]["requested_bytes"] == 500


def test_active_memory_callstack_at_event_can_exclude_static(peak_memory_db: Path) -> None:
    rows = _execute_template(
        peak_memory_db,
        "active_memory_callstack_at_event",
        {"event_id": 5, "include_static": False, "top_n": -1},
    )

    assert "[static] allocEventId=-1, freeEventId=-1" not in {row["callstack"] for row in rows}


def test_allocator_gap_reports_peak_events_and_same_event_gaps(peak_memory_db: Path) -> None:
    rows = _execute_template(peak_memory_db, "allocator_gap", {})

    assert len(rows) == 1
    row = rows[0]
    assert row["peak_allocated_event_id"] == 5
    assert row["peak_active_event_id"] == 5
    assert row["peak_reserved_event_id"] == 3
    assert row["allocated_active_same_event"] == 1
    assert row["active_reserved_same_event"] == 0
    assert row["reserved_active_gap_at_active_peak"] == 2560
    assert row["reserved_active_gap_at_reserved_peak"] == 7168
