"""Performance regression test for :class:`SnapshotAnalyzer` connection reuse.

The MCP server keeps one :class:`SnapshotAnalyzer` alive across many
``execute_query`` tool calls. Without caching, every call would pay for
schema validation and a fresh ``sqlite3.connect`` URI handshake. This test
exercises the caching path and asserts that ten consecutive calls against
the same database are not catastrophically slower than one call -- a
backstop to catch accidental regressions where the cache is silently
bypassed.
"""

from __future__ import annotations

import sqlite3
import tempfile
import time
from pathlib import Path

from pt_snap_cli.api import SnapshotAnalyzer


def _make_db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE dictionary (`table` TEXT, `column` TEXT, `key` TEXT, `value` TEXT)")
    conn.execute("""
        CREATE TABLE trace_entry_0 (
            id INTEGER PRIMARY KEY, action INTEGER, address INTEGER,
            size INTEGER, stream INTEGER, allocated INTEGER,
            active INTEGER, reserved INTEGER, callstack TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE block_0 (
            id INTEGER PRIMARY KEY, address INTEGER, size INTEGER,
            requestedSize INTEGER, state INTEGER, allocEventId INTEGER,
            freeEventId INTEGER
        )
    """)
    # Populate enough rows so SQLite does some work, but not so much that
    # the test becomes flaky on slow machines.
    conn.executemany(
        "INSERT INTO block_0 (size, allocEventId, freeEventId) VALUES (?, ?, ?)",
        [(1024 * (i + 1), i + 1, -1) for i in range(200)],
    )
    conn.commit()
    conn.close()
    return db_path


def test_repeated_execute_query_uses_cached_connection() -> None:
    """A single cached connection must serve every call in the loop, so
    the cumulative time is dominated by the query cost and not by
    connection setup."""
    db_path = _make_db()
    try:
        analyzer = SnapshotAnalyzer(db_path=db_path)

        # Warm up the cache (first call pays the schema-validation cost).
        analyzer.execute_query("leak_detection")

        started = time.perf_counter()
        for _ in range(10):
            analyzer.execute_query("leak_detection")
        elapsed = time.perf_counter() - started

        # The cache should contain exactly one entry after the warmup.
        assert len(analyzer.context_cache) == 1

        # 10 query calls each fetching ~200 rows must finish well under a
        # second on any reasonable machine; we use a generous 2 s budget to
        # avoid CI flakes while still failing if connection setup is
        # accidentally reintroduced per call (that would push elapsed time
        # into the multi-second range even on fast disks).
        assert elapsed < 2.0, f"10 cached queries took {elapsed:.3f}s"
    finally:
        db_path.unlink(missing_ok=True)
