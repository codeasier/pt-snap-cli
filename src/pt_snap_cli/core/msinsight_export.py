"""Original interface-facts converter for fixed msinsight 101f65b8 compatibility.

No Ascend implementation is copied (its source is Mulan PSL v2). Physical
schema/hash facts: blobs 1fe50a5136f85365db55f4632d58f3cf7090431e,
95612509ef990ac6b7034919dae4938cc6acf3ad and
ca421c7b33f3a0050df9e7a01e666f558801bc2f. See sharded-snapshotdb docs.
Only caller-owned finalized native staging is converted; existing caches are
never mutated, even under force. This is not GUI acceptance.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .dataset_contract import (
    ACTION_NAMES,
    MANIFEST_SCHEMA_VERSION,
    MSINSIGHT_REVISION,
    TRACE_COLUMNS,
    DatasetContractError,
    DatasetManifest,
    parse_manifest,
    validate_dataset,
)
from .dataset_files import hash_file, readonly_member_uri, require_readonly_member
from .dataset_import_backend import DatasetImportBackend
from .errors import ImportExecutionError
from .import_metadata_contract import metadata_from_mapping
from .models import ImportMetadata
from .sharded_replay_service import ShardedReplayResult
from .snapshot_cache import parse_cache_manifest, seal_manifest, source_hashes, validate_cache

COMPATIBILITY_FORMAT = "compatibility-v1"
DEFAULT_CAPACITY = 500000
# Independent semantic versions, not the installed CLI version or GUI cacheHash.
EXPORT_VERSION = 2
REFERENCE_VERSION = 1


def salted_hash(source: Path) -> str:
    return source_hashes(source)[1]


def compatible_identity(source_hash: str, device: int | None, capacity: int) -> dict[str, object]:
    return {
        "sourceSha256": source_hash,
        "requestedDevice": device,
        "eventsPerSlice": capacity,
        "outputFormat": COMPATIBILITY_FORMAT,
        "manifestContractVersion": MANIFEST_SCHEMA_VERSION,
        "exportContractVersion": EXPORT_VERSION,
        "referenceContractVersion": REFERENCE_VERSION,
        "metadataSchemaVersion": 1,
        "importFormatVersion": 1,
        "targetRevision": MSINSIGHT_REVISION,
    }


class MsinsightImportBackend(DatasetImportBackend):
    """Use the proven exclusive/compensating publisher, never its replacement path."""

    @staticmethod
    def target_path(source: Path, output_dir: Path) -> Path:
        return output_dir / f"{source.name}.msinsight"

    @staticmethod
    def inspect_target(target: Path) -> None:
        if target.exists() or target.is_symlink():
            raise ImportExecutionError(
                "Compatible output already exists; preserved even under --force. Choose a new output directory."
            )
        return None


def _require_integer_primary_key(conn: sqlite3.Connection, trace: str) -> None:
    """Prove unique integer IDs before relying on count and range endpoints.

    The native writer uses a rowid alias, which enforces integer storage. SQLite's
    inline PRIMARY KEY DESC exception and WITHOUT ROWID tables instead have a
    primary-key index: retain support for these only after checking storage types.
    """
    kind = conn.execute("SELECT type FROM sqlite_master WHERE name=?", (trace,)).fetchone()
    primary_key = [row for row in conn.execute(f'PRAGMA table_info("{trace}")') if row[5]]
    if (
        kind != ("table",)
        or len(primary_key) != 1
        or primary_key[0][1] != "id"
        or primary_key[0][2].upper() != "INTEGER"
        or primary_key[0][5] != 1
    ):
        raise ValueError(f"{trace}.id must be the sole INTEGER PRIMARY KEY")
    if any(row[3] == "pk" for row in conn.execute(f'PRAGMA index_list("{trace}")')) and (
        conn.execute(f"SELECT 1 FROM {trace} WHERE typeof(id)!='integer' LIMIT 1").fetchone()
        is not None
    ):
        raise ValueError(f"{trace}.id INTEGER PRIMARY KEY must contain only integers")


def _validate_shards(result: ShardedReplayResult) -> None:
    """Validate every selected device before conversion without collecting IDs."""
    for device in sorted({s.device for s in result.slices}):
        next_expected = 0
        for item in (s for s in result.slices if s.device == device):
            require_readonly_member(result.directory, item.file)
            with closing(sqlite3.connect(item.file.as_uri() + "?mode=ro", uri=True)) as conn:
                trace = f"trace_entry_{device}"
                _require_integer_primary_key(conn, trace)
                count, low, high = conn.execute(
                    f'SELECT COUNT(*), MIN(id), MAX(id) FROM "{trace}" WHERE id>=0'
                ).fetchone()
                # With unique integer IDs, count and endpoints prove there are
                # no holes inside this shard. Checking each shard in order also
                # rejects overlaps/gaps that a device-wide aggregate can hide.
                if count and (low != next_expected or high != next_expected + count - 1):
                    raise DatasetContractError(
                        f"events[{next_expected}]",
                        "event_identity",
                        "compatibility requires original real IDs 0..N-1; do not silently renumber",
                    )
                next_expected += count
                if (
                    conn.execute(
                        f"SELECT id FROM {trace} WHERE typeof(action)!='integer' "
                        "OR action NOT BETWEEN 0 AND 7 OR action IS NULL LIMIT 1"
                    ).fetchone()
                    is not None
                ):
                    raise ValueError("msinsight compatibility does not support OOM/unknown actions")
        if not next_expected:
            raise DatasetContractError(
                "events", "empty", "empty/static-only devices cannot use compatibility v1"
            )


def _compact_compatible_block_ids(result: ShardedReplayResult) -> None:
    """Match Insight's continuous preexisting-block IDs without changing native shards."""
    for device in sorted({item.device for item in result.slices}):
        items = [item for item in result.slices if item.device == device]
        tokens: set[int] = set()
        for item in items:
            with closing(sqlite3.connect(item.file.as_uri() + "?mode=ro", uri=True)) as conn:
                tokens.update(
                    row[0] for row in conn.execute(f"SELECT id FROM block_{device} WHERE id<0")
                )
        if not tokens:
            continue
        ordered = sorted(tokens, reverse=True)
        floor = min(tokens) - len(tokens)
        # Move every key out of the final range before assigning compact IDs.
        phases = (
            [(floor - index, token) for index, token in enumerate(ordered, 1)],
            [(-index, floor - index) for index in range(1, len(ordered) + 1)],
        )
        for item in items:
            with closing(sqlite3.connect(item.file.as_uri() + "?mode=rw", uri=True)) as conn, conn:
                for updates in phases:
                    conn.executemany(f"UPDATE block_{device} SET id=? WHERE id=?", updates)
                    conn.executemany(
                        "UPDATE pt_snap_block_reference SET blockId=? WHERE blockId=?", updates
                    )


def convert_shards(result: ShardedReplayResult) -> None:
    """Preserve event/stream/lifecycle values, materialize inline ninth column.

    First validate all selected IDs/actions, without inventing event zero or
    coercing unsupported OOM. Negative block IDs and boundary IDs are normalized
    to Insight numbering; no foreign real events are copied into the slice window.
    """
    _validate_shards(result)
    _compact_compatible_block_ids(result)
    boundary_count = 0
    for item in sorted(result.slices, key=lambda item: (item.device, -item.index)):
        device = item.device
        trace = f"trace_entry_{device}"
        with closing(sqlite3.connect(item.file.as_uri() + "?mode=rw", uri=True)) as conn, conn:
            count = conn.execute(f"SELECT COUNT(*) FROM {trace} WHERE id<0").fetchone()[0]
            conn.execute(f"UPDATE {trace} SET id=id-? WHERE id<0", (boundary_count,))
            boundary_count += count
            # A missing stack reference must fail, not silently erase an event.
            if (
                conn.execute(
                    f"SELECT t.id FROM {trace} t LEFT JOIN callstack c ON c.id=t.callstackId "
                    "WHERE c.id IS NULL LIMIT 1"
                ).fetchone()
                is not None
            ):
                raise ValueError("Missing finalized callstack reference")
            conn.execute(f"ALTER TABLE {trace} RENAME TO pt_snap_native_trace")
            columns = ",".join(
                f'"{name}" {kind}' + (" PRIMARY KEY" if name == "id" else "")
                for name, kind in TRACE_COLUMNS
            )
            conn.execute(f"CREATE TABLE {trace} ({columns})")
            conn.execute(
                f"INSERT INTO {trace} SELECT t.id,t.action,t.address,t.size,t.stream,"
                "t.allocated,t.active,t.reserved,c.callstack FROM pt_snap_native_trace t "
                "JOIN callstack c ON c.id=t.callstackId"
            )
            conn.execute("DROP TABLE pt_snap_native_trace")
            conn.execute("DROP TABLE callstack")
            conn.execute('DELETE FROM dictionary WHERE "table"=? AND "column"=?', (trace, "action"))
            conn.executemany(
                "INSERT INTO dictionary VALUES (?,?,?,?)",
                [(trace, "action", str(key), name) for key, name in enumerate(ACTION_NAMES)],
            )
            for metric in ("allocated", "active", "reserved"):
                conn.execute(f"CREATE INDEX {trace}_{metric} ON {trace} ({metric})")


def build_compatible_manifest(
    result: ShardedReplayResult,
    metadata: ImportMetadata,
    source: Path,
    capacity: int,
    cache_hash: str,
) -> dict[str, object]:
    devices: dict[str, object] = {}
    files: dict[str, str] = {}
    for device in sorted({s.device for s in result.slices}):
        slices = [s for s in result.slices if s.device == device]
        devices[str(device)] = {
            "eventCount": sum(s.end_position - s.start_position + 1 for s in slices),
            "sliceCount": len(slices),
            "readySlices": list(range(len(slices))),
            "slices": [
                {
                    "index": s.index,
                    "startEventId": s.start_event_id,
                    "endEventId": s.end_event_id,
                    "file": s.file.relative_to(result.directory).as_posix(),
                    "ready": True,
                }
                for s in slices
            ],
        }
    manifest: dict[str, Any] = {
        "schemaVersion": MANIFEST_SCHEMA_VERSION,
        "status": "complete",
        "sourceFile": str(source.resolve()),
        "cacheHash": cache_hash,
        "eventsPerSlice": capacity,
        "devices": devices,
        "ptSnap": {
            "identity": compatible_identity(
                metadata.source_sha256, metadata.requested_device, capacity
            ),
            "metadata": asdict(metadata),
            "omittedDevices": list(result.omitted_devices),
            "members": files,
        },
    }
    seal_manifest(result.directory, manifest, metadata.requested_device)
    manifest["ptSnap"]["members"] = manifest["parserCache"]["members"]
    manifest["ptSnap"]["memberHashKind"] = "parser-v1"
    return manifest


@dataclass(frozen=True)
class CompatibleCache:
    manifest: DatasetManifest
    identity: dict[str, object]
    metadata: ImportMetadata
    omitted_devices: tuple[int, ...]


def inspect_owned_cache(target: Path) -> CompatibleCache:
    """Whole valid recognized identity only; salted hash alone is never ownership.

    Base tables are attested logically. Consumer-owned tables and indexes may
    change without invalidating parser data. Legacy exports retain byte checks.
    """
    data = parse_cache_manifest((target / "manifest.json").read_bytes())
    extension = data.get("ptSnap")
    if not isinstance(extension, dict):
        raise ValueError("manifest.ptSnap: expected object")
    identity = extension.get("identity")
    if not isinstance(identity, dict):
        raise ValueError("manifest.ptSnap.identity: expected object")
    for key in ("metadata", "members"):
        if not isinstance(extension.get(key), dict):
            raise ValueError(f"manifest.ptSnap.{key}: expected object")
    if not isinstance(extension.get("omittedDevices"), list):
        raise ValueError("manifest.ptSnap.omittedDevices: expected array")
    version = identity.get("exportContractVersion")
    if type(version) is int and version < EXPORT_VERSION:
        raise ValueError(
            f"Legacy export contract v{version}; choose a new --output-dir to re-export as v{EXPORT_VERSION}"
        )
    # Sealed base rows are already fully scanned by validate_cache below. Avoid
    # a second expensive callstack/row walk and keep live WAL reads transactional.
    manifest = parse_manifest(data)
    if data.get("ptSnap", {}).get("memberHashKind") != "parser-v1":
        manifest = validate_dataset(target).manifest
    extension = data["ptSnap"]
    metadata = metadata_from_mapping(extension["metadata"])
    identity = extension["identity"]
    expected_identity = compatible_identity(
        metadata.source_sha256, metadata.requested_device, manifest.events_per_slice
    )
    if identity != expected_identity or any(
        type(identity[key]) is not type(value) for key, value in expected_identity.items()
    ):
        raise ValueError("Unsupported or inconsistent pt-snap compatibility identity")
    if (
        metadata.importer_name != "pt-snap-cli"
        or metadata.import_format_version != 1
        or metadata.metadata_schema_version != 1
    ):
        raise ValueError("Metadata must match physical v1 layout")
    paths = {s.file for d in manifest.devices for s in d.slices}
    if any((target / (relative + "-journal")).exists() for relative in paths):
        raise ValueError(
            "Snapshot member has a rollback journal; a writer or recovery may be active, retry later"
        )
    if set(extension["members"]) != paths:
        raise ValueError("Incomplete member attestation")
    expected = {"manifest.json", "parse.log", *paths, *(str(Path(p).parent) for p in paths)}
    expected.update(relative + suffix for relative in paths for suffix in ("-wal", "-shm"))
    actual = {p.relative_to(target).as_posix() for p in target.rglob("*")}
    if not actual <= expected or any(p.is_symlink() for p in target.rglob("*")):
        raise ValueError("Unrecognized files or aliases in compatible cache")
    logical_members = None
    if extension.get("memberHashKind") == "parser-v1":
        checked = validate_cache(target, data["cacheHash"], metadata.requested_device)
        if checked != data:
            raise ValueError("Compatible manifest changed during inspection")
        # validate_cache checks the producer seal even without parserCache.
        logical_members = checked["ptSnap"]["members"]
    elif "memberHashKind" in extension:
        raise ValueError("Unsupported member hash contract")
    for relative in paths:
        member = target / relative
        digest = logical_members[relative] if logical_members is not None else hash_file(member)
        if digest != extension["members"][relative]:
            raise ValueError("Compatible member hash changed")
        require_readonly_member(target, member, immutable=True)
        with closing(sqlite3.connect(readonly_member_uri(member), uri=True)) as conn:
            conn.row_factory = sqlite3.Row
            if (
                conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='pt_snap_metadata'"
                ).fetchone()
                is None
            ):
                raise ValueError(f"{relative}.pt_snap_metadata: required metadata table is missing")
            rows = conn.execute("SELECT * FROM pt_snap_metadata").fetchall()
            if (
                len(rows) != 1
                or rows[0]["id"] != 1
                or metadata_from_mapping(dict(rows[0])) != metadata
            ):
                raise ValueError("Member metadata disagrees with identity")
    omitted = extension["omittedDevices"]
    devices = {d.device_id for d in manifest.devices}
    if (
        not isinstance(omitted, list)
        or any(type(v) is not int or v < 0 or v in devices for v in omitted)
        or len(set(omitted)) != len(omitted)
    ):
        raise ValueError("Invalid omitted device inventory")
    if metadata.requested_device is not None and devices != {metadata.requested_device}:
        raise ValueError("Device selection disagrees with identity")
    if Path(manifest.source_file).name != metadata.source_name:
        raise ValueError("Source path disagrees with metadata")
    return CompatibleCache(manifest, identity, metadata, tuple(omitted))
