import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from pt_snap_cli.core import FocusNotConfiguredError, OverviewService
from pt_snap_cli.core.import_metadata import ImportMetadataService


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PT_SNAP_DB_PATH", raising=False)
    with patch.object(Path, "home", return_value=tmp_path):
        yield


def _overview_db(path: Path) -> Path:
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE dictionary (`table` TEXT, `column` TEXT, `key` TEXT, `value` TEXT)")
    for device_id, event_ids in {0: (1, 4, 9), 1: (10, 12)}.items():
        conn.execute(f"""
            CREATE TABLE trace_entry_{device_id} (
                id INTEGER PRIMARY KEY, action INTEGER, address INTEGER, size INTEGER,
                stream INTEGER, allocated INTEGER, active INTEGER, reserved INTEGER, callstack TEXT
            )
            """)
        conn.executemany(
            f"INSERT INTO trace_entry_{device_id} (id, action) VALUES (?, 4)",
            [(event_id,) for event_id in event_ids],
        )
    conn.commit()
    conn.close()
    return path


def test_overview_reports_devices_bounds_and_missing_metadata(tmp_path: Path) -> None:
    db_path = _overview_db(tmp_path / "overview.db")
    payload = OverviewService().overview_to_dict(OverviewService().inspect(db_path))

    assert payload["db_path"] == str(db_path.resolve())
    assert payload["focus_source"] == "explicit"
    assert payload["devices"] == [
        {"device_id": 0, "first_event_id": 1, "last_event_id": 9},
        {"device_id": 1, "first_event_id": 10, "last_event_id": 12},
    ]
    assert payload["import_metadata"]["status"] == "unavailable"
    assert payload["import_metadata"]["reason"] == "metadata_missing"


def test_overview_includes_available_import_metadata(tmp_path: Path) -> None:
    db_path = _overview_db(tmp_path / "with_meta.db")
    source = tmp_path / "snapshot.pkl"
    source.write_bytes(b"snapshot")
    service = ImportMetadataService()
    digest = service.calculate_sha256(source)
    service.write(db_path, service.build_metadata(source, digest, None))

    payload = OverviewService().overview_to_dict(OverviewService().inspect(db_path))
    assert payload["import_metadata"]["status"] == "available"
    assert payload["import_metadata"]["metadata"]["source_sha256"] == digest


def test_overview_requires_a_database() -> None:
    with pytest.raises(FocusNotConfiguredError):
        OverviewService().inspect()


def test_overview_empty_device_has_null_bounds(tmp_path: Path) -> None:
    db_path = tmp_path / "empty.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE dictionary (`table` TEXT, `column` TEXT, `key` TEXT, `value` TEXT)")
    conn.execute("CREATE TABLE trace_entry_0 (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

    payload = OverviewService().overview_to_dict(OverviewService().inspect(db_path))
    assert payload["devices"] == [{"device_id": 0, "first_event_id": None, "last_event_id": None}]
