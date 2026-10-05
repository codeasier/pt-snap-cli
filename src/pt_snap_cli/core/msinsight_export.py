"""Original interface-facts converter for fixed msinsight 101f65b8 compatibility.

No Ascend implementation is copied (its source is Mulan PSL v2). Physical
schema/hash facts: blobs 1fe50a5136f85365db55f4632d58f3cf7090431e,
95612509ef990ac6b7034919dae4938cc6acf3ad and
ca421c7b33f3a0050df9e7a01e666f558801bc2f. See sharded-snapshotdb docs.
Only caller-owned finalized native staging is converted; existing caches are
never mutated, even under force. This is not GUI acceptance.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path

from .dataset_contract import (
    ACTION_NAMES,
    MANIFEST_SCHEMA_VERSION,
    MSINSIGHT_REVISION,
    TRACE_COLUMNS,
    DatasetManifest,
    _unique_object,
    validate_dataset,
    validate_event_ids,
)
from .dataset_files import hash_file, require_readonly_member
from .dataset_import_backend import DatasetImportBackend
from .errors import ImportExecutionError
from .import_metadata_contract import metadata_from_mapping
from .models import ImportMetadata
from .sharded_replay_service import ShardedReplayResult

COMPATIBILITY_FORMAT = "compatibility-v1"
DEFAULT_CAPACITY = 500000
SALT = b"mem_snapshot_parser_v2"
# Independent semantic versions, not the installed CLI version or GUI cacheHash.
EXPORT_VERSION = 1
REFERENCE_VERSION = 1


def salted_hash(source: Path) -> str:
    digest = hashlib.sha256(SALT)
    with source.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def convert_shards(result: ShardedReplayResult) -> None:
    """Preserve event/stream/lifecycle values, materialize inline ninth column.

    First validate all selected IDs/actions, without inventing event zero or
    coercing unsupported OOM. Block/reference tables are left byte-semantically
    intact; no foreign real events are copied into the slice window.
    """
    for device in sorted({s.device for s in result.slices}):
        ids: list[int] = []
        for item in (s for s in result.slices if s.device == device):
            require_readonly_member(result.directory, item.file)
            with closing(sqlite3.connect(item.file.as_uri() + "?mode=ro", uri=True)) as conn:
                ids.extend(
                    row[0]
                    for row in conn.execute(
                        f"SELECT id FROM trace_entry_{device} WHERE id>=0 ORDER BY id"
                    )
                )
                if (
                    conn.execute(
                        f"SELECT id FROM trace_entry_{device} WHERE typeof(action)!='integer' "
                        "OR action NOT BETWEEN 0 AND 7 OR action IS NULL LIMIT 1"
                    ).fetchone()
                    is not None
                ):
                    raise ValueError("msinsight compatibility does not support OOM/unknown actions")
        validate_event_ids(ids)
    for item in result.slices:
        device = item.device
        trace = f"trace_entry_{device}"
        with closing(sqlite3.connect(item.file.as_uri() + "?mode=rw", uri=True)) as conn, conn:
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
        for item in slices:
            files[item.file.relative_to(result.directory).as_posix()] = hash_file(item.file)
    return {
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


@dataclass(frozen=True)
class CompatibleCache:
    manifest: DatasetManifest
    identity: dict[str, object]
    metadata: ImportMetadata
    omitted_devices: tuple[int, ...]


def inspect_owned_cache(target: Path) -> CompatibleCache:
    """Whole valid recognized identity only; salted hash alone is never ownership.

    Reject unexpected files/aliases rather than adopt them. GUI may change
    derived tables: that invalidates pt-snap's immutable cache attestation, and
    requires a new output, never repair or force-replacement.
    """
    validation = validate_dataset(target)
    with (target / "manifest.json").open(encoding="utf-8") as file:
        data = json.load(file, object_pairs_hook=_unique_object)
    extension = data["ptSnap"]
    metadata = metadata_from_mapping(extension["metadata"])
    identity = extension["identity"]
    expected_identity = compatible_identity(
        metadata.source_sha256, metadata.requested_device, validation.manifest.events_per_slice
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
    paths = {s.file for d in validation.manifest.devices for s in d.slices}
    if set(extension["members"]) != paths:
        raise ValueError("Incomplete member attestation")
    expected = {"manifest.json", *paths, *(str(Path(p).parent) for p in paths)}
    actual = {p.relative_to(target).as_posix() for p in target.rglob("*")}
    if actual != expected or any(p.is_symlink() for p in target.rglob("*")):
        raise ValueError("Unrecognized files or aliases in compatible cache")
    for relative in paths:
        member = target / relative
        if hash_file(member) != extension["members"][relative]:
            raise ValueError("Compatible member hash changed")
        with closing(sqlite3.connect(member.as_uri() + "?mode=ro&immutable=1", uri=True)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM pt_snap_metadata").fetchall()
            if (
                len(rows) != 1
                or rows[0]["id"] != 1
                or metadata_from_mapping(dict(rows[0])) != metadata
            ):
                raise ValueError("Member metadata disagrees with identity")
    omitted = extension["omittedDevices"]
    devices = {d.device_id for d in validation.manifest.devices}
    if (
        not isinstance(omitted, list)
        or any(type(v) is not int or v < 0 or v in devices for v in omitted)
        or len(set(omitted)) != len(omitted)
    ):
        raise ValueError("Invalid omitted device inventory")
    if metadata.requested_device is not None and devices != {metadata.requested_device}:
        raise ValueError("Device selection disagrees with identity")
    if Path(validation.manifest.source_file).name != metadata.source_name:
        raise ValueError("Source path disagrees with metadata")
    return CompatibleCache(validation.manifest, identity, metadata, tuple(omitted))
