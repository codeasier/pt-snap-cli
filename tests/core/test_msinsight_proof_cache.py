"""Process-local proof reuse keeps strong byte and publication guards."""

import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock

import pytest

from pt_snap_cli.core import dataset_resolver
from pt_snap_cli.core import msinsight_export as export
from pt_snap_cli.core.import_service import ImportService
from pt_snap_cli.core.overview_service import OverviewService
from tests.core.test_dataset_import import hashes
from tests.core.test_msinsight_content_proof import (
    add_cache,
    execute,
    read_manifest,
    write_manifest,
)
from tests.core.test_msinsight_export import options


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("PT_SNAP_DB_PATH", raising=False)
    monkeypatch.delenv("PT_SNAP_DATASET_CACHE", raising=False)
    with export._OWNED_CACHE_LOCK:
        export._OWNED_CACHE.clear()
    with dataset_resolver._CACHE_LOCK:
        dataset_resolver._VALIDATED.clear()
    yield
    with export._OWNED_CACHE_LOCK:
        export._OWNED_CACHE.clear()
    with dataset_resolver._CACHE_LOCK:
        dataset_resolver._VALIDATED.clear()


@pytest.fixture
def root(tmp_path):
    result = ImportService().import_snapshot(options(tmp_path, focus=False))
    for path in result.db_path.glob("device_*/*.db"):
        add_cache(path)
    with export._OWNED_CACHE_LOCK:
        export._OWNED_CACHE.clear()
    return result.db_path


def spies(monkeypatch):
    validation = Mock(wraps=export.validate_dataset)
    proof = Mock(wraps=export.compare_member_content)
    monkeypatch.setattr(export, "validate_dataset", validation)
    monkeypatch.setattr(export, "compare_member_content", proof)
    return validation, proof


def test_cold_validates_and_warm_hashes_twice_without_sql(root, monkeypatch):
    validation, proof = spies(monkeypatch)
    before = hashes(root)
    first = export.inspect_owned_cache(root)
    members = sorted(root.glob("device_*/*.db"))
    assert validation.call_count == 1
    assert proof.call_count == len(members)
    digest = Mock(wraps=export.hash_file)
    inventory = Mock(wraps=export._cache_inventory)
    monkeypatch.setattr(export, "hash_file", digest)
    monkeypatch.setattr(export, "_cache_inventory", inventory)
    monkeypatch.setattr(
        export.sqlite3, "connect", lambda *a, **kw: pytest.fail("warm proof reuse opened SQLite")
    )
    assert export.inspect_owned_cache(root) == first
    assert validation.call_count == 1
    assert proof.call_count == len(members)
    hashed = [call.args[0] for call in digest.call_args_list]
    for path in [root / "manifest.json", *members]:
        assert hashed.count(path) >= 2
    assert inventory.call_count >= 2
    assert hashes(root) == before


@pytest.mark.parametrize("immutable", [False, True])
def test_same_size_restored_mtime_base_tamper_is_rejected_and_evicts(root, immutable, monkeypatch):
    if immutable:
        monkeypatch.setenv("PT_SNAP_DATASET_CACHE", "immutable")
    export.inspect_owned_cache(root)
    member = root / "device_0/slice_00000.db"
    stamp = member.stat()
    execute(member, "UPDATE trace_entry_0 SET size=size+1 WHERE id=0")
    assert member.stat().st_size == stamp.st_size
    os.utime(member, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    assert member.stat().st_mtime_ns == stamp.st_mtime_ns
    with pytest.raises(ValueError):
        export.inspect_owned_cache(root)
    assert root not in export._OWNED_CACHE


@pytest.mark.parametrize("change", ["manifest", "proof", "cache-rows"])
def test_changed_fingerprint_revalidates_instead_of_using_warm_proof(root, monkeypatch, change):
    validation, proof = spies(monkeypatch)
    export.inspect_owned_cache(root)
    validation.reset_mock()
    proof.reset_mock()
    manifest = read_manifest(root)
    if change == "manifest":
        (root / "manifest.json").write_text((root / "manifest.json").read_text() + "\n")
    elif change == "proof":
        first = next(iter(manifest["ptSnap"]["memberContent"]["members"].values()))
        first["tables"]["dictionary"]["sha256"] = "0" * 64
        write_manifest(root, manifest)
    else:
        execute(
            root / "device_0/slice_00000.db",
            "UPDATE memory_allocation_cache_v1_0 SET payload=X'1234'",
        )
    if change == "proof":
        with pytest.raises(ValueError):
            export.inspect_owned_cache(root)
        assert root not in export._OWNED_CACHE
    else:
        export.inspect_owned_cache(root)
    assert validation.call_count == 1
    assert proof.call_count >= 1


@pytest.mark.parametrize("kind", ["wal", "journal", "extra", "alias"])
def test_warm_cache_rejects_sidecars_extra_files_and_member_aliases(root, kind):
    export.inspect_owned_cache(root)
    member = root / "device_0/slice_00000.db"
    if kind == "alias":
        destination = root.parent / "member-copy.db"
        shutil.copyfile(member, destination)
        member.unlink()
        member.symlink_to(destination)
    else:
        path = Path(str(member) + {"wal": "-wal", "journal": "-journal", "extra": ".notes"}[kind])
        path.write_bytes(b"unexpected")
    before = hashes(root)
    with pytest.raises(ValueError):
        export.inspect_owned_cache(root)
    assert root not in export._OWNED_CACHE
    assert hashes(root) == before


@pytest.mark.parametrize("warm", [False, True])
def test_final_guard_failure_cannot_admit_or_retain_a_proof(root, monkeypatch, warm):
    if warm:
        export.inspect_owned_cache(root)
    original = export.hash_file
    manifest_reads = 0

    def fail_final_hash(path):
        nonlocal manifest_reads
        digest = original(path)
        if path == root / "manifest.json":
            manifest_reads += 1
            if manifest_reads == 2:
                return "0" * 64
        return digest

    with monkeypatch.context() as patch:
        patch.setattr(export, "hash_file", fail_final_hash)
        with pytest.raises(ValueError):
            export.inspect_owned_cache(root)
    assert root not in export._OWNED_CACHE
    validation, _ = spies(monkeypatch)
    export.inspect_owned_cache(root)
    assert validation.call_count == 1


def test_owned_cache_is_bounded_and_evicts_least_recently_used(root, monkeypatch):
    roots = [root]
    for index in range(16):
        destination = root.parent / f"copy-{index}"
        shutil.copytree(root, destination)
        roots.append(destination)
    for path in roots[:16]:
        export.inspect_owned_cache(path)
    assert len(export._OWNED_CACHE) == 16
    export.inspect_owned_cache(roots[0])
    export.inspect_owned_cache(roots[16])
    assert len(export._OWNED_CACHE) == 16
    assert roots[0] in export._OWNED_CACHE
    assert roots[1] not in export._OWNED_CACHE
    validation, _ = spies(monkeypatch)
    export.inspect_owned_cache(roots[1])
    assert validation.call_count == 1


def test_mutating_returned_identity_cannot_poison_cached_result(root):
    first = export.inspect_owned_cache(root)
    expected = first.identity.copy()
    first.identity["exportContractVersion"] = 999
    second = export.inspect_owned_cache(root)
    assert second.identity == expected
    second.identity.clear()
    assert export.inspect_owned_cache(root).identity == expected


def test_overview_reuses_its_resolution_for_one_base_validation(root, monkeypatch):
    with dataset_resolver._CACHE_LOCK:
        dataset_resolver._VALIDATED.clear()
    resolver_validation = Mock(wraps=dataset_resolver.validate_dataset)
    monkeypatch.setattr(dataset_resolver, "validate_dataset", resolver_validation)
    own_validation, proof = spies(monkeypatch)
    resolver_inspect = Mock(wraps=dataset_resolver.DatasetResolver().inspect)
    monkeypatch.setattr(dataset_resolver.DatasetResolver, "inspect", resolver_inspect)
    before = hashes(root)
    service = OverviewService()
    try:
        result = service.inspect(root)
    finally:
        service.close()
    assert result.metadata.status == "available"
    assert resolver_inspect.call_count == 1
    assert resolver_validation.call_count == 1
    assert own_validation.call_count == 0
    assert proof.call_count == len(list(root.glob("device_*/*.db")))
    assert hashes(root) == before


@pytest.mark.parametrize("change", ["bytes", "manifest", "different-root"])
@pytest.mark.parametrize("immutable", [False, True])
def test_resolved_dataset_cannot_authorize_changed_or_other_content(
    root, change, immutable, monkeypatch
):
    if immutable:
        monkeypatch.setenv("PT_SNAP_DATASET_CACHE", "immutable")
    resolved = dataset_resolver.DatasetResolver().inspect(root)
    assert resolved is not None
    export.inspect_owned_cache(root, _resolved=resolved)
    target = root
    if change == "bytes":
        execute(
            root / "device_0/slice_00000.db",
            "UPDATE memory_allocation_cache_v1_0 SET payload=X'9988'",
        )
    elif change == "manifest":
        (root / "manifest.json").write_text((root / "manifest.json").read_text() + "\n")
    else:
        target = root.parent / "another-dataset"
        shutil.copytree(root, target)
    before = hashes(target)
    with pytest.raises(ValueError):
        export.inspect_owned_cache(target, _resolved=resolved)
    assert target not in export._OWNED_CACHE
    assert hashes(target) == before


def test_matching_base_resolution_does_not_prove_owned_content(root, monkeypatch):
    manifest = read_manifest(root)
    first = next(iter(manifest["ptSnap"]["memberContent"]["members"].values()))
    first["tables"]["dictionary"]["sha256"] = "0" * 64
    write_manifest(root, manifest)
    resolved = dataset_resolver.DatasetResolver().inspect(root)
    assert resolved is not None
    validation, proof = spies(monkeypatch)
    with pytest.raises(ValueError):
        export.inspect_owned_cache(root, _resolved=resolved)
    assert validation.call_count == 0
    assert proof.call_count >= 1
    assert root not in export._OWNED_CACHE


@pytest.mark.parametrize("warm", [False, True])
def test_hardlinked_member_is_rejected_without_admission(root, warm):
    if warm:
        export.inspect_owned_cache(root)
    member = root / "device_0/slice_00000.db"
    alias = root.parent / "outside-hardlink.db"
    os.link(member, alias)
    before = hashes(root)
    with pytest.raises(ValueError):
        export.inspect_owned_cache(root)
    assert root not in export._OWNED_CACHE
    assert hashes(root) == before


def test_concurrent_callers_receive_independent_results(root):
    before = hashes(root)
    expected_version = read_manifest(root)["ptSnap"]["identity"]["exportContractVersion"]

    def inspect_and_mutate(index):
        result = export.inspect_owned_cache(root)
        version = result.identity["exportContractVersion"]
        result.identity["exportContractVersion"] = 100 + index
        return version

    with ThreadPoolExecutor(max_workers=4) as executor:
        versions = list(executor.map(inspect_and_mutate, range(8)))
    assert versions == [expected_version] * 8
    assert export.inspect_owned_cache(root).identity["exportContractVersion"] == expected_version
    assert hashes(root) == before


def test_concurrent_failed_inspections_never_seed_a_success(root):
    manifest = read_manifest(root)
    manifest["ptSnap"]["memberContent"]["version"] = 999
    write_manifest(root, manifest)
    before = hashes(root)

    def inspect_invalid(_):
        with pytest.raises(ValueError):
            export.inspect_owned_cache(root)

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(inspect_invalid, range(8)))
    assert root not in export._OWNED_CACHE
    with pytest.raises(ValueError):
        export.inspect_owned_cache(root)
    assert hashes(root) == before
