"""Cache-only SQLite drift must not weaken compatibility member ownership."""

import dataclasses
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from pt_snap_cli.api import SnapshotAnalyzer
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


def execute(path, sql, parameters=()):
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute(sql, parameters)


def read_manifest(root):
    return json.loads((root / "manifest.json").read_text())


def write_manifest(root, manifest):
    (root / "manifest.json").write_text(json.dumps(manifest))


def add_cache(path, device=0):
    execute(
        path, f"CREATE TABLE memory_allocation_cache_v1_{device} (event_id INTEGER, payload BLOB)"
    )
    execute(path, f"INSERT INTO memory_allocation_cache_v1_{device} VALUES (?, ?)", (0, b"cache"))


def assert_refused_without_changes(service, request, root):
    before = hashes(root)
    focus = request.snapshot_file.parent / ".pt-snap/focus.json"
    old_focus = focus.read_bytes() if focus.exists() else None
    for force in (False, True):
        with pytest.raises(ImportExecutionError, match="preserved even under --force"):
            service.import_snapshot(dataclasses.replace(request, force=force))
        assert hashes(root) == before
        assert (focus.read_bytes() if focus.exists() else None) == old_focus


def test_fresh_export_records_complete_content_proofs_and_keeps_export_version(tmp_path):
    from pt_snap_cli.core.msinsight_content_proof import member_content

    result = ImportService().import_snapshot(options(tmp_path, multiple=True))
    extension = read_manifest(result.db_path)["ptSnap"]
    assert extension["identity"]["exportContractVersion"] == 1
    content = extension["memberContent"]
    assert content["version"] == 1
    assert set(content["members"]) == set(extension["members"])
    for relative, proof in content["members"].items():
        path = result.db_path / relative
        assert proof == member_content(path)
        assert extension["members"][relative] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert set(proof) == {"schema", "tables"}
        assert {"dictionary", "pt_snap_metadata", "pt_snap_block_reference"} <= set(proof["tables"])
        assert all(len(row) == 4 for row in proof["schema"])


@pytest.mark.parametrize("multiple", [False, True])
def test_cache_addition_reuses_every_device_without_replay_or_writes(
    tmp_path, monkeypatch, multiple
):
    service = ImportService()
    request = options(tmp_path, multiple=multiple)
    first = service.import_snapshot(request)
    manifest = read_manifest(first.db_path)
    with SnapshotAnalyzer(first.db_path) as analyzer:
        expected = {
            device: analyzer.execute_query("event", {"id": 0}, device_id=device)["rows"]
            for device in first.devices
        }
    for device, inventory in manifest["devices"].items():
        for shard in inventory["slices"]:
            add_cache(first.db_path / shard["file"], int(device))
    before = hashes(first.db_path)
    monkeypatch.setattr(
        service._msinsight_backend.replay,
        "stage",
        lambda *a, **k: pytest.fail("cache-only reuse replayed input"),
    )
    for force in (False, True):
        reused = service.import_snapshot(dataclasses.replace(request, force=force))
        assert reused.reused and reused.metadata == first.metadata
    with SnapshotAnalyzer(first.db_path) as analyzer:
        for device in first.devices:
            assert (
                analyzer.execute_query("event", {"id": 0}, device_id=device)["rows"]
                == expected[device]
            )
    assert hashes(first.db_path) == before


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE trace_entry_0 SET size=size+1 WHERE id=0",
        "UPDATE block_0 SET size=size+1",
        "ALTER TABLE trace_entry_0 ADD COLUMN unexpected TEXT",
        "UPDATE pt_snap_metadata SET importer_version='changed'",
        "DELETE FROM pt_snap_block_reference",
        "UPDATE dictionary SET value='changed' WHERE key='0'",
        "DELETE FROM dictionary WHERE rowid=(SELECT MIN(rowid) FROM dictionary)",
        "INSERT INTO dictionary SELECT * FROM dictionary LIMIT 1",
        "DROP INDEX trace_entry_0_allocated",
    ],
)
def test_cache_does_not_mask_changes_to_base_content(tmp_path, sql):
    service = ImportService()
    request = options(tmp_path)
    result = service.import_snapshot(request)
    path = result.db_path / "device_0/slice_00000.db"
    add_cache(path)
    execute(path, sql)
    assert_refused_without_changes(service, request, result.db_path)


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE TABLE memory_allocation_cache_v2_0 (id INTEGER)",
        "CREATE TABLE memory_allocation_cache_v1_1 (id INTEGER)",
        "CREATE TABLE memory_allocation_cache_v1_00 (id INTEGER)",
        "CREATE TABLE unrelated (id INTEGER)",
        "CREATE VIEW memory_allocation_cache_v1_0 AS SELECT * FROM trace_entry_0",
        "CREATE VIRTUAL TABLE memory_allocation_cache_v1_0 USING fts5(payload)",
        "CREATE INDEX memory_allocation_cache_v1_0 ON trace_entry_0(size)",
        "CREATE TRIGGER memory_allocation_cache_v1_0 AFTER INSERT ON dictionary BEGIN SELECT 1; END",
    ],
)
def test_only_exact_ordinary_device_cache_table_is_permitted(tmp_path, sql):
    service = ImportService()
    request = options(tmp_path)
    result = service.import_snapshot(request)
    execute(result.db_path / "device_0/slice_00000.db", sql)
    assert_refused_without_changes(service, request, result.db_path)


@pytest.mark.parametrize(
    "object_sql",
    [
        "CREATE INDEX cache_index ON memory_allocation_cache_v1_0(event_id)",
        "CREATE TRIGGER cache_trigger AFTER INSERT ON memory_allocation_cache_v1_0 BEGIN SELECT 1; END",
    ],
)
def test_allowed_cache_table_does_not_allow_extra_schema_objects(tmp_path, object_sql):
    service = ImportService()
    request = options(tmp_path)
    result = service.import_snapshot(request)
    path = result.db_path / "device_0/slice_00000.db"
    add_cache(path)
    execute(path, object_sql)
    assert_refused_without_changes(service, request, result.db_path)


@pytest.mark.parametrize(
    "kind",
    [
        "null",
        "version",
        "boolean-version",
        "members",
        "missing-member",
        "extra-member",
        "schema",
        "tables",
        "rows",
        "digest",
    ],
)
def test_present_malformed_proof_is_rejected_even_when_raw_hash_matches(tmp_path, kind):
    service = ImportService()
    request = options(tmp_path)
    result = service.import_snapshot(request)
    manifest = read_manifest(result.db_path)
    content = manifest["ptSnap"]["memberContent"]
    first = next(iter(content["members"]))
    if kind == "null":
        manifest["ptSnap"]["memberContent"] = None
    elif kind == "version":
        content["version"] = 999
    elif kind == "boolean-version":
        content["version"] = True
    elif kind == "members":
        content["members"] = []
    elif kind == "missing-member":
        del content["members"][first]
    elif kind == "extra-member":
        content["members"]["extra.db"] = content["members"][first]
    elif kind == "schema":
        content["members"][first]["schema"] = "invalid"
    elif kind == "tables":
        content["members"][first]["tables"] = []
    elif kind == "rows":
        content["members"][first]["tables"]["dictionary"]["rows"] = True
    else:
        content["members"][first]["tables"]["dictionary"]["sha256"] = "not-a-digest"
    write_manifest(result.db_path, manifest)
    assert_refused_without_changes(service, request, result.db_path)


@pytest.mark.parametrize("changed", [False, True])
def test_legacy_no_proof_requires_exact_raw_bytes(tmp_path, changed):
    service = ImportService()
    request = options(tmp_path, focus=False)
    result = service.import_snapshot(request)
    manifest = read_manifest(result.db_path)
    del manifest["ptSnap"]["memberContent"]
    write_manifest(result.db_path, manifest)
    if changed:
        add_cache(result.db_path / "device_0/slice_00000.db")
        assert_refused_without_changes(service, request, result.db_path)
    else:
        before = hashes(result.db_path)
        assert service.import_snapshot(request).reused
        assert hashes(result.db_path) == before


def test_content_proof_hashes_sqlite_types_and_duplicate_multiplicity(tmp_path):
    from pt_snap_cli.core.msinsight_content_proof import member_content

    path = tmp_path / "types.db"
    execute(path, "CREATE TABLE sample (value)")
    proofs = []
    for value in (None, 1, 1.0, "1", b"1", b"\x00\xff"):
        execute(path, "DELETE FROM sample")
        execute(path, "INSERT INTO sample VALUES (?)", (value,))
        proofs.append(member_content(path)["tables"]["sample"])
    assert all(proof["rows"] == 1 for proof in proofs)
    assert len({proof["sha256"] for proof in proofs}) == len(proofs)
    execute(path, "INSERT INTO sample SELECT * FROM sample")
    duplicate = member_content(path)["tables"]["sample"]
    assert duplicate["rows"] == 2
    assert duplicate["sha256"] != proofs[-1]["sha256"]


def test_content_proof_ignores_row_order_and_schema_rootpage(tmp_path):
    from pt_snap_cli.core.msinsight_content_proof import member_content

    path = tmp_path / "layout.db"
    execute(path, "CREATE TABLE discarded (value)")
    execute(path, "CREATE TABLE sample (value)")
    execute(path, "DROP TABLE discarded")
    for value in ("first", "second", "first"):
        execute(path, "INSERT INTO sample VALUES (?)", (value,))
    before = member_content(path)
    with closing(sqlite3.connect(path)) as conn:
        old_rootpage = conn.execute(
            "SELECT rootpage FROM sqlite_master WHERE name='sample'"
        ).fetchone()
        conn.execute("VACUUM")
        new_rootpage = conn.execute(
            "SELECT rootpage FROM sqlite_master WHERE name='sample'"
        ).fetchone()
    assert old_rootpage != new_rootpage
    assert member_content(path) == before
    execute(path, "DELETE FROM sample")
    for value in ("first", "first", "second"):
        execute(path, "INSERT INTO sample VALUES (?)", (value,))
    assert member_content(path) == before


def test_compare_proves_base_even_when_allowed_cache_exists(tmp_path):
    from pt_snap_cli.core.msinsight_content_proof import (
        compare_member_content,
        member_content,
    )

    path = tmp_path / "base.db"
    execute(path, "CREATE TABLE sample (value)")
    execute(path, "INSERT INTO sample VALUES (?)", (b"base",))
    proof = member_content(path)
    compare_member_content(path, proof, 1)
    add_cache(path, 1)
    compare_member_content(path, proof, 1)
    execute(path, "UPDATE memory_allocation_cache_v1_1 SET payload=?", (b"recomputed",))
    compare_member_content(path, proof, 1)
    with pytest.raises(ValueError):
        compare_member_content(path, proof, 0)
    execute(path, "UPDATE sample SET value=?", (b"modified",))
    with pytest.raises(ValueError):
        compare_member_content(path, proof, 1)


def test_cache_for_another_device_cannot_hide_in_multi_device_dataset(tmp_path):
    service = ImportService()
    request = options(tmp_path, multiple=True)
    result = service.import_snapshot(request)
    add_cache(result.db_path / "device_1/slice_00000.db", 0)
    assert_refused_without_changes(service, request, result.db_path)
