"""Resolve finalized compatibility datasets above the single-DB Context layer.

Original local reader of the P0 contract; no pickle, migration or producer code.
Native-v2 private replay staging is not a dataset until the native publisher closes,
attests and validates its complete versioned manifest.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from threading import RLock

from pt_snap_cli.core.dataset_contract import (
    DatasetContractError,
    DatasetManifest,
    DatasetValidation,
    DeviceRecord,
    QueryScope,
    _unique_object,
    parse_manifest,
    validate_dataset,
)
from pt_snap_cli.core.dataset_files import hash_file as _hash_file
from pt_snap_cli.core.dataset_files import require_readonly_member as _require_readonly_member
from pt_snap_cli.core.dataset_support import DATASET_SUPPORT
from pt_snap_cli.core.errors import DatabaseSchemaError, InvalidDeviceError, InvalidParameterError
from pt_snap_cli.core.native_dataset_contract import (
    NATIVE_FORMAT,
    NativeManifest,
    NativeSlice,
    parse_native_manifest,
    require_native_members,
    validate_native_dataset,
    validate_native_scope,
)
from pt_snap_cli.core.validation_budget import ValidationBudget, check_budget, checked_rows

_FileStamp = tuple[int, int, int, int, int, int, int]
_Generation = tuple[tuple[str, _FileStamp], ...]


@dataclass(frozen=True)
class ResolvedDataset:
    root: Path
    validation: DatasetValidation
    fingerprint: str
    ordered_frames_version: int | None = None
    generation: _Generation | None = None

    def require_unchanged(self, budget: ValidationBudget | None = None) -> None:
        """Guard a reused report/query resolution without repeating full validation."""
        if _root(self.root) != self.root:
            raise DatabaseSchemaError("Dataset path changed during operation; retry.")
        try:
            current = _generation(self.root, self.validation.manifest, budget)
            if self.generation is None or current != self.generation:
                raise DatabaseSchemaError("Dataset members changed during operation; retry.")
            if not _cacheable(current):
                if (
                    _content_fingerprint(self.root, self.validation.manifest, budget)
                    != self.fingerprint
                    or _generation(self.root, self.validation.manifest, budget) != current
                ):
                    raise DatabaseSchemaError("Dataset content changed during operation; retry.")
        except (DatasetContractError, OSError) as exc:
            raise DatabaseSchemaError(f"Dataset changed during operation: {exc}") from exc

    @property
    def device_ids(self) -> list[int]:
        return sorted(item.device_id for item in self.validation.manifest.devices)

    @property
    def callstack_layout(self) -> str:
        return "v2" if isinstance(self.validation.manifest, NativeManifest) else "v1"

    @property
    def callstack_layout_error(self) -> None:
        return None

    def device(self, device_id: int | None = None) -> DeviceRecord:
        selected = self.device_ids[0] if device_id is None else device_id
        for device in self.validation.manifest.devices:
            if type(selected) is int and device.device_id == selected:
                return device
        raise InvalidDeviceError(f"Device {selected} not found. Available: {self.device_ids}")

    def paths(self, scope: QueryScope) -> tuple[Path, ...]:
        """Address all matching slices; this does not execute/aggregate queries."""
        try:
            manifest = self.validation.manifest
            if isinstance(manifest, NativeManifest):
                validate_native_scope(scope, manifest)
            else:
                scope.validate(manifest)
        except DatasetContractError as exc:
            raise InvalidParameterError(str(exc)) from exc
        return tuple(
            self.root / item.file
            for device in self.validation.manifest.devices
            if scope.device_id is None or device.device_id == scope.device_id
            for item in device.slices
            if (scope.slice_index is None or item.index == scope.slice_index)
            and (scope.start_event_id is None or item.end_event_id >= scope.start_event_id)
            and (scope.end_event_id is None or item.start_event_id <= scope.end_event_id)
        )

    def to_dict(self) -> dict[str, object]:
        manifest = self.validation.manifest
        return {
            "manifest_path": str(self.root / "manifest.json"),
            "schema_version": manifest.schema_version,
            "status": manifest.status,
            "format": NATIVE_FORMAT if isinstance(manifest, NativeManifest) else "compatibility-v1",
            "fingerprint": self.fingerprint,
            "real_event_count": self.validation.real_event_count,
            "boundary_event_count": self.validation.boundary_event_count,
            "text_callstacks": True,
            "structured_frames": False,
            "cross_slice_queries": True,
            "supported_queries": dict(DATASET_SUPPORT),
            "cross_slice_sources": True,
            "ordered_frames_reader_version": 1,
            "structured_frames_scope": "validation_only; query source coverage is separate",
            "devices": [
                {
                    "device_id": device.device_id,
                    "event_count": device.event_count,
                    "slices": [
                        {
                            "index": item.index,
                            "first_event_id": item.start_event_id,
                            "last_event_id": item.end_event_id,
                            "db_path": str(self.root / item.file),
                        }
                        for item in device.slices
                    ],
                }
                for device in sorted(manifest.devices, key=lambda item: item.device_id)
            ],
        }


# This is deliberately process-local, bounded, and contains no open connections.
# Cross-call reuse is opt-in: unknown/coarse filesystems cannot supply a
# trustworthy change token merely because Python exposes st_ctime_ns. The caller
# must attest immutable publication and suitable change-time semantics explicitly.
_CACHE_LIMIT = 16
_VALIDATED: OrderedDict[Path, tuple[_Generation, ResolvedDataset]] = OrderedDict()
_CACHE_LOCK = RLock()


def _stamp(path: Path) -> _FileStamp:
    stat = path.stat()
    return (
        stat.st_dev,
        stat.st_ino,
        stat.st_size,
        stat.st_mtime_ns,
        stat.st_ctime_ns,
        stat.st_mode,
        stat.st_nlink,
    )


def _root(path: Path | str) -> Path | None:
    candidate = Path(path).expanduser().absolute()
    if not candidate.is_dir() and candidate.name != "manifest.json":
        return None
    root = candidate if candidate.is_dir() else candidate.parent
    if candidate.is_symlink() or root.resolve() != root:
        raise DatabaseSchemaError("Dataset must use canonical non-symlink paths.")
    if (root / "manifest.json").is_symlink():
        raise DatabaseSchemaError("Dataset manifest must not be a symlink.")
    if not (root / "manifest.json").is_file():
        raise DatabaseSchemaError("Dataset manifest.json must be a regular file.")
    return root


def _generation(
    root: Path, manifest: DatasetManifest, budget: ValidationBudget | None
) -> _Generation:
    """Always recheck aliases, transport, and membership before trusting a hit."""
    check_budget(budget)
    if isinstance(manifest, NativeManifest):
        require_native_members(root, manifest, budget=budget)
    stamps = [(".", _stamp(root)), ("manifest.json", _stamp(root / "manifest.json"))]
    for device in checked_rows(manifest.devices, budget):
        directory = f"device_{device.device_id}"
        if (root / directory).is_symlink():
            raise DatabaseSchemaError("Dataset device directory must not be a symlink.")
        stamps.append((directory, _stamp(root / directory)))
        for item in checked_rows(device.slices, budget):
            member = root / item.file
            _require_readonly_member(
                root, member, immutable=not isinstance(manifest, NativeManifest)
            )
            stamps.append((item.file, _stamp(member)))
    check_budget(budget)
    return tuple(stamps)


def _cacheable(generation: _Generation) -> bool:
    # This is a caller contract, not an automatic inference from OS or filesystem
    # metadata. Windows ctime historically means creation time, so stay strong.
    return (
        os.environ.get("PT_SNAP_DATASET_CACHE") == "immutable"
        and os.name == "posix"
        and all(stamp[4] > 0 for _, stamp in generation)
    )


def _content_fingerprint(
    root: Path, manifest: DatasetManifest, budget: ValidationBudget | None
) -> str:
    """Strong verification for pinned operations without repeating row validation."""
    digest = hashlib.sha256()
    digest.update(_hash_file(root / "manifest.json", budget=budget).encode("ascii"))
    for device in checked_rows(manifest.devices, budget):
        for item in checked_rows(device.slices, budget):
            digest.update(item.file.encode("utf-8"))
            digest.update(_hash_file(root / item.file, budget=budget).encode("ascii"))
    return digest.hexdigest()


class DatasetResolver:
    """Resolve and validate finalized datasets, reusing unchanged generations.

    By default every call validates and hashes content. Explicitly setting
    PT_SNAP_DATASET_CACHE=immutable enables bounded process-local reuse under
    the caller's immutable-publication/change-time contract. Even then paths,
    members, sidecars and kernel change times are checked on every call.
    Explicit validators always perform full validation.
    """

    def inspect(
        self, path: Path | str, *, budget: ValidationBudget | None = None
    ) -> ResolvedDataset | None:
        check_budget(budget)
        root = _root(path)
        if root is None:
            return None
        try:
            with _CACHE_LOCK:
                cached = _VALIDATED.get(root)
            if cached is not None:
                previous, resolved = cached
                manifest_unchanged = (
                    _stamp(root / "manifest.json") == dict(previous)["manifest.json"]
                )
                generation = (
                    _generation(root, resolved.validation.manifest, budget)
                    if manifest_unchanged
                    else None
                )
                if generation is not None and _cacheable(generation) and generation == previous:
                    with _CACHE_LOCK:
                        if root in _VALIDATED:
                            _VALIDATED.move_to_end(root)
                    result = copy.deepcopy(resolved)
                    check_budget(budget)
                    return result
                with _CACHE_LOCK:
                    _VALIDATED.pop(root, None)
            manifest_path = root / "manifest.json"
            manifest_stamp = _stamp(manifest_path)
            before = _hash_file(manifest_path, budget=budget)
            with manifest_path.open(encoding="utf-8") as source:
                raw: object = json.load(source, object_pairs_hook=_unique_object)
            check_budget(budget)
            planned = (
                parse_native_manifest(raw, budget=budget)
                if isinstance(raw, dict) and raw.get("format") == NATIVE_FORMAT
                else parse_manifest(raw, budget=budget)
            )
            # Preflight every member before the first SQLite open. Capturing
            # both ends also refuses publication during validation or hashing.
            generation = _generation(root, planned, budget)
            if manifest_stamp != _stamp(manifest_path):
                raise DatabaseSchemaError("Dataset manifest changed during inspection; retry.")
            validation = (
                validate_native_dataset(root, planned, budget=budget)
                if isinstance(planned, NativeManifest)
                else validate_dataset(root, budget=budget)
            )
            digest = hashlib.sha256()
            digest.update(before.encode("ascii"))
            for device in checked_rows(validation.manifest.devices, budget):
                for item in checked_rows(device.slices, budget):
                    digest.update(item.file.encode("utf-8"))
                    # Native validation already verifies this digest before and
                    # after SQLite reads; do not hash every shard a third time.
                    content_hash = (
                        item.sha256
                        if isinstance(item, NativeSlice)
                        else _hash_file(root / item.file, budget=budget)
                    )
                    digest.update(content_hash.encode("ascii"))
            if before != _hash_file(manifest_path, budget=budget):
                raise DatabaseSchemaError("Dataset manifest changed during inspection; retry.")
            if generation != _generation(root, planned, budget):
                raise DatabaseSchemaError("Dataset members changed during inspection; retry.")
            extensions = raw.get("extensions") if isinstance(raw, dict) else None
            frames = extensions.get("ptSnapOrderedFrames") if isinstance(extensions, dict) else None
            version = frames.get("version") if isinstance(frames, dict) else None
            result = ResolvedDataset(
                root,
                validation,
                digest.hexdigest(),
                version if type(version) is int else None,
                generation,
            )
            if _cacheable(generation):
                with _CACHE_LOCK:
                    _VALIDATED[root] = (generation, copy.deepcopy(result))
                    _VALIDATED.move_to_end(root)
                    while len(_VALIDATED) > _CACHE_LIMIT:
                        _VALIDATED.popitem(last=False)
            return result
        except (DatasetContractError, OSError, UnicodeError, json.JSONDecodeError) as exc:
            with _CACHE_LOCK:
                _VALIDATED.pop(root, None)
            raise DatabaseSchemaError(f"Invalid dataset: {exc}") from exc

    def completion_device_ids(self, path: Path | str) -> list[int] | None:
        """Bounded manifest-only hints, never evidence of dataset validity.

        Completion must not open or hash shard contents. Large or invalid
        manifests produce no hints; a real query still performs strong admission.
        """
        root = _root(path)
        if root is None:
            return None
        try:
            with (root / "manifest.json").open("rb") as source:
                data = source.read(1024 * 1024 + 1)
            if len(data) > 1024 * 1024:
                return []
            raw: object = json.loads(data, object_pairs_hook=_unique_object)
            manifest = (
                parse_native_manifest(raw)
                if isinstance(raw, dict) and raw.get("format") == NATIVE_FORMAT
                else parse_manifest(raw)
            )
            return sorted(device.device_id for device in manifest.devices)
        except (DatasetContractError, OSError, UnicodeError, json.JSONDecodeError):
            return []
