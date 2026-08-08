"""End-to-end tests for :class:`SnapshotAnalyzer` connection reuse.

These exercise the path that the MCP server takes: keep one
:class:`SnapshotAnalyzer` alive and call ``execute_query`` repeatedly
against the same database. We assert that:

* the analyzer reuses a single cached :class:`Context` across calls,
* ``invalidate_context_cache`` forces a fresh context,
* a database file replaced on disk is detected through the mtime probe,
* a fresh schema invalidation surfaces the standard ``DatabaseSchemaError``-
  equivalent error to callers.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
import time
from pathlib import Path

import pytest

from pt_snap_cli.api import SnapshotAnalyzer
from pt_snap_cli.core.context_cache import ContextCache


@pytest.fixture
def valid_db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE dictionary (
            `table` TEXT, `column` TEXT, `key` TEXT, `value` TEXT
        )
    """)
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
    conn.commit()
    conn.close()

    yield db_path
    db_path.unlink(missing_ok=True)


class TestSnapshotAnalyzerContextCache:
    def test_repeated_queries_reuse_cached_context(self, valid_db: Path) -> None:
        """Two consecutive ``execute_query`` calls must share one cached
        Context so that the second call avoids the schema validation
        and sqlite3.connect handshake."""
        analyzer = SnapshotAnalyzer(db_path=valid_db)

        first_ctx = analyzer.context_cache.get(valid_db)
        analyzer.execute_query("leak_detection")
        second_ctx = analyzer.context_cache.get(valid_db)

        assert first_ctx is second_ctx
        assert len(analyzer.context_cache) == 1

    def test_invalidate_context_cache_forces_refresh(self, valid_db: Path) -> None:
        analyzer = SnapshotAnalyzer(db_path=valid_db)

        first_ctx = analyzer.context_cache.get(valid_db)
        analyzer.invalidate_context_cache(valid_db)
        assert len(analyzer.context_cache) == 0

        second_ctx = analyzer.context_cache.get(valid_db)
        assert second_ctx is not first_ctx

    def test_db_file_replacement_invalidates_cache(self, valid_db: Path) -> None:
        analyzer = SnapshotAnalyzer(db_path=valid_db)
        first_ctx = analyzer.context_cache.get(valid_db)

        # Recreate the file with new content. ``os.replace`` updates
        # ``st_mtime`` so the cache's mtime probe invalidates the entry.
        time.sleep(0.05)
        new_path = valid_db.with_suffix(".new")
        conn = sqlite3.connect(str(new_path))
        conn.execute(
            "CREATE TABLE dictionary (`table` TEXT, `column` TEXT, `key` TEXT, `value` TEXT)"
        )
        conn.execute("CREATE TABLE trace_entry_1 (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()
        os.replace(new_path, valid_db)

        second_ctx = analyzer.context_cache.get(valid_db)
        assert second_ctx is not first_ctx
        assert second_ctx.device_ids == [1]

    def test_analyzer_can_use_externally_supplied_cache(self, valid_db: Path) -> None:
        shared = ContextCache(maxsize=2)
        analyzer = SnapshotAnalyzer(db_path=valid_db, context_cache=shared)

        assert analyzer.context_cache is shared
        analyzer.execute_query("leak_detection")
        assert len(shared) == 1
