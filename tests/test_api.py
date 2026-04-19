"""Tests for the high-level SnapshotAnalyzer API."""

import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from pt_snap_cli.api import FocusState, SnapshotAnalyzer


@pytest.fixture
def valid_db() -> Path:
    """Create a valid test database."""
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


@pytest.fixture(autouse=True)
def _reset_registry():
    """Reset the query registry singleton between tests."""
    from pt_snap_cli.query.registry import QueryRegistry

    QueryRegistry.reset()


@pytest.fixture(autouse=True)
def _isolate_config():
    """Isolate Config from user's global config during tests."""
    original_env = os.environ.get("PT_SNAP_DB_PATH")
    if "PT_SNAP_DB_PATH" in os.environ:
        del os.environ["PT_SNAP_DB_PATH"]
    with patch.object(Path, "home", return_value=Path(tempfile.mkdtemp())):
        yield
    if original_env is not None:
        os.environ["PT_SNAP_DB_PATH"] = original_env


class TestFocusState:
    def test_focus_state_fields(self) -> None:
        state = FocusState(
            db_path="/tmp/test.db",
            device_id=0,
            source="explicit",
            available_devices=[0, 1],
        )
        assert state.db_path == "/tmp/test.db"
        assert state.device_id == 0
        assert state.source == "explicit"
        assert state.available_devices == [0, 1]


class TestSnapshotAnalyzerWithDB:
    def test_get_focus_with_explicit_db(self, valid_db: Path) -> None:
        analyzer = SnapshotAnalyzer(db_path=valid_db)
        state = analyzer.get_focus()
        assert state.db_path == str(valid_db)
        assert state.source == "explicit"
        assert 0 in state.available_devices

    def test_set_focus_changes_db(self, valid_db: Path, tmp_path: Path) -> None:
        """Create a second DB and switch focus."""
        second_db = tmp_path / "second.db"
        conn = sqlite3.connect(str(second_db))
        conn.execute(
            "CREATE TABLE dictionary (`table` TEXT, `column` TEXT, `key` TEXT, `value` TEXT)"
        )
        conn.execute("CREATE TABLE trace_entry_1 (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()

        analyzer = SnapshotAnalyzer(db_path=valid_db)
        assert analyzer.get_focus().db_path == str(valid_db)

        state = analyzer.set_focus(db_path=str(second_db), device_id=1)
        assert state.db_path == str(second_db)
        assert state.device_id == 1

        second_db.unlink(missing_ok=True)

    def test_set_focus_invalid_db(self) -> None:
        analyzer = SnapshotAnalyzer()
        with pytest.raises(FileNotFoundError):
            analyzer.set_focus(db_path="/nonexistent/path/db.sqlite")

    def test_list_templates(self) -> None:
        analyzer = SnapshotAnalyzer()
        templates = analyzer.list_templates()
        assert isinstance(templates, list)
        assert len(templates) > 0

    def test_list_templates_by_category(self) -> None:
        analyzer = SnapshotAnalyzer()
        result = analyzer.list_templates(category="basic")
        assert isinstance(result, list)

    def test_get_template_info_exists(self) -> None:
        analyzer = SnapshotAnalyzer()
        info = analyzer.get_template_info("leak_detection")
        assert info is not None
        assert info["name"] == "leak_detection"
        assert "description" in info

    def test_get_template_info_not_found(self) -> None:
        analyzer = SnapshotAnalyzer()
        info = analyzer.get_template_info("nonexistent_template_xyz")
        assert info is None

    def test_execute_query_requires_focus(self) -> None:
        analyzer = SnapshotAnalyzer()
        # Mock resolve_focus to return no configured DB
        from pt_snap_cli.config import ResolvedFocus

        with patch.object(analyzer._config, "resolve_focus") as mock_resolve:
            mock_resolve.return_value = ResolvedFocus(None, "none", None, None)
            with pytest.raises(RuntimeError, match="No database configured"):
                analyzer.execute_query("leak_detection")

    def test_execute_query_with_focus(self, valid_db: Path) -> None:
        analyzer = SnapshotAnalyzer(db_path=valid_db)
        result = analyzer.execute_query("leak_detection", max_rows=10)
        assert "total" in result
        assert "returned" in result
        assert "device_id" in result
        assert "rows" in result
        assert isinstance(result["rows"], list)

    def test_execute_query_max_rows_zero(self, valid_db: Path) -> None:
        """max_rows=0 returns all rows."""
        analyzer = SnapshotAnalyzer(db_path=valid_db)
        result = analyzer.execute_query("leak_detection", max_rows=0)
        # leak_detection on empty table returns 0 rows
        assert result["total"] == 0
        assert result["returned"] == 0
