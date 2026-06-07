"""Tests for peak memory report service."""

import sqlite3
from pathlib import Path

import pytest

from pt_snap_cli.core.report_service import ReportService
from pt_snap_cli.query.registry import QueryRegistry, _load_all_templates


@pytest.fixture(autouse=True)
def _reload_query_templates():
    QueryRegistry.reset()
    _load_all_templates()


@pytest.fixture
def report_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "report.db"
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
            (2, 2, 0x2000, 2048, 0, 3072, 3072, 4096, "block.py:20"),
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


def test_peak_memory_report_selects_active_peak_event(report_db: Path) -> None:
    report = ReportService().peak_memory_report(report_db, metric="active")

    assert report.device_id == 0
    assert report.metric == "active"
    assert report.event_id == 5
    assert report.peak["peak_active"] == 5632
    assert report.allocator_gap is not None
    assert report.allocator_gap["peak_reserved_event_id"] == 3
    assert report.callstack_groups[0]["callstack"] == "[static] allocEventId=-1, freeEventId=-1"


def test_peak_memory_report_can_exclude_static(report_db: Path) -> None:
    report = ReportService().peak_memory_report(report_db, include_static=False)

    assert "[static] allocEventId=-1, freeEventId=-1" not in {
        row["callstack"] for row in report.callstack_groups
    }


def test_peak_memory_report_rejects_invalid_metric(report_db: Path) -> None:
    with pytest.raises(ValueError, match="Invalid metric"):
        ReportService().peak_memory_report(report_db, metric="invalid")  # type: ignore[arg-type]


def test_peak_memory_report_handles_empty_trace(tmp_path: Path) -> None:
    db_path = tmp_path / "empty.db"
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
    conn.commit()
    conn.close()

    report = ReportService().peak_memory_report(db_path)

    assert report.event_id is None
    assert report.allocator_gap is None
    assert report.callstack_groups == []
