"""Tests for shell completion functions."""

import json
import sqlite3
from pathlib import Path

import pytest

from pt_snap_cli.completion import (
    complete_categories,
    complete_device_ids,
    complete_template_names,
)
from pt_snap_cli.config import (
    DB_PATH_KEY,
    PROJECT_FOCUS_DIR,
    PROJECT_FOCUS_FILE,
)
from pt_snap_cli.query.config import QueryTemplate
from pt_snap_cli.query.registry import QueryRegistry, register_query


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset query registry before each test."""
    QueryRegistry.reset()
    yield
    QueryRegistry.reset()


def _create_sample_db(db_path: Path) -> Path:
    """Create a sample SQLite database with device tables."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE dictionary (
            `table` TEXT, `column` TEXT, `key` TEXT, `value` TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE trace_entry_0 (
            id INTEGER PRIMARY KEY, action TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE trace_entry_1 (
            id INTEGER PRIMARY KEY, action TEXT
        )
    """)
    conn.commit()
    conn.close()
    return db_path


class TestCompleteTemplateNames:
    def test_returns_registered_templates(self):
        register_query(QueryTemplate(name="alpha_z_test", query="SELECT 1"))

        result = complete_template_names()
        assert "alpha_z_test" in result

    def test_returns_sorted(self):
        register_query(QueryTemplate(name="zebra_test", query="SELECT 1"))
        register_query(QueryTemplate(name="apple_test", query="SELECT 1"))
        after = complete_template_names()

        # Verify the result is sorted and contains our new entries
        assert after == sorted(after)
        assert "apple_test" in after
        assert "zebra_test" in after


class TestCompleteCategories:
    def test_returns_three_categories(self):
        result = complete_categories()
        assert len(result) == 3
        assert set(result) == {"basic", "statistical", "business"}

    def test_order_is_fixed(self):
        result = complete_categories()
        assert result == sorted(result)


class TestCompleteDeviceIds:
    def test_returns_device_ids_from_db(self, tmp_path: Path):
        db_path = _create_sample_db(tmp_path / "test.db")
        import os

        old_env = os.environ.get("PT_SNAP_DB_PATH")
        os.environ["PT_SNAP_DB_PATH"] = str(db_path)
        try:
            result = complete_device_ids()
            assert result == ["0", "1"]
        finally:
            if old_env is None:
                os.environ.pop("PT_SNAP_DB_PATH", None)
            else:
                os.environ["PT_SNAP_DB_PATH"] = old_env

    def test_returns_empty_for_no_db(self):
        result = complete_device_ids()
        # Without any DB configured, should return empty list
        assert result == []

    def test_returns_empty_for_invalid_db(self, tmp_path: Path):
        import os

        invalid_file = tmp_path / "not_a_db.txt"
        invalid_file.write_text("not a database")
        old_env = os.environ.get("PT_SNAP_DB_PATH")
        os.environ["PT_SNAP_DB_PATH"] = str(invalid_file)
        try:
            result = complete_device_ids()
            assert result == []
        finally:
            if old_env is None:
                os.environ.pop("PT_SNAP_DB_PATH", None)
            else:
                os.environ["PT_SNAP_DB_PATH"] = old_env

    def test_uses_project_focus(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        db_path = _create_sample_db(tmp_path / "test.db")
        focus_dir = tmp_path / PROJECT_FOCUS_DIR
        focus_dir.mkdir()
        focus_file = focus_dir / PROJECT_FOCUS_FILE
        focus_file.write_text(json.dumps({DB_PATH_KEY: str(db_path)}))
        monkeypatch.chdir(tmp_path)

        result = complete_device_ids()
        assert result == ["0", "1"]

    def test_sorted_by_integer_value(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Device IDs should be sorted numerically, not lexicographically."""
        import os

        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE dictionary (k TEXT, v TEXT)")
        for dev in [0, 1, 2, 10]:
            conn.execute(f"CREATE TABLE trace_entry_{dev} (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()

        old_env = os.environ.get("PT_SNAP_DB_PATH")
        os.environ["PT_SNAP_DB_PATH"] = str(db_path)
        try:
            result = complete_device_ids()
            assert result == ["0", "1", "2", "10"]
        finally:
            if old_env is None:
                os.environ.pop("PT_SNAP_DB_PATH", None)
            else:
                os.environ["PT_SNAP_DB_PATH"] = old_env
