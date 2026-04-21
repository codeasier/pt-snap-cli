import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from pt_snap_cli.config import Config
from pt_snap_cli.core import (
    FocusNotConfiguredError,
    InvalidCategoryError,
    InvalidDeviceError,
    QueryService,
    TemplateNotFoundError,
)
from pt_snap_cli.query.config import QueryTemplate
from pt_snap_cli.query.registry import QueryRegistry, register_query


@pytest.fixture(autouse=True)
def mock_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PT_SNAP_DB_PATH", raising=False)
    with patch.object(Path, "home", return_value=tmp_path):
        QueryRegistry.reset()
        yield
        QueryRegistry.reset()


@pytest.fixture
def sample_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "sample.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE dictionary (`table` TEXT, `column` TEXT, `key` TEXT, `value` TEXT)")
    conn.execute("CREATE TABLE trace_entry_0 (id INTEGER PRIMARY KEY, size INTEGER)")
    conn.execute("CREATE TABLE trace_entry_1 (id INTEGER PRIMARY KEY, size INTEGER)")
    conn.execute("INSERT INTO trace_entry_0 (size) VALUES (10), (20)")
    conn.commit()
    conn.close()
    return db_path


class TestQueryService:
    def test_list_templates_invalid_category(self) -> None:
        with pytest.raises(InvalidCategoryError):
            QueryService().list_templates("does-not-exist")

    def test_get_template_info_missing(self) -> None:
        with pytest.raises(TemplateNotFoundError):
            QueryService().get_template_info("missing")

    def test_execute_query_requires_focus(self) -> None:
        with pytest.raises(FocusNotConfiguredError):
            QueryService().execute_query("leak_detection")

    def test_execute_query_uses_focused_device_zero(self, sample_db: Path) -> None:
        config = Config()
        config.write_project_focus(sample_db, device_id=0)
        register_query(
            QueryTemplate(
                name="size_query", description="Test", query="SELECT size FROM trace_entry_0"
            )
        )

        result = QueryService().execute_query("size_query")

        assert result.device_id == 0
        assert result.total == 2
        assert result.returned == 2

    def test_execute_query_explicit_device_zero_wins(self, sample_db: Path) -> None:
        config = Config()
        config.write_project_focus(sample_db, device_id=1)
        register_query(
            QueryTemplate(
                name="size_query", description="Test", query="SELECT size FROM trace_entry_0"
            )
        )

        result = QueryService().execute_query("size_query", device_id=0)

        assert result.device_id == 0

    def test_execute_query_max_rows_zero_is_unlimited(self, sample_db: Path) -> None:
        config = Config()
        config.write_project_focus(sample_db)
        register_query(
            QueryTemplate(
                name="size_query", description="Test", query="SELECT size FROM trace_entry_0"
            )
        )

        result = QueryService().execute_query("size_query", max_rows=0)

        assert result.total == 2
        assert result.returned == 2
        assert len(result.rows) == 2

    def test_execute_query_max_rows_positive_limits_rows(self, sample_db: Path) -> None:
        config = Config()
        config.write_project_focus(sample_db)
        register_query(
            QueryTemplate(
                name="size_query", description="Test", query="SELECT size FROM trace_entry_0"
            )
        )

        result = QueryService().execute_query("size_query", max_rows=1)

        assert result.total == 2
        assert result.returned == 1
        assert len(result.rows) == 1

    def test_execute_query_invalid_device(self, sample_db: Path) -> None:
        config = Config()
        config.write_project_focus(sample_db)
        register_query(
            QueryTemplate(
                name="size_query", description="Test", query="SELECT size FROM trace_entry_0"
            )
        )

        with pytest.raises(InvalidDeviceError):
            QueryService().execute_query("size_query", device_id=99)
