"""Original interface-facts converter for fixed msinsight 101f65b8 compatibility.

No Ascend implementation is copied (its source is Mulan PSL v2). Physical
schema/hash facts: blobs 1fe50a5136f85365db55f4632d58f3cf7090431e,
95612509ef990ac6b7034919dae4938cc6acf3ad and
ca421c7b33f3a0050df9e7a01e666f558801bc2f. See sharded-snapshotdb docs.
Only caller-owned finalized native staging is converted; existing caches are
never mutated, even under force. This is not GUI acceptance.
"""

from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
from collections import OrderedDict
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING

from .dataset_contract import (
    ACTION_NAMES,
    MANIFEST_SCHEMA_VERSION,
    MSINSIGHT_REVISION,
    TRACE_COLUMNS,
    DatasetContractError,
    DatasetManifest,
    _unique_object,
    parse_manifest,
    validate_dataset,
)
from .dataset_files import hash_file, require_readonly_member
from .dataset_import_backend import DatasetImportBackend
from .errors import ImportExecutionError
from .import_metadata_contract import metadata_from_mapping
from .models import ImportMetadata
from .msinsight_content_proof import (
    CONTENT_VERSION,
    compare_member_content,
    member_content,
    validate_member_content,
)
from .sharded_replay_service import ShardedReplayResult

if TYPE_CHECKING:
    from .dataset_resolver import ResolvedDataset


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


def convert_shards(result: ShardedReplayResult) -> None:
    """Preserve event/stream/lifecycle values, materialize inline ninth column.

    First validate all selected IDs/actions, without inventing event zero or
    coercing unsupported OOM. Block/reference tables are left byte-semantically
    intact; no foreign real events are copied into the slice window.
    """
    _validate_shards(result)
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
    contents: dict[str, object] = {}
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
            relative = item.file.relative_to(result.directory).as_posix()
            require_readonly_member(result.directory, item.file, immutable=True)
            before = hash_file(item.file)
            contents[relative] = member_content(item.file)
            require_readonly_member(result.directory, item.file, immutable=True)
            if hash_file(item.file) != before:
                raise ValueError("Compatible member changed while building proof")
            files[relative] = before
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
            "memberContent": {"version": CONTENT_VERSION, "members": contents},
        },
    }


@dataclass(frozen=True)
class CompatibleCache:
    manifest: DatasetManifest
    identity: dict[str, object]
    metadata: ImportMetadata
    omitted_devices: tuple[int, ...]


# No persisted receipt, live connection or stat-only reuse. Every hit is bracketed
# by current manifest/member byte hashes and transport/generation checks.
_OWNED_CACHE_LIMIT = 16
_OWNED_CACHE: OrderedDict[Path, tuple[str, CompatibleCache]] = OrderedDict()
_OWNED_CACHE_LOCK = RLock()


def _cache_inventory(target: Path) -> dict[str, tuple[int, ...]]:
    """Snapshot identity of the entire owned tree without following aliases."""
    if target.resolve() != target or target.is_symlink() or not target.is_dir():
        raise ValueError("Compatible cache must be a canonical directory")
    result = {}
    for path in (target, *target.rglob("*")):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError("Unrecognized files or aliases in compatible cache")
        stat = path.stat()
        if path.is_file() and stat.st_nlink != 1:
            raise ValueError("Compatible cache files must not have hard-link aliases")
        result[path.relative_to(target).as_posix()] = (
            stat.st_dev,
            stat.st_ino,
            stat.st_size,
            stat.st_mtime_ns,
            stat.st_ctime_ns,
            stat.st_mode,
            stat.st_nlink,
        )
    return result


def inspect_owned_cache(
    target: Path, *, _resolved: ResolvedDataset | None = None
) -> CompatibleCache:
    """Inspect complete ownership evidence, evicting any failed admission."""
    try:
        return _inspect_owned_cache(target, _resolved=_resolved)
    except BaseException:
        with _OWNED_CACHE_LOCK:
            _OWNED_CACHE.pop(target, None)
        raise


def _inspect_owned_cache(
    target: Path, *, _resolved: ResolvedDataset | None = None
) -> CompatibleCache:
    """Recognized identity plus byte or versioned base-content attestation.

    Stable cache-only changes can reuse new proofs. Legacy byte drift cannot be
    classified retrospectively. Bracketing detects changes, not a writer lock.
    """
    generation = _cache_inventory(target)
    manifest_path = target / "manifest.json"
    manifest_hash = hash_file(manifest_path)
    with manifest_path.open(encoding="utf-8") as file:
        data = json.load(file, object_pairs_hook=_unique_object)
    planned = parse_manifest(data)
    paths = {s.file: d.device_id for d in planned.devices for s in d.slices}
    expected = {".", "manifest.json", *paths, *(str(Path(p).parent) for p in paths)}
    if set(generation) != expected:
        raise ValueError("Unrecognized files or aliases in compatible cache")
    before = {}
    for relative in paths:
        require_readonly_member(target, target / relative, immutable=True)
        before[relative] = hash_file(target / relative)
    digest = hashlib.sha256(manifest_hash.encode("ascii"))
    for relative, content_hash in before.items():
        digest.update(relative.encode("utf-8"))
        digest.update(content_hash.encode("ascii"))
    fingerprint = digest.hexdigest()

    def require_unchanged() -> None:
        for relative in paths:
            require_readonly_member(target, target / relative, immutable=True)
            if hash_file(target / relative) != before[relative]:
                raise ValueError("Compatible member changed during inspection")
        if hash_file(manifest_path) != manifest_hash or _cache_inventory(target) != generation:
            raise ValueError("Compatible cache changed during inspection")

    # A resolver result proves only the P0 contract, never ownership. Bind it to
    # these current bytes before reusing that base validation; the remaining
    # identity, logical proof and metadata checks still run on a cold admission.
    if _resolved is not None and (
        _resolved.root != target
        or _resolved.fingerprint != fingerprint
        or _resolved.validation.manifest != planned
        or dict(_resolved.generation or ()) != generation
    ):
        raise ValueError("Compatible cache changed since dataset resolution")
    with _OWNED_CACHE_LOCK:
        cached = _OWNED_CACHE.get(target)
        if cached is not None and cached[0] == fingerprint:
            result = copy.deepcopy(cached[1])
            _OWNED_CACHE.move_to_end(target)
        else:
            result = None
            _OWNED_CACHE.pop(target, None)
    if result is not None:
        require_unchanged()
        return result
    validation = _resolved.validation if _resolved is not None else validate_dataset(target)
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
    if set(extension["members"]) != set(paths):
        raise ValueError("Incomplete member attestation")
    proofs = None
    if "memberContent" in extension:
        content = extension["memberContent"]
        if (
            not isinstance(content, dict)
            or set(content) != {"version", "members"}
            or type(content["version"]) is not int
            or content["version"] != CONTENT_VERSION
            or not isinstance(content["members"], dict)
            or set(content["members"]) != set(paths)
        ):
            raise ValueError("Unsupported or incomplete compatible base-content proof")
        proofs = content["members"]
        for proof in proofs.values():
            validate_member_content(proof)
    for relative, device in paths.items():
        member = target / relative
        if before[relative] != extension["members"][relative]:
            if proofs is None:
                raise ValueError(
                    "Compatible member hash changed; legacy integrity proof invalidated. "
                    "No prior base-content proof is available; base-data corruption is not established."
                )
            compare_member_content(member, proofs[relative], device)
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
    require_unchanged()
    result = CompatibleCache(validation.manifest, identity, metadata, tuple(omitted))
    admitted = copy.deepcopy(result)
    with _OWNED_CACHE_LOCK:
        _OWNED_CACHE[target] = (fingerprint, admitted)
        _OWNED_CACHE.move_to_end(target)
        while len(_OWNED_CACHE) > _OWNED_CACHE_LIMIT:
            _OWNED_CACHE.popitem(last=False)
    return result
