"""Resolve finalized compatibility datasets above the single-DB Context layer.

Original local reader of the P0 contract; no pickle, migration or producer code.
Native-v2 private replay staging has no published manifest and is not a dataset.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from pt_snap_cli.core.dataset_contract import (
    DatasetContractError,
    DatasetValidation,
    DeviceRecord,
    QueryScope,
    parse_manifest,
    validate_dataset,
)
from pt_snap_cli.core.errors import DatabaseSchemaError, InvalidDeviceError, InvalidParameterError


@dataclass(frozen=True)
class ResolvedDataset:
    root: Path
    validation: DatasetValidation
    fingerprint: str

    @property
    def device_ids(self) -> list[int]:
        return sorted(item.device_id for item in self.validation.manifest.devices)

    @property
    def callstack_layout(self) -> str:
        return "v1"

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
            scope.validate(self.validation.manifest)
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
            "format": "compatibility-v1",
            "fingerprint": self.fingerprint,
            "real_event_count": self.validation.real_event_count,
            "boundary_event_count": self.validation.boundary_event_count,
            "text_callstacks": True,
            "structured_frames": False,
            "cross_slice_queries": False,
            "supported_queries": ["event: real ID, single-slice range, or explicit slice"],
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


class DatasetResolver:
    """Stateless resolution: revalidate every call, retain no connections/manifest cache.

    Content hashes (not cacheHash or size/mtime alone) form the Context generation.
    Work is proportional to artifact size; no concurrent-publication lock is claimed.
    """

    def inspect(self, path: Path | str) -> ResolvedDataset | None:
        candidate = Path(path).expanduser().absolute()
        if not candidate.is_dir() and candidate.name != "manifest.json":
            return None
        root = candidate if candidate.is_dir() else candidate.parent
        if candidate.is_symlink() or root.resolve() != root:
            raise DatabaseSchemaError("Dataset must use canonical non-symlink paths.")
        try:
            manifest_path = root / "manifest.json"
            if manifest_path.is_symlink():
                raise DatabaseSchemaError("Dataset manifest must not be a symlink.")
            before = _hash_file(manifest_path)
            with manifest_path.open(encoding="utf-8") as source:
                raw: object = json.load(source)
            planned = parse_manifest(raw)
            # mode=ro can create WAL/SHM files even after the last writer has
            # checkpointed and removed them. Check every member before the first
            # SQLite open, without following aliases or repairing the artifact.
            for device in planned.devices:
                for item in device.slices:
                    _require_readonly_member(root, root / item.file)
            validation = validate_dataset(root)
            digest = hashlib.sha256()
            digest.update(before.encode("ascii"))
            for device in validation.manifest.devices:
                for item in device.slices:
                    member = root / item.file
                    _require_readonly_member(root, member)
                    digest.update(item.file.encode("utf-8"))
                    digest.update(_hash_file(member).encode("ascii"))
            if before != _hash_file(manifest_path):
                raise DatabaseSchemaError("Dataset manifest changed during inspection; retry.")
            return ResolvedDataset(root, validation, digest.hexdigest())
        except (DatasetContractError, OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise DatabaseSchemaError(f"Invalid dataset: {exc}") from exc


def _require_readonly_member(root: Path, member: Path) -> None:
    # Manifest parsing fixes canonical relative paths; reject member/parent
    # symlinks before the header read, not only when the validator opens SQLite.
    parts = member.relative_to(root).parts
    for index in range(1, len(parts) + 1):
        if root.joinpath(*parts[:index]).is_symlink():
            raise DatabaseSchemaError(f"Dataset member must not use symlink paths: {member}")
    if member.resolve() != member or not member.is_file():
        raise DatabaseSchemaError(f"Dataset member is missing or not a canonical file: {member}")
    for suffix in ("-wal", "-journal", "-shm"):
        sidecar = Path(str(member) + suffix)
        if sidecar.exists() or sidecar.is_symlink():
            raise DatabaseSchemaError(f"Dataset member has a live SQLite sidecar: {member}")
    with member.open("rb") as source:
        header = source.read(20)
    # SQLite's file-format write/read versions at offsets 18/19 mark WAL as 2.
    # A sidecar-free WAL database is still unsafe to open with mode=ro.
    if header[:16] == b"SQLite format 3\x00" and 2 in header[18:20]:
        raise DatabaseSchemaError(f"Dataset member uses persistent WAL mode: {member}")


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
