"""Deterministic mutations across owned-cache inspection guard boundaries."""

import dataclasses
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from pt_snap_cli.core import msinsight_export as export
from pt_snap_cli.core.errors import ImportExecutionError
from pt_snap_cli.core.import_service import ImportService
from tests.core.test_dataset_import import hashes
from tests.core.test_msinsight_export import options


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("PT_SNAP_DB_PATH", raising=False)


def add_cache(path):
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute("CREATE TABLE memory_allocation_cache_v1_0 (value INTEGER)")
        conn.execute("INSERT INTO memory_allocation_cache_v1_0 VALUES (1)")


@pytest.mark.parametrize("force", [False, True])
def test_manifest_swap_after_validation_preserves_cache_and_focus(tmp_path, monkeypatch, force):
    request = options(tmp_path)
    service = ImportService()
    root = service.import_snapshot(request).db_path
    manifest = root / "manifest.json"
    focus = tmp_path / ".pt-snap/focus.json"
    old_focus = focus.read_bytes()
    original = export.validate_dataset
    changed = {}

    def swap(*args, **kwargs):
        result = original(*args, **kwargs)
        data = json.loads(manifest.read_text())
        data["sourceFile"] = str(tmp_path / "other" / request.snapshot_file.name)
        replacement = tmp_path / "replacement.json"
        replacement.write_text(json.dumps(data))
        replacement.replace(manifest)
        changed.update(hashes(root))
        return result

    monkeypatch.setattr(export, "validate_dataset", swap)
    with pytest.raises(ImportExecutionError, match="preserved even under --force"):
        service.import_snapshot(dataclasses.replace(request, force=force))
    assert changed and hashes(root) == changed
    assert focus.read_bytes() == old_focus


@pytest.mark.parametrize("force", [False, True])
def test_earlier_member_mutation_during_later_proof_is_rejected(tmp_path, monkeypatch, force):
    request = options(tmp_path)
    service = ImportService()
    root = service.import_snapshot(request).db_path
    members = sorted(root.glob("device_0/*.db"))
    assert len(members) > 1
    for member in members:
        add_cache(member)
    focus = tmp_path / ".pt-snap/focus.json"
    old_focus = focus.read_bytes()
    original = export.compare_member_content
    changed = {}
    visited = []

    def change_earlier(path, *args, **kwargs):
        original(path, *args, **kwargs)
        visited.append(path)
        if len(visited) == 2:
            with closing(sqlite3.connect(visited[0])) as conn, conn:
                conn.execute("UPDATE memory_allocation_cache_v1_0 SET value=2")
            changed.update(hashes(root))

    monkeypatch.setattr(export, "compare_member_content", change_earlier)
    with pytest.raises(ImportExecutionError, match="preserved even under --force"):
        service.import_snapshot(dataclasses.replace(request, force=force))
    assert changed and hashes(root) == changed
    assert focus.read_bytes() == old_focus


@pytest.mark.parametrize("kind", ["wal", "journal", "shm", "symlink", "unknown"])
@pytest.mark.parametrize("force", [False, True])
def test_late_transport_or_inventory_change_is_rejected(tmp_path, monkeypatch, kind, force):
    request = options(tmp_path)
    service = ImportService()
    root = service.import_snapshot(request).db_path
    members = sorted(root.glob("device_0/*.db"))
    for member in members:
        add_cache(member)
    focus = tmp_path / ".pt-snap/focus.json"
    old_focus = focus.read_bytes()
    original = export.compare_member_content
    changed = {}
    changed_path = None
    visited = []

    def inject_after_last_proof(path, *args, **kwargs):
        nonlocal changed_path
        original(path, *args, **kwargs)
        visited.append(path)
        if len(visited) != len(members):
            return
        if kind in ("wal", "journal", "shm"):
            changed_path = Path(str(visited[0]) + "-" + kind)
            changed_path.write_bytes(b"test-owned concurrent sidecar")
        elif kind == "symlink":
            saved = tmp_path / "saved-member.db"
            saved.write_bytes(visited[0].read_bytes())
            visited[0].unlink()
            visited[0].symlink_to(saved)
            changed_path = visited[0]
        else:
            changed_path = root / "user-notes"
            changed_path.write_text("concurrent user data")
        changed.update(hashes(root))

    monkeypatch.setattr(export, "compare_member_content", inject_after_last_proof)
    with pytest.raises(ImportExecutionError, match="preserved even under --force"):
        service.import_snapshot(dataclasses.replace(request, force=force))
    assert changed and hashes(root) == changed
    assert focus.read_bytes() == old_focus
    assert changed_path is not None and changed_path.exists()
    if kind == "symlink":
        assert changed_path.is_symlink()
