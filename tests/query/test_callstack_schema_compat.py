"""Read-only v1/v2 callstack schema compatibility for packaged templates."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

from pt_snap_cli.context import Context, SchemaVersionError
from pt_snap_cli.core.query_service import QueryService
from pt_snap_cli.query.executor import QueryExecutionError, QueryExecutor
from pt_snap_cli.query.registry import QueryRegistry, _load_all_templates, get_query


@pytest.fixture(autouse=True)
def _reload_query_templates() -> None:
    QueryRegistry.reset()
    _load_all_templates()


_BLOCKS = [
    (-10, 0xA000, 8192, 8000, 1, -1, -1),
    (1, 0x1000, 1024, 1000, 1, 1, -1),
    (2, 0x2000, 2048, 2000, 0, 2, 3),
    (4, 0x4000, 4096, 4000, 1, 4, -1),
    (5, 0x5000, 512, 500, 1, 5, -1),
]
_EVENTS = [
    (1, 2, 0x1000, 1024, 0, 1024, 1024, 4096, "train.py:10"),
    (2, 2, 0x2000, 2048, 0, 3072, 3072, 4096, "freed.py:20"),
    (3, 3, 0x2000, 2048, 0, 1024, 1024, 8192, "free.py:30"),
    (4, 2, 0x4000, 4096, 0, 5120, 5120, 8192, "after.py:40"),
    (5, 2, 0x5000, 512, 0, 5632, 5632, 8192, None),
]


def _fingerprint(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest, path.stat().st_mtime_ns


def _create_dictionary(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE dictionary (`table` TEXT, `column` TEXT, `key` TEXT, `value` TEXT)")


def _create_block_table(conn: sqlite3.Connection, device_id: int = 0) -> None:
    conn.execute(f"""
        CREATE TABLE block_{device_id} (
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
        f"""
        INSERT INTO block_{device_id}
          (id, address, size, requestedSize, state, allocEventId, freeEventId)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        _BLOCKS,
    )


def _insert_metadata(conn: sqlite3.Connection, import_format_version: int) -> None:
    conn.execute("""
        CREATE TABLE pt_snap_metadata (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            metadata_schema_version INTEGER NOT NULL,
            import_format_version INTEGER NOT NULL,
            source_sha256 TEXT NOT NULL,
            source_size INTEGER NOT NULL,
            source_name TEXT NOT NULL,
            requested_device INTEGER,
            importer_name TEXT NOT NULL,
            importer_version TEXT NOT NULL,
            completed_at TEXT NOT NULL
        )
        """)
    conn.execute(
        """
        INSERT INTO pt_snap_metadata (
            id, metadata_schema_version, import_format_version, source_sha256,
            source_size, source_name, requested_device, importer_name,
            importer_version, completed_at
        ) VALUES (1, 1, ?, ?, 1, 'snapshot.pkl', NULL, 'pt-snap-cli', '0.2.0',
                  '2026-01-01T00:00:00+00:00')
        """,
        (import_format_version, "a" * 64),
    )


def create_v1_db(
    path: Path,
    *,
    metadata_version: int | None = None,
    extra_device: bool = False,
) -> Path:
    conn = sqlite3.connect(str(path))
    _create_dictionary(conn)
    devices = [0, 1] if extra_device else [0]
    for device_id in devices:
        conn.execute(f"""
            CREATE TABLE trace_entry_{device_id} (
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
        conn.executemany(
            f"""
            INSERT INTO trace_entry_{device_id}
              (id, action, address, size, stream, allocated, active, reserved, callstack)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            _EVENTS,
        )
        _create_block_table(conn, device_id)
    if metadata_version is not None:
        _insert_metadata(conn, metadata_version)
    conn.commit()
    conn.close()
    return path


def create_v2_db(path: Path, *, metadata_version: int | None = None) -> Path:
    conn = sqlite3.connect(str(path))
    _create_dictionary(conn)
    conn.execute("CREATE TABLE callstack (id INTEGER PRIMARY KEY, callstack TEXT)")
    texts = ["train.py:10", "freed.py:20", "free.py:30", "after.py:40"]
    conn.executemany(
        "INSERT INTO callstack (id, callstack) VALUES (?, ?)",
        list(enumerate(texts)),
    )
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
    conn.executemany(
        """
        INSERT INTO trace_entry_0
          (id, action, address, size, stream, allocated, active, reserved, callstackId)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [(*event[:-1], None if event[-1] is None else texts.index(event[-1])) for event in _EVENTS],
    )
    _create_block_table(conn)
    if metadata_version is not None:
        _insert_metadata(conn, metadata_version)
    conn.commit()
    conn.close()
    return path


def _execute(db_path: Path, name: str, params: dict | None = None) -> list[dict]:
    context = Context(db_path)
    try:
        return QueryExecutor(context).execute_template(name, params or {}, device_id=0)
    finally:
        context.close()


@pytest.fixture
def v1_db(tmp_path: Path) -> Path:
    return create_v1_db(tmp_path / "v1.db")


@pytest.fixture
def v2_db(tmp_path: Path) -> Path:
    return create_v2_db(tmp_path / "v2.db")


def test_packaged_callstack_templates_declare_both_variants() -> None:
    for name in ("event", "callstack_analysis", "active_memory_callstack_at_event"):
        template = get_query(name)
        assert template is not None
        assert set(template.query_variants) == {"v1", "v2"}
        assert "callstackId" in template.query_variants["v2"]
        assert "callstackId" not in template.query_variants["v1"]


def test_event_results_match_across_v1_and_v2(v1_db: Path, v2_db: Path) -> None:
    v1_rows = _execute(v1_db, "event", {"order_by": "id", "order_dir": "ASC"})
    v2_rows = _execute(v2_db, "event", {"order_by": "id", "order_dir": "ASC"})
    assert [row["id"] for row in v1_rows] == [1, 2, 3, 4, 5]
    assert [row["callstack"] for row in v1_rows] == [row["callstack"] for row in v2_rows]
    assert v1_rows[0]["callstack"] == "train.py:10"
    assert v1_rows[-1]["callstack"] is None


def test_callstack_analysis_aggregates_match_across_layouts(v1_db: Path, v2_db: Path) -> None:
    params = {"min_count": 1, "min_size": 0}
    v1_rows = _execute(v1_db, "callstack_analysis", params)
    v2_rows = _execute(v2_db, "callstack_analysis", params)
    assert [(row["callstack"], row["alloc_count"], row["total_size"]) for row in v1_rows] == [
        (row["callstack"], row["alloc_count"], row["total_size"]) for row in v2_rows
    ]
    assert [row["callstack"] for row in v1_rows] == [
        "after.py:40",
        "free.py:30",
        "freed.py:20",
        "train.py:10",
    ]


def test_active_memory_callstack_groups_match_across_layouts(v1_db: Path, v2_db: Path) -> None:
    params = {"event_id": 5, "include_static": True, "top_n": -1}
    v1_rows = _execute(v1_db, "active_memory_callstack_at_event", params)
    v2_rows = _execute(v2_db, "active_memory_callstack_at_event", params)
    assert {row["callstack"]: row["size_bytes"] for row in v1_rows} == {
        row["callstack"]: row["size_bytes"] for row in v2_rows
    }
    by_callstack = {row["callstack"]: row for row in v1_rows}
    assert by_callstack["[static] allocEventId=-1, freeEventId=-1"]["size_bytes"] == 8192
    assert by_callstack["after.py:40"]["size_bytes"] == 4096
    assert by_callstack["[missing callstack]"]["requested_bytes"] == 500


def test_v1_callstack_analysis_pagination_and_total(v1_db: Path) -> None:
    result = QueryService().execute_query(
        "callstack_analysis",
        params={"min_count": 1, "min_size": 0},
        db_path=v1_db,
        max_rows=2,
    )
    assert result.total == 4
    assert result.returned == 2
    assert [row["callstack"] for row in result.rows] == ["after.py:40", "free.py:30"]


def test_v2_callstack_analysis_keeps_id_aggregation(v2_db: Path) -> None:
    context = Context(v2_db)
    sql = QueryExecutor(context).render(
        get_query("callstack_analysis"),
        {"min_count": 1, "min_size": 0, "limit": -1},
        device_id=0,
    )
    normalized = sql.replace("GROUP BY callstackId", "")
    assert "GROUP BY callstackId" in sql
    assert "GROUP BY callstack" not in normalized
    context.close()


def test_v1_callstack_analysis_groups_by_text(v1_db: Path) -> None:
    context = Context(v1_db)
    sql = QueryExecutor(context).render(
        get_query("callstack_analysis"),
        {"min_count": 1, "min_size": 0, "limit": -1},
        device_id=0,
    )
    assert "GROUP BY callstack" in sql
    assert "callstackId" not in sql
    context.close()


def test_query_and_focus_do_not_write_v1_database(v1_db: Path) -> None:
    before = _fingerprint(v1_db)
    QueryService().execute_query("event", db_path=v1_db, params={"limit": 1})
    Context(v1_db)
    assert _fingerprint(v1_db) == before


@pytest.mark.parametrize("metadata_version", [None, 1])
def test_v1_layout_detected_with_or_without_metadata(
    tmp_path: Path, metadata_version: int | None
) -> None:
    db_path = create_v1_db(tmp_path / "legacy.db", metadata_version=metadata_version)
    assert Context(db_path).callstack_layout == "v1"


@pytest.mark.parametrize("metadata_version", [None, 2])
def test_v2_layout_detected_with_or_without_metadata(
    tmp_path: Path, metadata_version: int | None
) -> None:
    db_path = create_v2_db(tmp_path / "current.db", metadata_version=metadata_version)
    assert Context(db_path).callstack_layout == "v2"


def test_multi_device_v1_layout_is_consistent(tmp_path: Path) -> None:
    db_path = create_v1_db(tmp_path / "multi.db", extra_device=True)
    ctx = Context(db_path)
    assert ctx.device_ids == [0, 1]
    assert ctx.callstack_layout == "v1"
    rows = QueryExecutor(ctx).execute_template("event", {"id": 1}, device_id=1)
    assert rows[0]["callstack"] == "train.py:10"


def test_metadata_conflict_is_a_schema_error(tmp_path: Path) -> None:
    db_path = create_v1_db(tmp_path / "conflict.db", metadata_version=2)
    with pytest.raises(SchemaVersionError, match="import_format_version is 2"):
        Context(db_path)


def test_unknown_metadata_version_does_not_override_structure(tmp_path: Path) -> None:
    db_path = create_v2_db(tmp_path / "future.db", metadata_version=3)
    assert Context(db_path).callstack_layout == "v2"


def test_mixed_device_layouts_are_a_schema_error(tmp_path: Path) -> None:
    db_path = tmp_path / "mixed.db"
    conn = sqlite3.connect(str(db_path))
    _create_dictionary(conn)
    conn.execute("CREATE TABLE trace_entry_0 (id INTEGER PRIMARY KEY, callstack TEXT)")
    conn.execute("CREATE TABLE trace_entry_1 (id INTEGER PRIMARY KEY, callstackId INTEGER)")
    conn.execute("CREATE TABLE callstack (id INTEGER PRIMARY KEY, callstack TEXT)")
    conn.commit()
    conn.close()
    with pytest.raises(SchemaVersionError, match="devices disagree"):
        Context(db_path)


def test_unknown_layout_errors_only_for_variant_templates(tmp_path: Path) -> None:
    db_path = tmp_path / "unknown.db"
    conn = sqlite3.connect(str(db_path))
    _create_dictionary(conn)
    conn.execute("CREATE TABLE trace_entry_0 (id INTEGER PRIMARY KEY, size INTEGER)")
    conn.commit()
    conn.close()

    ctx = Context(db_path)
    assert ctx.callstack_layout is None
    with pytest.raises(QueryExecutionError, match="needs a v1 or v2 callstack layout"):
        QueryExecutor(ctx).execute_template("event", device_id=0)
