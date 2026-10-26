"""Owned frame evidence must survive publication and repeat-import checks."""

import dataclasses
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from pt_snap_cli.core import import_service
from pt_snap_cli.core.errors import ImportExecutionError
from pt_snap_cli.core.import_service import ImportService
from tests.core.test_dataset_import import hashes
from tests.core.test_msinsight_export import options


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("PT_SNAP_DB_PATH", raising=False)


MUTATIONS = {
    "missing-table": "DROP TABLE pt_snap_stack_frame",
    "bad-count": "UPDATE pt_snap_stack SET frameCount=frameCount+1",
    "bad-index": "UPDATE pt_snap_stack_frame SET frameIndex=frameIndex+100",
    "orphan-frame": "UPDATE pt_snap_stack_frame SET frameId=999999",
    "orphan-event": "INSERT INTO pt_snap_event_stack VALUES(999999,0)",
    "nonfinite-json": "UPDATE pt_snap_frame_value SET frameJson='{\"name\":NaN}'",
    "duplicate-key": 'UPDATE pt_snap_frame_value SET frameJson=\'{"name":1,"name":2}\'',
}


@pytest.mark.parametrize("fmt", [None])
@pytest.mark.parametrize("mutation", MUTATIONS)
def test_invalid_new_frames_never_publish(tmp_path, monkeypatch, fmt, mutation):
    service = ImportService()
    request = dataclasses.replace(options(tmp_path, focus=False), format=fmt)
    backend = service._msinsight_backend if fmt else service._dataset_backend
    stage = backend.replay.stage

    def damaged_stage(*args, **kwargs):
        result = stage(*args, **kwargs)
        with closing(sqlite3.connect(result.slices[0].file)) as conn, conn:
            conn.execute(MUTATIONS[mutation])
        return result

    monkeypatch.setattr(backend.replay, "stage", damaged_stage)
    with pytest.raises(ImportExecutionError):
        service.import_snapshot(request)
    target = backend.target_path(request.snapshot_file, request.output_dir)
    assert not target.exists()
    assert not list(request.output_dir.glob(".*stage*"))
    assert not (tmp_path / ".pt-snap").exists()


@pytest.mark.parametrize("fmt", [None])
def test_invalid_new_declaration_never_publishes(tmp_path, monkeypatch, fmt):
    name = "build_compatible_manifest" if fmt else "build_native_manifest"
    build = getattr(import_service, name)

    def missing_declaration(*args, **kwargs):
        manifest = build(*args, **kwargs)
        manifest.pop("extensions")
        return manifest

    monkeypatch.setattr(import_service, name, missing_declaration)
    service = ImportService()
    request = dataclasses.replace(options(tmp_path, focus=False), format=fmt)
    with pytest.raises(ImportExecutionError):
        service.import_snapshot(request)
    backend = service._msinsight_backend if fmt else service._dataset_backend
    assert not backend.target_path(request.snapshot_file, request.output_dir).exists()


@pytest.mark.parametrize("fmt", [None])
@pytest.mark.parametrize("mutation", ["missing-table", "frame-content", "declaration"])
def test_repeat_import_rejects_changed_frames_without_overwriting(tmp_path, fmt, mutation):
    service = ImportService()
    request = dataclasses.replace(options(tmp_path, focus=False), format=fmt)
    first = service.import_snapshot(request)
    assert not first.reused
    assert service.import_snapshot(request).reused
    path = first.db_path / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    member = first.db_path / "device_0/slice_00000.db"
    if mutation == "declaration":
        manifest.pop("extensions")
    else:
        with closing(sqlite3.connect(member)) as conn, conn:
            conn.execute(
                MUTATIONS[mutation]
                if mutation == "missing-table"
                else 'UPDATE pt_snap_frame_value SET frameJson=\'{"name":"changed"}\''
            )
        if fmt is None and mutation == "missing-table":
            # Resealed malformed native members must still fail schema validation.
            manifest["devices"]["0"]["slices"][0]["sha256"] = hashlib.sha256(
                member.read_bytes()
            ).hexdigest()
    path.write_text(json.dumps(manifest), encoding="utf-8")
    before = hashes(first.db_path)
    with pytest.raises(ImportExecutionError):
        service.import_snapshot(request)
    assert hashes(first.db_path) == before
    assert not (tmp_path / ".pt-snap").exists()
    if fmt is None:
        rebuilt = service.import_snapshot(dataclasses.replace(request, force=True))
        assert not rebuilt.reused
        assert service.import_snapshot(request).reused
