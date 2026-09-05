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
            callstackId INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE callstack (
            id INTEGER PRIMARY KEY,
            callstack TEXT
        )
    """)
    conn.executemany(
        "INSERT INTO callstack (id, callstack) VALUES (?, ?)",
        [
            (0, "train.py:10"),
            (1, "freed.py:20"),
            (2, "free.py:30"),
            (3, "after.py:40"),
        ],
    )
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
          (id, action, address, size, stream, allocated, active, reserved, callstackId)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (1, 2, 0x1000, 1024, 0, 1024, 1024, 4096, 0),
            (2, 2, 0x2000, 2048, 0, 3072, 3072, 4096, 1),
            (3, 3, 0x2000, 2048, 0, 1024, 1024, 8192, 2),
            (4, 2, 0x4000, 4096, 0, 5120, 5120, 8192, 3),
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


def test_active_blocks_at_event_treats_null_free_event_as_live(peak_memory_db: Path) -> None:
    conn = sqlite3.connect(str(peak_memory_db))
    conn.execute(
        """
        INSERT INTO block_0
          (id, address, size, requestedSize, state, allocEventId, freeEventId)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (6, 0x6000, 1536, 1500, 1, 2, None),
    )
    conn.commit()
    conn.close()

    rows = _execute_template(
        peak_memory_db,
        "active_blocks_at_event",
        {"event_id": 3, "include_static": False, "order_by": "id", "order_dir": "ASC"},
    )

    assert [row["id"] for row in rows] == [1, 6]


def _insert_preexisting_block(db_path: Path, block_id: int, free_event_id: int | None) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        INSERT INTO block_0
          (id, address, size, requestedSize, state, allocEventId, freeEventId)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (block_id, 0x7000, 2048, 2000, 1, -1, free_event_id),
    )
    conn.commit()
    conn.close()


def test_active_blocks_at_event_includes_preexisting_block_freed_after_event(
    peak_memory_db: Path,
) -> None:
    _insert_preexisting_block(peak_memory_db, -11, 4)

    rows = _execute_template(peak_memory_db, "active_blocks_at_event", {"event_id": 3})

    by_id = {row["id"]: row for row in rows}
    assert set(by_id) == {-10, -11, 1}
    assert by_id[-10]["category"] == "static"
    assert by_id[-11]["category"] == "preexisting_live_at_event"


def test_active_blocks_at_event_excludes_preexisting_block_freed_by_event(
    peak_memory_db: Path,
) -> None:
    _insert_preexisting_block(peak_memory_db, -11, 4)

    rows = _execute_template(peak_memory_db, "active_blocks_at_event", {"event_id": 4})

    assert {row["id"] for row in rows} == {-10, 1, 4}


def test_active_blocks_at_event_treats_preexisting_null_free_event_as_live(
    peak_memory_db: Path,
) -> None:
    _insert_preexisting_block(peak_memory_db, -11, None)

    rows = _execute_template(peak_memory_db, "active_blocks_at_event", {"event_id": 5})

    assert {row["id"] for row in rows} == {-10, -11, 1, 4, 5}


def test_active_blocks_at_event_excludes_preexisting_when_static_disabled(
    peak_memory_db: Path,
) -> None:
    _insert_preexisting_block(peak_memory_db, -11, 4)

    rows = _execute_template(
        peak_memory_db,
        "active_blocks_at_event",
        {"event_id": 3, "include_static": False},
    )

    assert [row["id"] for row in rows] == [1]


def test_active_memory_callstack_at_event_treats_null_free_event_as_live(
    peak_memory_db: Path,
) -> None:
    conn = sqlite3.connect(str(peak_memory_db))
    conn.execute(
        """
        INSERT INTO block_0
          (id, address, size, requestedSize, state, allocEventId, freeEventId)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (6, 0x6000, 1536, 1500, 1, 2, None),
    )
    conn.commit()
    conn.close()

    rows = _execute_template(
        peak_memory_db,
        "active_memory_callstack_at_event",
        {"event_id": 3, "include_static": False, "top_n": -1},
    )

    by_callstack = {row["callstack"]: row for row in rows}
    assert by_callstack["freed.py:20"]["size_bytes"] == 1536
    assert by_callstack["freed.py:20"]["block_count"] == 1


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


def test_active_memory_callstack_at_event_labels_preexisting_group(
    peak_memory_db: Path,
) -> None:
    _insert_preexisting_block(peak_memory_db, -11, 4)
    _insert_preexisting_block(peak_memory_db, -12, None)

    rows = _execute_template(
        peak_memory_db,
        "active_memory_callstack_at_event",
        {"event_id": 3, "include_static": True, "top_n": -1},
    )

    by_callstack = {row["callstack"]: row for row in rows}
    preexisting = by_callstack["[preexisting live] allocEventId=-1"]
    assert preexisting["category"] == "preexisting_live_at_event"
    assert preexisting["block_count"] == 2
    assert preexisting["size_bytes"] == 4096
    assert by_callstack["[static] allocEventId=-1, freeEventId=-1"]["category"] == "static"


def test_active_memory_callstack_at_event_keeps_special_groups_beyond_top_n(
    peak_memory_db: Path,
) -> None:
    conn = sqlite3.connect(str(peak_memory_db))
    conn.executemany(
        "INSERT INTO callstack (id, callstack) VALUES (?, ?)",
        [(10, "a.py:1"), (11, "b.py:2"), (12, "c.py:3")],
    )
    conn.executemany(
        """
        INSERT INTO trace_entry_0
          (id, action, address, size, stream, allocated, active, reserved, callstackId)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (-101, 2, 0x11000, 20000, 0, 0, 0, 0, 10),
            (-102, 2, 0x12000, 18000, 0, 0, 0, 0, 11),
            (-103, 2, 0x13000, 16000, 0, 0, 0, 0, 12),
        ],
    )
    conn.executemany(
        """
        INSERT INTO block_0
          (id, address, size, requestedSize, state, allocEventId, freeEventId)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (-11, 0x7000, 3000, 2900, 1, -1, 4),
            (11, 0x11000, 20000, 19900, 1, -101, -1),
            (12, 0x12000, 18000, 17900, 1, -102, -1),
            (13, 0x13000, 16000, 15900, 1, -103, -1),
        ],
    )
    conn.commit()
    conn.close()

    rows = _execute_template(
        peak_memory_db,
        "active_memory_callstack_at_event",
        {"event_id": 3, "include_static": True, "top_n": 2},
    )

    by_callstack = {row["callstack"]: row for row in rows}
    # Only the two largest dynamic groups survive top_n; static and preexisting
    # groups are exempt from truncation even though smaller groups were dropped.
    assert set(by_callstack) == {
        "a.py:1",
        "b.py:2",
        "[static] allocEventId=-1, freeEventId=-1",
        "[preexisting live] allocEventId=-1",
    }
    assert by_callstack["[static] allocEventId=-1, freeEventId=-1"]["size_bytes"] == 8192
    assert by_callstack["[preexisting live] allocEventId=-1"]["size_bytes"] == 3000
    total = 20000 + 18000 + 8192 + 3000
    assert by_callstack["[static] allocEventId=-1, freeEventId=-1"][
        "percent_of_active_blocks"
    ] == pytest.approx(100.0 * 8192 / total, rel=1e-4)


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
