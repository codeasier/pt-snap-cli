from __future__ import annotations

import importlib
import pickle
import sys
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


def test_import_writes_db_and_sets_focus(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import_service_cls = _import_service_type()
    service = import_service_cls()
    project_dir = tmp_path / "project"
    output_dir = tmp_path / "output"
    project_dir.mkdir()
    monkeypatch.chdir(project_dir)

    result = service.import_snapshot(
        ImportOptions(snapshot_file=EMPTY_CACHE_SNAPSHOT, output_dir=output_dir)
    )

    assert result.db_path.exists()
    assert result.db_path.suffix == ".db"
    assert (project_dir / ".pt-snap" / "focus.json").exists()
    assert not (output_dir / ".pt-snap" / "focus.json").exists()
    assert result.reused is False
    assert result.cache_miss_reason == "database_missing"


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
    """Wrong suffix is rejected before the vendor backend is invoked."""
    import_service_cls = _import_service_type()
    service = import_service_cls()
    snapshot_file = tmp_path / "foo.txt"
    snapshot_file.write_bytes(b"any content is fine here - suffix is the only check")

    with pytest.raises(SnapshotFileInvalidError, match=r"\.pkl|\.pickle|suffix"):
        service.import_snapshot(ImportOptions(snapshot_file=snapshot_file))


def test_import_snapshot_file_invalid_corrupt_pickle(tmp_path: Path) -> None:
    """A .pkl file that cannot be unpickled surfaces as an import execution error.

    After removing the redundant upfront pickle.load, the suffix check passes
    for ``.pkl`` and the failure is reported by the vendored backend, which
    surfaces as :class:`ImportExecutionError`.
    """
    import_service_cls = _import_service_type()
    service = import_service_cls()
    snapshot_file = tmp_path / "corrupt.pkl"
    # Real pickle protocol header followed by garbage: passes suffix check,
    # fails inside the vendor's load_pickle_to_dict.
    snapshot_file.write_bytes(b"\x80\x04not a valid pickle stream")

    with pytest.raises(ImportExecutionError, match=r"backend (failed|reported failure)"):
        service.import_snapshot(ImportOptions(snapshot_file=snapshot_file))


def test_failed_reimport_preserves_existing_database(tmp_path: Path) -> None:
    import_service_cls = _import_service_type()
    service = import_service_cls()
    result = service.import_snapshot(
        ImportOptions(snapshot_file=EMPTY_CACHE_SNAPSHOT, output_dir=tmp_path, set_focus=False)
    )
    original_size = result.db_path.stat().st_size
    assert Context(result.db_path).discover_devices()

    with pytest.raises(ImportExecutionError, match=r"backend (failed|reported failure)"):
        service.import_snapshot(
            ImportOptions(
                snapshot_file=EMPTY_CACHE_SNAPSHOT, output_dir=tmp_path, device=999, set_focus=False
            )
        )

    assert result.db_path.exists()
    assert result.db_path.stat().st_size == original_size
    assert Context(result.db_path).discover_devices()


def test_import_replaces_destination_errors_are_wrapped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import_service_cls = _import_service_type()
    service = import_service_cls()

    def fail_replace(*args: object) -> None:
        raise OSError("cannot replace")

    monkeypatch.setattr("pt_snap_cli.core.snapshot_import_backend.os.replace", fail_replace)

    with pytest.raises(ImportExecutionError, match="cannot replace"):
        service.import_snapshot(
            ImportOptions(snapshot_file=EMPTY_CACHE_SNAPSHOT, output_dir=tmp_path, set_focus=False)
        )


def test_snapshot_import_backend_lazy_loads_vendor_module() -> None:
    sys.modules.pop("pt_snap_cli.core.snapshot_import_backend", None)
    vendor_module = "pt_snap_cli.vendor.memsnapdump.tools.adaptors.snapshot2db"
    sys.modules.pop(vendor_module, None)

    importlib.import_module("pt_snap_cli.core.snapshot_import_backend")

    assert vendor_module not in sys.modules


def test_import_raises_on_missing_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import_service_cls = _import_service_type()
    service = import_service_cls()

    def raise_missing_tool(*args: object, **kwargs: object) -> Path:
        raise ImportToolMissingError(
            "Vendored snapshot import backend is unavailable. Reinstall pt-snap-cli; "
            "the package may be incomplete."
        )

    monkeypatch.setattr(service._backend, "dump_to_db", raise_missing_tool)

    with pytest.raises(ImportToolMissingError, match="Vendored snapshot import backend"):
        service.import_snapshot(
            ImportOptions(snapshot_file=EMPTY_CACHE_SNAPSHOT, output_dir=tmp_path)
        )


def test_import_raises_on_upstream_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A backend that raises ImportExecutionError is propagated as-is."""
    import_service_cls = _import_service_type()
    service = import_service_cls()

    def fail_dump_to_db(
        snapshot_file: Path,
        dump_dir: Path,
        device: int | None,
        finalize_temp_db=None,
    ) -> Path:
        raise ImportExecutionError("Vendored snapshot import backend failed: upstream failed")

    monkeypatch.setattr(service._backend, "dump_to_db", fail_dump_to_db)

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


@pytest.mark.parametrize("character", ["?", "#"])
def test_import_supports_sqlite_uri_characters_in_filename(character: str, tmp_path: Path) -> None:
    import_service_cls = _import_service_type()
    service = import_service_cls()
    snapshot_file = tmp_path / f"snapshot{character}.pickle"
    snapshot_file.write_bytes(EMPTY_CACHE_SNAPSHOT.read_bytes())

    result = service.import_snapshot(
        ImportOptions(snapshot_file=snapshot_file, output_dir=tmp_path, set_focus=False)
    )

    assert result.db_path.name == f"snapshot{character}.pickle.db"
    assert service._metadata_service.inspect(result.db_path).status == "available"


def test_repeated_import_reuses_database_without_backend(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import_service_cls = _import_service_type()
    service = import_service_cls()
    first = service.import_snapshot(
        ImportOptions(snapshot_file=EMPTY_CACHE_SNAPSHOT, output_dir=tmp_path, set_focus=False)
    )

    def fail_if_called(*args: object, **kwargs: object) -> Path:
        raise AssertionError("backend must not run on cache hit")

    monkeypatch.setattr(service._backend, "dump_to_db", fail_if_called)
    second = service.import_snapshot(
        ImportOptions(snapshot_file=EMPTY_CACHE_SNAPSHOT, output_dir=tmp_path, set_focus=False)
    )

    assert second.db_path == first.db_path
    assert second.reused is True
    assert second.cache_miss_reason is None
    assert second.metadata == first.metadata


def test_force_rebuilds_compatible_database(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import_service_cls = _import_service_type()
    service = import_service_cls()
    service.import_snapshot(
        ImportOptions(snapshot_file=EMPTY_CACHE_SNAPSHOT, output_dir=tmp_path, set_focus=False)
    )
    original_dump = service._backend.dump_to_db
    calls = 0

    def counting_dump(*args: object, **kwargs: object) -> Path:
        nonlocal calls
        calls += 1
        return original_dump(*args, **kwargs)

    monkeypatch.setattr(service._backend, "dump_to_db", counting_dump)
    result = service.import_snapshot(
        ImportOptions(
            snapshot_file=EMPTY_CACHE_SNAPSHOT,
            output_dir=tmp_path,
            set_focus=False,
            force=True,
        )
    )

    assert calls == 1
    assert result.reused is False
    assert result.cache_miss_reason == "forced"


def test_force_first_import_reports_database_missing(tmp_path: Path) -> None:
    import_service_cls = _import_service_type()
    result = import_service_cls().import_snapshot(
        ImportOptions(
            snapshot_file=EMPTY_CACHE_SNAPSHOT,
            output_dir=tmp_path,
            set_focus=False,
            force=True,
        )
    )

    assert result.reused is False
    assert result.cache_miss_reason == "database_missing"


def test_malformed_metadata_rebuilds_database(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import sqlite3

    import_service_cls = _import_service_type()
    service = import_service_cls()
    first = service.import_snapshot(
        ImportOptions(snapshot_file=EMPTY_CACHE_SNAPSHOT, output_dir=tmp_path, set_focus=False)
    )
    with sqlite3.connect(first.db_path) as conn:
        conn.execute("UPDATE pt_snap_metadata SET source_sha256 = 'invalid'")

    original_dump = service._backend.dump_to_db
    calls = 0

    def counting_dump(*args: object, **kwargs: object) -> Path:
        nonlocal calls
        calls += 1
        return original_dump(*args, **kwargs)

    monkeypatch.setattr(service._backend, "dump_to_db", counting_dump)
    result = service.import_snapshot(
        ImportOptions(snapshot_file=EMPTY_CACHE_SNAPSHOT, output_dir=tmp_path, set_focus=False)
    )

    assert calls == 1
    assert result.reused is False
    assert result.cache_miss_reason == "metadata_invalid"
    assert service._metadata_service.inspect(result.db_path).status == "available"


def test_legacy_database_rebuilds_once_then_reuses(tmp_path: Path) -> None:
    import sqlite3

    import_service_cls = _import_service_type()
    service = import_service_cls()
    legacy_db = tmp_path / f"{EMPTY_CACHE_SNAPSHOT.name}.db"
    with sqlite3.connect(legacy_db) as conn:
        conn.execute(
            "CREATE TABLE dictionary (`table` TEXT, `column` TEXT, `key` TEXT, `value` TEXT)"
        )
        conn.execute("CREATE TABLE trace_entry_0 (id INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE block_0 (id INTEGER PRIMARY KEY)")

    rebuilt = service.import_snapshot(
        ImportOptions(snapshot_file=EMPTY_CACHE_SNAPSHOT, output_dir=tmp_path, set_focus=False)
    )
    reused = service.import_snapshot(
        ImportOptions(snapshot_file=EMPTY_CACHE_SNAPSHOT, output_dir=tmp_path, set_focus=False)
    )

    assert rebuilt.reused is False
    assert rebuilt.cache_miss_reason == "metadata_missing"
    assert reused.reused is True


def test_metadata_write_failure_preserves_existing_database(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from pt_snap_cli.core.errors import ImportMetadataError

    import_service_cls = _import_service_type()
    service = import_service_cls()
    first = service.import_snapshot(
        ImportOptions(snapshot_file=EMPTY_CACHE_SNAPSHOT, output_dir=tmp_path, set_focus=False)
    )
    original_metadata = service._metadata_service.inspect(first.db_path).metadata

    def fail_write(*args: object, **kwargs: object) -> None:
        raise ImportMetadataError("metadata write failed")

    monkeypatch.setattr(service._metadata_service, "write", fail_write)
    with pytest.raises(ImportExecutionError, match="metadata write failed"):
        service.import_snapshot(
            ImportOptions(
                snapshot_file=EMPTY_CACHE_SNAPSHOT,
                output_dir=tmp_path,
                set_focus=False,
                force=True,
            )
        )

    assert service._metadata_service.inspect(first.db_path).metadata == original_metadata


def test_initial_hash_failure_preserves_existing_database(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from pt_snap_cli.core.errors import ImportMetadataError

    import_service_cls = _import_service_type()
    service = import_service_cls()
    first = service.import_snapshot(
        ImportOptions(snapshot_file=EMPTY_CACHE_SNAPSHOT, output_dir=tmp_path, set_focus=False)
    )
    original_metadata = service._metadata_service.inspect(first.db_path).metadata
    monkeypatch.setattr(
        service._metadata_service,
        "calculate_sha256",
        lambda path: (_ for _ in ()).throw(ImportMetadataError("hash failed")),
    )

    with pytest.raises(ImportExecutionError, match="hash failed"):
        service.import_snapshot(
            ImportOptions(
                snapshot_file=EMPTY_CACHE_SNAPSHOT,
                output_dir=tmp_path,
                set_focus=False,
                force=True,
            )
        )

    assert service._metadata_service.inspect(first.db_path).metadata == original_metadata


def test_import_format_change_rebuilds_database(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import pt_snap_cli.core.import_metadata as metadata_module

    import_service_cls = _import_service_type()
    service = import_service_cls()
    service.import_snapshot(
        ImportOptions(snapshot_file=EMPTY_CACHE_SNAPSHOT, output_dir=tmp_path, set_focus=False)
    )
    monkeypatch.setattr(
        metadata_module,
        "IMPORT_FORMAT_VERSION",
        metadata_module.IMPORT_FORMAT_VERSION + 1,
    )

    result = service.import_snapshot(
        ImportOptions(snapshot_file=EMPTY_CACHE_SNAPSHOT, output_dir=tmp_path, set_focus=False)
    )

    assert result.reused is False
    assert result.cache_miss_reason == "import_format_changed"


def test_device_change_rebuilds_database(tmp_path: Path) -> None:
    import_service_cls = _import_service_type()
    service = import_service_cls()
    service.import_snapshot(
        ImportOptions(
            snapshot_file=MULTI_DEVICE_SNAPSHOT,
            output_dir=tmp_path,
            device=0,
            set_focus=False,
        )
    )

    result = service.import_snapshot(
        ImportOptions(
            snapshot_file=MULTI_DEVICE_SNAPSHOT,
            output_dir=tmp_path,
            device=1,
            set_focus=False,
        )
    )

    assert result.reused is False
    assert result.cache_miss_reason == "device_changed"
    assert result.metadata.requested_device == 1


def test_source_change_during_import_preserves_existing_database(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from pt_snap_cli.core.errors import SourceChangedError

    import_service_cls = _import_service_type()
    service = import_service_cls()
    first = service.import_snapshot(
        ImportOptions(snapshot_file=EMPTY_CACHE_SNAPSHOT, output_dir=tmp_path, set_focus=False)
    )
    original_size = first.db_path.stat().st_size
    hashes = iter(["a" * 64, "b" * 64])
    monkeypatch.setattr(service._metadata_service, "calculate_sha256", lambda path: next(hashes))

    with pytest.raises(SourceChangedError, match="source changed"):
        service.import_snapshot(
            ImportOptions(
                snapshot_file=EMPTY_CACHE_SNAPSHOT,
                output_dir=tmp_path,
                set_focus=False,
                force=True,
            )
        )

    assert first.db_path.stat().st_size == original_size
    assert sorted(path.name for path in tmp_path.iterdir()) == [first.db_path.name]
