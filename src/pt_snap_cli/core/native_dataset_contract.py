"""Original published pt-snap native-v2 protocol; NOT compatibility-v1/msinsight.

Counts/capacity use original positions per device. IDs stay sparse and original.
Only closed, finalized artifacts are accepted; unknown extensions grant no capabilities.
"""

from __future__ import annotations

import json
import re
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import cast

from .dataset_contract import (
    ACTION_NAMES,
    BLOCK_COLUMNS,
    BLOCK_STATES,
    DICTIONARY_COLUMNS,
    TRACE_COLUMNS,
    DatasetContractError,
    DatasetManifest,
    DatasetValidation,
    DeviceRecord,
    QueryScope,
    SliceRecord,
    _array,
    _integer,
    _need,
    _object,
    _safe_file,
    _schema,
    _text,
    _unique_object,
)
from .dataset_files import hash_file as _hash_file
from .dataset_files import require_readonly_member as _require_readonly_member
from .import_metadata_contract import metadata_from_mapping
from .models import ImportMetadata
from .sharded_replay_service import ShardedReplayResult

NATIVE_FORMAT = "pt-snap-native-v2"
NATIVE_MANIFEST_VERSION = 1
# Semantic contracts, deliberately independent of the installed CLI __version__.
NATIVE_FORMAT_VERSION = 1
NATIVE_IMPORT_VERSION = 1
NATIVE_EXTENSION_VERSION = 1


@dataclass(frozen=True)
class NativeSlice(SliceRecord):
    start_position: int
    end_position: int
    sha256: str


@dataclass(frozen=True)
class NativeManifest(DatasetManifest):
    identity: dict[str, object]
    metadata: ImportMetadata
    omitted_devices: tuple[int, ...]


def cache_identity(source_sha256: str, device: int | None, capacity: int) -> dict[str, object]:
    return {
        "sourceSha256": source_sha256,
        "requestedDevice": device,
        "eventsPerSlice": capacity,
        "outputFormat": NATIVE_FORMAT,
        "manifestContractVersion": NATIVE_MANIFEST_VERSION,
        "formatContractVersion": NATIVE_FORMAT_VERSION,
        "importContractVersion": NATIVE_IMPORT_VERSION,
        "extensionContractVersion": NATIVE_EXTENSION_VERSION,
        "metadataSchemaVersion": 1,
        "importFormatVersion": 2,
    }


def _digest(value: object, loc: str) -> str:
    result = _text(value, loc)
    _need(re.fullmatch(r"[0-9a-f]{64}", result) is not None, loc, "hash", "expected SHA256")
    return result


def parse_native_manifest(value: object) -> NativeManifest:

    data = _object(value, "manifest")
    _need(data.get("format") == NATIVE_FORMAT, "format", "format", "unsupported native format")
    version = _integer(data.get("schemaVersion"), "schemaVersion", minimum=1)
    _need(
        version == NATIVE_MANIFEST_VERSION,
        "schemaVersion",
        "version",
        "unsupported native manifest",
    )
    _need(
        data.get("status") == "complete", "status", "building", "complete native dataset required"
    )
    source = _text(data.get("sourceFile"), "sourceFile")
    identity = _object(data.get("identity"), "identity")
    _digest(identity.get("sourceSha256"), "identity.sourceSha256")
    requested = identity.get("requestedDevice")
    if requested is not None:
        _integer(requested, "identity.requestedDevice", maximum=2**31 - 1)
    capacity = _integer(identity.get("eventsPerSlice"), "identity.eventsPerSlice", minimum=1)
    _need(
        identity.get("outputFormat") == NATIVE_FORMAT,
        "identity",
        "format",
        "format identity mismatch",
    )
    for key in (
        "manifestContractVersion",
        "formatContractVersion",
        "importContractVersion",
        "extensionContractVersion",
        "metadataSchemaVersion",
        "importFormatVersion",
    ):
        _integer(identity.get(key), "identity." + key, minimum=1)
    _need(
        set(identity) == set(cache_identity("", None, 1)),
        "identity",
        "fields",
        "identity fields differ",
    )
    try:
        metadata = metadata_from_mapping(_object(data.get("metadata"), "metadata"))
    except (KeyError, TypeError, ValueError) as exc:
        raise DatasetContractError("metadata", "metadata", str(exc)) from exc
    _need(
        (
            metadata.source_sha256,
            metadata.requested_device,
            metadata.metadata_schema_version,
            metadata.import_format_version,
        )
        == (
            identity["sourceSha256"],
            requested,
            identity["metadataSchemaVersion"],
            identity["importFormatVersion"],
        ),
        "metadata",
        "identity",
        "metadata disagrees with dataset identity",
    )
    _need(
        source == metadata.source_name,
        "sourceFile",
        "metadata",
        "source name disagrees with metadata",
    )
    omitted = tuple(
        _integer(v, "omittedDevices", maximum=2**31 - 1)
        for v in _array(data.get("omittedDevices"), "omittedDevices")
    )
    _need(len(set(omitted)) == len(omitted), "omittedDevices", "duplicate", "duplicate device")
    devices: list[DeviceRecord] = []
    for key, raw in _object(data.get("devices"), "devices").items():
        loc = f"devices.{key}"
        _need(
            isinstance(key, str) and re.fullmatch(r"0|[1-9][0-9]*", key) is not None,
            loc,
            "device",
            "noncanonical device",
        )
        device_id = _integer(int(key), loc, maximum=2**31 - 1)
        device = _object(raw, loc)
        count = _integer(device.get("eventCount"), loc + ".eventCount", minimum=1)
        records = _array(device.get("slices"), loc + ".slices")
        _need(
            bool(records)
            and device.get("sliceCount") == len(records)
            and type(device.get("sliceCount")) is int,
            loc,
            "count",
            "invalid sliceCount",
        )
        ready = tuple(
            _integer(v, loc + ".readySlices")
            for v in _array(device.get("readySlices"), loc + ".readySlices")
        )
        _need(
            ready == tuple(range(len(records))),
            loc,
            "readiness",
            "all slices must be ready in order",
        )
        slices: list[SliceRecord] = []
        position, last_id = 0, -1
        for index, raw_slice in enumerate(records):
            item = _object(raw_slice, loc)
            _need(
                type(item.get("index")) is int
                and item["index"] == index
                and item.get("ready") is True,
                loc,
                "index",
                "slice index/readiness mismatch",
            )
            start = _integer(item.get("startPosition"), loc + ".startPosition")
            end = _integer(item.get("endPosition"), loc + ".endPosition", minimum=start)
            _need(
                start == position and end - start + 1 <= capacity,
                loc,
                "coverage",
                "invalid positional coverage/capacity",
            )
            # All but the last shard must be full; no omitted positions are allowed.
            _need(
                index == len(records) - 1 or end - start + 1 == capacity,
                loc,
                "capacity",
                "nonfinal slice is not full",
            )
            low = _integer(item.get("startEventId"), loc + ".startEventId", minimum=last_id + 1)
            high = _integer(item.get("endEventId"), loc + ".endEventId", minimum=low)
            file = _text(item.get("file"), loc + ".file")
            _need(
                file == f"device_{device_id}/slice_{index:05d}.db",
                loc,
                "path",
                "noncanonical member",
            )
            slices.append(
                NativeSlice(
                    index, low, high, file, True, start, end, _digest(item.get("sha256"), loc)
                )
            )
            position, last_id = end + 1, high
        _need(position == count, loc, "coverage", "positions do not cover eventCount")
        devices.append(DeviceRecord(device_id, count, ready, tuple(slices)))
    _need(bool(devices), "devices", "empty", "event-bearing device required")
    selected = {d.device_id for d in devices}
    _need(
        not selected.intersection(omitted), "omittedDevices", "device", "selected device is omitted"
    )
    _need(
        requested is None or selected == {requested},
        "identity",
        "device",
        "requested device mismatch",
    )
    return NativeManifest(
        version, "complete", source, "", capacity, tuple(devices), identity, metadata, omitted
    )


def read_native_manifest(root: Path) -> NativeManifest:
    try:
        with _safe_file(root, "manifest.json").open(encoding="utf-8") as file:
            return parse_native_manifest(json.load(file, object_pairs_hook=_unique_object))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DatasetContractError("manifest.json", "read", str(exc)) from exc


def require_native_members(root: Path, manifest: NativeManifest) -> None:
    """Ownership recognition before any replacement: never adopt unknown files/dirs."""
    _need(
        root.resolve() == root and not root.is_symlink(),
        "dataset",
        "path",
        "noncanonical directory",
    )
    expected = {"manifest.json", *(f"device_{d.device_id}" for d in manifest.devices)}
    _need(
        {p.name for p in root.iterdir()} == expected,
        "dataset",
        "members",
        "unexpected/missing dataset member",
    )
    for device in manifest.devices:
        directory = root / f"device_{device.device_id}"
        _need(
            not directory.is_symlink() and directory.is_dir(),
            str(directory),
            "path",
            "unsafe device directory",
        )
        _need(
            {p.name for p in directory.iterdir()} == {Path(s.file).name for s in device.slices},
            str(directory),
            "members",
            "unexpected/missing shard",
        )
        for item in device.slices:
            _safe_file(root, item.file)


def validate_native_dataset(root: Path, manifest: NativeManifest) -> DatasetValidation:

    require_native_members(root, manifest)
    expected_identity = cache_identity(
        manifest.metadata.source_sha256,
        manifest.metadata.requested_device,
        manifest.events_per_slice,
    )
    _need(
        manifest.identity == expected_identity,
        "identity",
        "version",
        "unsupported native semantic contract",
    )
    # Check EVERY member before the FIRST SQLite open. No WAL/sidecars/repair.
    for device in manifest.devices:
        for raw in device.slices:
            item = cast(NativeSlice, raw)
            path = root / item.file
            _require_readonly_member(root, path)
            _need(_hash_file(path) == item.sha256, item.file, "hash", "member content changed")
    boundaries = 0
    for device in manifest.devices:
        ids: set[int] = set()
        lifetimes: dict[int, tuple[object, ...]] = {}
        references: list[tuple[int, int]] = []
        for raw in device.slices:
            item = cast(NativeSlice, raw)
            path = root / item.file
            try:
                with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as conn:
                    conn.execute("PRAGMA query_only=ON")
                    _need(
                        conn.execute("PRAGMA quick_check").fetchall() == [("ok",)],
                        item.file,
                        "sqlite",
                        "integrity check failed",
                    )
                    trace, block = f"trace_entry_{device.device_id}", f"block_{device.device_id}"
                    names = {
                        row[0]
                        for row in conn.execute(
                            "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
                        )
                    }
                    _need(
                        {n for n in names if n.lower().startswith(("trace_entry_", "block_"))}
                        == {trace, block},
                        item.file,
                        "device_tables",
                        "wrong device/table set",
                    )
                    for table, columns in (
                        (trace, TRACE_COLUMNS[:-1] + (("callstackId", "INTEGER"),)),
                        (block, BLOCK_COLUMNS),
                        ("dictionary", DICTIONARY_COLUMNS),
                        ("callstack", (("id", "INTEGER"), ("callstack", "TEXT"))),
                    ):
                        _schema(conn, table, columns, item.file)
                    _need(
                        conn.execute(
                            "SELECT type FROM sqlite_master WHERE name='pt_snap_block_reference'"
                        ).fetchone()
                        == ("table",),
                        item.file,
                        "extension",
                        "finalized reference table required",
                    )
                    reference_columns = conn.execute(
                        "PRAGMA table_info(pt_snap_block_reference)"
                    ).fetchall()
                    _need(
                        tuple((r[1], r[2].upper(), r[5]) for r in reference_columns)
                        == (
                            ("blockId", "INTEGER", 1),
                            ("stream", "INTEGER", 0),
                            ("allocCallstack", "TEXT", 0),
                            ("freeCallstack", "TEXT", 0),
                        ),
                        item.file,
                        "extension",
                        "invalid reference schema",
                    )
                    for table, column, values in (
                        (trace, "action", tuple(enumerate((*ACTION_NAMES, "oom")))),
                        (block, "state", BLOCK_STATES),
                    ):
                        rows = conn.execute(
                            'SELECT "key","value" FROM dictionary WHERE "table"=? AND "column"=?',
                            (table, column),
                        ).fetchall()
                        expected = {(str(k), v) for k, v in values}
                        _need(
                            len(rows) == len(expected) and set(rows) == expected,
                            item.file,
                            "dictionary",
                            "invalid native dictionary",
                        )
                    real = [
                        r[0]
                        for r in conn.execute(f'SELECT id FROM "{trace}" WHERE id>=0 ORDER BY id')
                    ]
                    _need(
                        len(real) == item.end_position - item.start_position + 1
                        and (real[0], real[-1]) == (item.start_event_id, item.end_event_id)
                        and not ids.intersection(real),
                        item.file,
                        "event_identity",
                        "real IDs/count differ from positions/ranges",
                    )
                    ids.update(real)
                    numeric = " OR ".join(
                        f"typeof({name})!='integer'" for name, _ in TRACE_COLUMNS[:-1]
                    )
                    invalid = conn.execute(
                        f"SELECT id FROM \"{trace}\" WHERE {numeric} OR action NOT BETWEEN 0 AND 8 OR (id<0 AND action NOT IN (0,2)) OR size<0 OR allocated<0 OR active<0 OR reserved<0 OR typeof(callstackId)!='integer' OR callstackId NOT IN (SELECT id FROM callstack) LIMIT 1"
                    ).fetchone()
                    _need(
                        invalid is None,
                        item.file,
                        "event_values",
                        "invalid native event/scalar/callstack",
                    )
                    _need(
                        conn.execute(
                            "SELECT id FROM callstack WHERE typeof(callstack) NOT IN ('text','null') LIMIT 1"
                        ).fetchone()
                        is None,
                        item.file,
                        "callstack",
                        "invalid text stack",
                    )
                    boundaries += conn.execute(
                        f'SELECT COUNT(*) FROM "{trace}" WHERE id<0'
                    ).fetchone()[0]
                    stacks = {
                        r[0]: r[1:] for r in conn.execute("SELECT * FROM pt_snap_block_reference")
                    }
                    blocks = conn.execute(f'SELECT * FROM "{block}"').fetchall()
                    _need(
                        set(stacks) == {r[0] for r in blocks},
                        item.file,
                        "extension",
                        "reference/block membership differs",
                    )
                    for row in blocks:
                        bid, address, size, requested, state, alloc, free = row
                        _need(
                            all(type(v) is int for v in row)
                            and state in (-1, 0, 1)
                            and size >= 0
                            and 0 <= requested <= size
                            and ((alloc == -1 and bid < 0) or (alloc >= 0 and bid == alloc))
                            and (free == -1 or free >= 0 and (alloc == -1 or free >= alloc)),
                            item.file,
                            "block_identity",
                            "unfinalized/invalid block",
                        )
                        ref = stacks[bid]
                        _need(
                            type(ref[0]) is int
                            and all(v is None or isinstance(v, str) for v in ref[1:]),
                            item.file,
                            "extension",
                            "invalid reference values",
                        )
                        signature = (address, size, requested, alloc, free, *ref)
                        _need(
                            bid not in lifetimes or lifetimes[bid] == signature,
                            item.file,
                            "block_identity",
                            "conflicting finalized identity/reference",
                        )
                        lifetimes[bid] = signature
                        references.append((alloc, free))
            except sqlite3.DatabaseError as exc:
                raise DatasetContractError(item.file, "sqlite", str(exc)) from exc
            try:
                with closing(
                    sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
                ) as metadata_conn:
                    metadata_conn.row_factory = sqlite3.Row
                    _need(
                        metadata_conn.execute(
                            "SELECT type FROM sqlite_master WHERE name='pt_snap_metadata'"
                        ).fetchone()[0]
                        == "table",
                        item.file,
                        "metadata",
                        "metadata must be an actual table",
                    )
                    rows = metadata_conn.execute("SELECT * FROM pt_snap_metadata").fetchall()
                    _need(
                        len(rows) == 1
                        and rows[0]["id"] == 1
                        and set(rows[0].keys()) == {"id", *asdict(manifest.metadata)},
                        item.file,
                        "metadata",
                        "invalid metadata row/schema",
                    )
                    metadata = metadata_from_mapping(dict(rows[0]))
                    _need(
                        metadata == manifest.metadata,
                        item.file,
                        "metadata",
                        "member metadata differs from manifest",
                    )
            except (sqlite3.DatabaseError, KeyError, TypeError, ValueError) as exc:
                raise DatasetContractError(item.file, "metadata", str(exc)) from exc
            _require_readonly_member(root, path)
            _need(
                _hash_file(path) == item.sha256,
                item.file,
                "hash",
                "member changed during validation",
            )
        _need(
            len(ids) == device.event_count
            and all(v == -1 or v in ids for pair in references for v in pair),
            "devices",
            "event_identity",
            "count/lifetime references not in original device scope",
        )
    return DatasetValidation(manifest, sum(d.event_count for d in manifest.devices), boundaries)


def validate_native_scope(scope: QueryScope, manifest: NativeManifest) -> None:
    if scope.kind == "event_range":
        device = next((d for d in manifest.devices if d.device_id == scope.device_id), None)
        _need(
            type(scope.device_id) is int and device is not None, "scope", "device", "unknown device"
        )
        assert device is not None
        _need(scope.slice_index is None, "scope", "selector", "unexpected slice selector")
        start = _integer(
            scope.start_event_id,
            "scope.start_event_id",
            minimum=device.slices[0].start_event_id,
            maximum=device.slices[-1].end_event_id,
        )
        _integer(
            scope.end_event_id,
            "scope.end_event_id",
            minimum=start,
            maximum=device.slices[-1].end_event_id,
        )
    else:
        scope.validate(manifest)


def build_native_manifest(
    result: ShardedReplayResult, metadata: ImportMetadata, capacity: int
) -> dict[str, object]:

    devices: dict[str, object] = {}
    for device in sorted({item.device for item in result.slices}):
        slices = [s for s in result.slices if s.device == device]
        devices[str(device)] = {
            "eventCount": sum(s.end_position - s.start_position + 1 for s in slices),
            "sliceCount": len(slices),
            "readySlices": list(range(len(slices))),
            "slices": [
                {
                    "index": s.index,
                    "startPosition": s.start_position,
                    "endPosition": s.end_position,
                    "startEventId": s.start_event_id,
                    "endEventId": s.end_event_id,
                    "file": s.file.relative_to(result.directory).as_posix(),
                    "ready": True,
                    "sha256": _hash_file(s.file),
                }
                for s in slices
            ],
        }
    return {
        "format": NATIVE_FORMAT,
        "schemaVersion": NATIVE_MANIFEST_VERSION,
        "status": "complete",
        "sourceFile": metadata.source_name,
        "identity": cache_identity(metadata.source_sha256, metadata.requested_device, capacity),
        "metadata": asdict(metadata),
        "omittedDevices": list(result.omitted_devices),
        "devices": devices,
    }
