from __future__ import annotations

import sqlite3
from pathlib import Path

from pt_snap_cli.vendor.memsnapdump.tools.adaptors.database.snapshot_db import SnapshotDb
from pt_snap_cli.vendor.memsnapdump.util.sqlite_meta import SqliteDB


def _pragma(conn: sqlite3.Connection, name: str) -> object:
    return conn.execute(f"PRAGMA {name}").fetchone()[0]


def test_snapshot_db_optimizes_import_writes(tmp_path: Path) -> None:
    db = SnapshotDb(str(tmp_path / "snapshot.db"))
    try:
        assert _pragma(db.conn, "journal_mode") == "memory"
        assert _pragma(db.conn, "synchronous") == 0
        assert _pragma(db.conn, "cache_size") == -65536
    finally:
        db.conn.close()


def test_generic_sqlite_db_keeps_default_write_settings(tmp_path: Path) -> None:
    baseline = sqlite3.connect(tmp_path / "baseline.db")
    db = SqliteDB(str(tmp_path / "generic.db"))
    try:
        for name in ("journal_mode", "synchronous", "cache_size"):
            assert _pragma(db.conn, name) == _pragma(baseline, name)
    finally:
        db.conn.close()
        baseline.close()
