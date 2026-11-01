"""Trusted in-memory numeric metadata rejection through the real import boundary.

Only the representation-loading seam is replaced: no pickle is created or
unpickled, and conversion, validation, error normalization and cleanup stay real.
Missing keys and arbitrary structural/type errors are a separate runtime gap;
this module covers the existing controlled ValueError conversion contract.
"""

from __future__ import annotations

import copy
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pt_snap_cli.core.errors import ImportExecutionError
from pt_snap_cli.core.snapshot_import_backend import SnapshotImportBackend
from pt_snap_cli.snapshot.tools.adaptors import snapshot2db

PROPERTY_SETTINGS = settings(
    max_examples=25, derandomize=True, database=None, deadline=None, print_blob=True
)


@pytest.mark.parametrize("field", ["addr", "size", "stream", "device_free", "id"])
@PROPERTY_SETTINGS
@given(suffix=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789 +-", max_size=40))
def test_generated_bad_numeric_snapshot_values_reject_without_publication(
    field: str, suffix: str
) -> None:
    event = {"action": "alloc", "addr": 4096, "size": 1, "stream": 0, "frames": []}
    event[field] = f"not-an-integer:{suffix}"
    representation = {"segments": [], "device_traces": [[event]]}
    before = copy.deepcopy(representation)

    with TemporaryDirectory() as directory, pytest.MonkeyPatch.context() as monkeypatch:
        root = Path(directory)
        source = root / "trusted-in-memory.pkl"
        output = root / "output"
        output.mkdir()
        backend = SnapshotImportBackend()
        destination = backend.target_db_path(source, output)
        destination.write_bytes(b"previous database must survive validation failure")
        previous = destination.read_bytes()
        loads = []

        def load_representation(path: Path) -> dict[str, object]:
            assert path == source
            loads.append(path)
            return representation

        monkeypatch.setattr(snapshot2db, "load_snapshot_representation", load_representation)
        with pytest.raises(ImportExecutionError, match="Snapshot import backend failed") as error:
            backend.dump_to_db(source, output, device=0)

        assert isinstance(error.value.__cause__, ValueError)
        assert loads == [source]
        assert representation == before
        assert not source.exists()
        assert destination.read_bytes() == previous
        assert list(output.iterdir()) == [destination]
