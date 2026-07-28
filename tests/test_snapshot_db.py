from __future__ import annotations

from pathlib import Path

from pt_snap_cli.vendor.memsnapdump.tools.adaptors.database.snapshot_db import SnapshotDb
from pt_snap_cli.vendor.memsnapdump.util.sqlite_meta import SqliteDB


def _pragma(db: SqliteDB, name: str) -> object:
    return db.conn.execute(f"PRAGMA {name}").fetchone()[0]


def test_snapshot_db_optimizes_import_writes(tmp_path: Path) -> None:
    db = SnapshotDb(str(tmp_path / "snapshot.db"))
    try:
        assert _pragma(db, "journal_mode") == "memory"
        assert _pragma(db, "synchronous") == 0
        assert _pragma(db, "cache_size") == -65536
    finally:
        db.conn.close()


def test_generic_sqlite_db_keeps_default_write_settings(tmp_path: Path) -> None:
    db = SqliteDB(str(tmp_path / "generic.db"))
    try:
        assert _pragma(db, "journal_mode") == "delete"
        assert _pragma(db, "synchronous") == 2
        assert _pragma(db, "cache_size") != -65536
    finally:
        db.conn.close()
