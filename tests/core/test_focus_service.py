import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from pt_snap_cli.config import Config
from pt_snap_cli.core import (
    DatabaseMissingError,
    FocusNotConfiguredError,
    FocusService,
    InvalidDeviceError,
)


@pytest.fixture(autouse=True)
def mock_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PT_SNAP_DB_PATH", raising=False)
    with patch.object(Path, "home", return_value=tmp_path):
        yield


@pytest.fixture
def sample_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "sample.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE dictionary (`table` TEXT, `column` TEXT, `key` TEXT, `value` TEXT)")
    conn.execute("CREATE TABLE trace_entry_0 (id INTEGER PRIMARY KEY, size INTEGER)")
    conn.execute("CREATE TABLE trace_entry_1 (id INTEGER PRIMARY KEY, size INTEGER)")
    conn.commit()
    conn.close()
    return db_path


class TestFocusService:
    def test_get_focus_uses_project_focus(self, sample_db: Path) -> None:
        config = Config()
        config.write_project_focus(sample_db, device_id=0)

        state = FocusService(config).get_focus()

        assert state.db_path == sample_db.resolve()
        assert state.device_id == 0
        assert state.source == "project"
        assert state.available_devices == [0, 1]

    def test_get_focus_with_missing_db_keeps_state(self, tmp_path: Path) -> None:
        focus_dir = tmp_path / ".pt-snap"
        focus_dir.mkdir()
        (focus_dir / "focus.json").write_text(
            json.dumps({"db_path": "/missing.db", "device_id": 0})
        )

        state = FocusService().get_focus()

        assert state.db_path == Path("/missing.db")
        assert state.device_id == 0
        assert state.available_devices == []

    def test_set_project_focus_with_device_zero(self, sample_db: Path) -> None:
        state = FocusService().set_project_focus(sample_db, device_id=0)

        assert state.device_id == 0
        assert state.available_devices == [0, 1]
        focus_data = json.loads((Path.cwd() / ".pt-snap" / "focus.json").read_text())
        assert focus_data["device_id"] == 0

    def test_set_device_updates_project_focus(self, sample_db: Path) -> None:
        config = Config()
        config.write_project_focus(sample_db)

        state = FocusService(config).set_device(0)

        assert state.device_id == 0
        focus_data = json.loads((Path.cwd() / ".pt-snap" / "focus.json").read_text())
        assert focus_data["device_id"] == 0

    def test_set_device_without_focus_fails(self) -> None:
        with pytest.raises(FocusNotConfiguredError):
            FocusService().set_device(0)

    def test_set_device_with_missing_db_fails(self, tmp_path: Path) -> None:
        focus_dir = tmp_path / ".pt-snap"
        focus_dir.mkdir()
        (focus_dir / "focus.json").write_text(json.dumps({"db_path": "/missing.db"}))

        with pytest.raises(DatabaseMissingError):
            FocusService().set_device(0)

    def test_set_device_invalid_device_fails(self, sample_db: Path) -> None:
        config = Config()
        config.write_project_focus(sample_db)

        with pytest.raises(InvalidDeviceError):
            FocusService(config).set_device(99)

    def test_validate_session_db_returns_devices(self, sample_db: Path) -> None:
        state = FocusService().validate_session_db(sample_db)

        assert state.db_path == sample_db.resolve()
        assert state.available_devices == [0, 1]
        assert not (Path.cwd() / ".pt-snap" / "focus.json").exists()
