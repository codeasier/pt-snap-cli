import os
from pathlib import Path

import pytest

from pt_snap_cli.core.errors import ImportExecutionError
from pt_snap_cli.core.snapshot_import_backend import SnapshotImportBackend


@pytest.fixture
def staged_backend(tmp_path, monkeypatch):
    backend = SnapshotImportBackend()
    source = tmp_path / "snapshot.pkl"
    output = tmp_path / "output"
    output.mkdir()
    destination = backend.target_db_path(source, output)
    destination.write_bytes(b"previous database")
    descriptors = []
    real_mkstemp = __import__("tempfile").mkstemp

    def tracked_mkstemp(*args, **kwargs):
        fd, name = real_mkstemp(*args, **kwargs)
        descriptors.append(fd)
        return fd, name

    def dump(snapshot_file, dump_dir, device):
        (Path(dump_dir) / destination.name).write_bytes(b"new database")
        return True

    monkeypatch.setattr(backend, "_load_run_dump_to_db", lambda: dump)
    monkeypatch.setattr(
        "pt_snap_cli.core.snapshot_import_backend.tempfile.mkstemp", tracked_mkstemp
    )
    yield backend, source, output, destination, descriptors
    # Leak detection is deterministic even on Python versions without ResourceWarning.
    for fd in descriptors:
        try:
            os.fstat(fd)
        except OSError:
            continue
        os.close(fd)
        pytest.fail("rollback descriptor was left open")


@pytest.mark.parametrize("failure", ["backup", "publish", "focus", "rollback"])
def test_failure_closes_rollback_descriptor(staged_backend, monkeypatch, failure):
    backend, source, output, destination, _ = staged_backend
    original = destination.read_bytes()

    def fail(*args, **kwargs):
        raise OSError(f"{failure} failed")

    def post_publish(path):
        assert path.read_bytes() == b"new database"
        if failure == "rollback":
            monkeypatch.setattr("pt_snap_cli.core.snapshot_import_backend.os.read", fail)
        if failure in ("focus", "rollback"):
            raise RuntimeError("focus failed")

    if failure == "backup":
        monkeypatch.setattr("pt_snap_cli.core.snapshot_import_backend.os.write", fail)
    elif failure == "publish":
        monkeypatch.setattr("pt_snap_cli.core.snapshot_import_backend.os.replace", fail)
    with pytest.raises((ImportExecutionError, RuntimeError), match="failed") as error:
        backend.dump_to_db(source, output, post_publish=post_publish)
    backups = list(output.glob("*.rollback"))
    if failure == "rollback":
        assert "Recovery backup:" in str(error.value)
        assert len(backups) == 1
        assert backups[0].read_bytes() == original
    else:
        assert destination.read_bytes() == original
        assert not backups
    assert not [p for p in output.iterdir() if p.is_dir()]


def test_short_backup_writes_preserve_complete_rollback(staged_backend, monkeypatch):
    backend, source, output, destination, _ = staged_backend
    original = destination.read_bytes()
    real_write = os.write
    monkeypatch.setattr(
        "pt_snap_cli.core.snapshot_import_backend.os.write",
        lambda fd, data: real_write(fd, data[:3]),
    )

    def fail_focus(path):
        raise RuntimeError("focus failed")

    with pytest.raises(RuntimeError, match="focus failed"):
        backend.dump_to_db(source, output, post_publish=fail_focus)
    assert destination.read_bytes() == original
    assert list(output.iterdir()) == [destination]


def test_zero_backup_write_fails_without_publishing(staged_backend, monkeypatch):
    backend, source, output, destination, _ = staged_backend
    monkeypatch.setattr("pt_snap_cli.core.snapshot_import_backend.os.write", lambda *args: 0)
    with pytest.raises(ImportExecutionError, match="backup"):
        backend.dump_to_db(source, output, post_publish=lambda path: None)
    assert destination.read_bytes() == b"previous database"


def test_missing_staged_database_does_not_publish(staged_backend, monkeypatch):
    backend, source, output, destination, _ = staged_backend
    monkeypatch.setattr(backend, "_load_run_dump_to_db", lambda: lambda **kwargs: True)
    with pytest.raises(ImportExecutionError, match="Expected database not produced"):
        backend.dump_to_db(source, output)
    assert list(output.iterdir()) == [destination]
    assert destination.read_bytes() == b"previous database"


def test_finalization_failure_does_not_publish(staged_backend):
    backend, source, output, destination, _ = staged_backend

    def fail_finalize(path):
        assert path.read_bytes() == b"new database"
        raise ValueError("metadata failed")

    with pytest.raises(ValueError, match="metadata failed"):
        backend.dump_to_db(source, output, finalize_temp_db=fail_finalize)
    assert list(output.iterdir()) == [destination]
    assert destination.read_bytes() == b"previous database"
