from __future__ import annotations

import pickle
from pathlib import Path

import pytest

from pt_snap_cli.context import Context
from pt_snap_cli.core.errors import (
    ImportExecutionError,
    ImportToolMissingError,
    SnapshotFileInvalidError,
)
from pt_snap_cli.core.models import ImportOptions

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "snapshots"
EMPTY_CACHE_SNAPSHOT = FIXTURE_DIR / "snapshot_with_empty_cache.pkl"
MULTI_DEVICE_SNAPSHOT = FIXTURE_DIR / "snapshot_with_multi_devices.pkl"


def _import_service_type():
    from pt_snap_cli.core.import_service import ImportService

    return ImportService


def test_import_writes_db_and_sets_focus(tmp_path: Path) -> None:
    import_service_cls = _import_service_type()
    service = import_service_cls()

    result = service.import_snapshot(
        ImportOptions(snapshot_file=EMPTY_CACHE_SNAPSHOT, output_dir=tmp_path)
    )

    assert result.db_path.exists()
    assert result.db_path.suffix == ".db"
    assert (tmp_path / ".pt-snap" / "focus.json").exists()


@pytest.mark.slow
def test_import_with_multi_device_fixture(tmp_path: Path) -> None:
    import_service_cls = _import_service_type()
    service = import_service_cls()

    result = service.import_snapshot(
        ImportOptions(snapshot_file=MULTI_DEVICE_SNAPSHOT, output_dir=tmp_path)
    )

    assert len(Context(result.db_path).discover_devices()) >= 2


def test_import_returns_focus_state(tmp_path: Path) -> None:
    import_service_cls = _import_service_type()
    service = import_service_cls()

    result = service.import_snapshot(
        ImportOptions(snapshot_file=EMPTY_CACHE_SNAPSHOT, output_dir=tmp_path)
    )

    assert result.focus_state is not None
    assert result.focus_state.source == "project"


def test_import_snapshot_file_invalid_missing(tmp_path: Path) -> None:
    import_service_cls = _import_service_type()
    service = import_service_cls()

    with pytest.raises(SnapshotFileInvalidError):
        service.import_snapshot(ImportOptions(snapshot_file=tmp_path / "missing.pkl"))


def test_import_snapshot_file_invalid_suffix(tmp_path: Path) -> None:
    import_service_cls = _import_service_type()
    service = import_service_cls()
    snapshot_file = tmp_path / "foo.txt"
    snapshot_file.write_bytes(b"not a pickle")

    with pytest.raises(SnapshotFileInvalidError):
        service.import_snapshot(ImportOptions(snapshot_file=snapshot_file))


def test_import_snapshot_file_invalid_corrupt_pickle(tmp_path: Path) -> None:
    import_service_cls = _import_service_type()
    service = import_service_cls()
    snapshot_file = tmp_path / "corrupt.pkl"
    snapshot_file.write_bytes(b"not a pickle")

    with pytest.raises(SnapshotFileInvalidError):
        service.import_snapshot(ImportOptions(snapshot_file=snapshot_file))


def test_import_raises_on_missing_tool(tmp_path: Path) -> None:
    import_service_cls = _import_service_type()
    service = import_service_cls()
    service._backend_available = False

    with pytest.raises(ImportToolMissingError, match="Vendored snapshot import backend"):
        service.import_snapshot(
            ImportOptions(snapshot_file=EMPTY_CACHE_SNAPSHOT, output_dir=tmp_path)
        )


def test_import_raises_on_upstream_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import_service_cls = _import_service_type()
    service = import_service_cls()

    def fail_dump_to_db(snapshot_file: Path, dump_dir: Path, device: int | None) -> Path:
        raise ImportExecutionError("Vendored snapshot import backend failed: upstream failed")

    monkeypatch.setattr(service, "_run_dump_to_db", fail_dump_to_db)

    with pytest.raises(ImportExecutionError):
        service.import_snapshot(
            ImportOptions(snapshot_file=EMPTY_CACHE_SNAPSHOT, output_dir=tmp_path)
        )


def test_import_skip_focus(tmp_path: Path) -> None:
    import_service_cls = _import_service_type()
    service = import_service_cls()

    result = service.import_snapshot(
        ImportOptions(
            snapshot_file=EMPTY_CACHE_SNAPSHOT,
            output_dir=tmp_path,
            set_focus=False,
        )
    )

    assert result.db_path.exists()
    assert not (tmp_path / ".pt-snap").exists()
    assert result.focus_state is None


def test_import_output_path_uses_full_filename(tmp_path: Path) -> None:
    import_service_cls = _import_service_type()
    service = import_service_cls()
    snapshot_file = tmp_path / "snapshot.pickle"
    snapshot_file.write_bytes(pickle.dumps({}))

    result = service.import_snapshot(
        ImportOptions(snapshot_file=snapshot_file, output_dir=tmp_path, set_focus=False)
    )

    assert result.db_path.name == "snapshot.pickle.db"
