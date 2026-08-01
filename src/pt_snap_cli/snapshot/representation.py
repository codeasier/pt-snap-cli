import hashlib
import json
import math
import pickle
from pathlib import Path
from typing import Any, Literal, cast

from .simulate import AllocatorHooker, SimulateDeviceSnapshot, SimulateHooker
from .util.file_util import load_pickle_to_dict, save_dict_to_pickle

SnapshotFormat = Literal["pickle", "json"]


def load_pickle_representation(snapshot_file: str | Path) -> dict[str, Any]:
    """Load a trusted pickle snapshot representation."""
    return cast(dict[str, Any], load_pickle_to_dict(Path(snapshot_file)))


def load_json_representation(snapshot_file: str | Path) -> dict[str, Any]:
    """Load a JSON snapshot representation."""
    with Path(snapshot_file).open(encoding="utf-8") as stream:
        value: object = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError(
            f"The content of the JSON file is not of type dict, actual type: {type(value).__name__}"
        )
    return cast(dict[str, Any], value)


def load_snapshot_representation(
    snapshot_file: str | Path, snapshot_format: SnapshotFormat = "pickle"
) -> dict[str, Any]:
    """Load either supported representation through one dispatch point."""
    if snapshot_format == "pickle":
        return load_pickle_representation(snapshot_file)
    if snapshot_format == "json":
        return load_json_representation(snapshot_file)
    raise ValueError(f"Unsupported snapshot format: {snapshot_format}")


def serialize_snapshot_representation(
    representation: dict[str, Any], snapshot_format: SnapshotFormat = "pickle"
) -> bytes:
    """Serialize a snapshot in its supported pickle or normalized JSON form."""
    if snapshot_format == "pickle":
        return serialize_pickle_representation(representation)
    if snapshot_format == "json":
        return serialize_json_representation(representation)
    raise ValueError(f"Unsupported snapshot format: {snapshot_format}")


def serialize_pickle_representation(representation: dict[str, Any]) -> bytes:
    """Serialize the complete runtime-coupled pickle representation."""
    return pickle.dumps(representation, protocol=4)


def serialize_json_representation(representation: dict[str, Any]) -> bytes:
    """Serialize the normalized inspectable JSON representation."""
    return canonical_snapshot_bytes(representation)


def save_pickle_representation(representation: dict[str, Any], snapshot_file: str | Path) -> None:
    """Save a trusted pickle snapshot using the retained protocol."""
    save_dict_to_pickle(representation, Path(snapshot_file), protocol=4)


def save_json_representation(representation: dict[str, Any], snapshot_file: str | Path) -> None:
    """Save normalized compact UTF-8 JSON."""
    Path(snapshot_file).write_bytes(serialize_json_representation(representation))


def save_snapshot_representation(
    representation: dict[str, Any],
    snapshot_file: str | Path,
    snapshot_format: SnapshotFormat = "pickle",
) -> None:
    """Save a snapshot representation without caller-specific format behavior."""
    path = Path(snapshot_file)
    if snapshot_format == "pickle":
        save_pickle_representation(representation, path)
        return
    if snapshot_format == "json":
        save_json_representation(representation, path)
        return
    raise ValueError(f"Unsupported snapshot format: {snapshot_format}")


def canonicalize_snapshot(value: object) -> object:
    """Normalize supported snapshot values without changing semantic list order."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Canonical snapshots do not support non-finite floats.")
        return value
    if isinstance(value, dict):
        normalized: dict[str, object] = {}
        if not all(isinstance(key, str) for key in value):
            raise ValueError("Canonical snapshots require string dictionary keys.")
        for key in sorted(cast(dict[str, object], value)):
            normalized[key] = canonicalize_snapshot(value[key])
        return normalized
    if isinstance(value, (list, tuple)):
        return [canonicalize_snapshot(item) for item in value]
    raise ValueError(f"Canonical snapshots do not support {type(value).__name__} values.")


def canonical_snapshot_bytes(representation: object) -> bytes:
    """Return canonical UTF-8 JSON bytes for representation equivalence."""
    return json.dumps(
        canonicalize_snapshot(representation),
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_snapshot_sha256(representation: object) -> str:
    """Return the SHA256 of the canonical snapshot bytes."""
    return hashlib.sha256(canonical_snapshot_bytes(representation)).hexdigest()


def replay_snapshot(
    representation: dict[str, Any],
    device: int,
    *,
    hooker: SimulateHooker | None = None,
    allocator_hooker: AllocatorHooker | None = None,
) -> tuple[SimulateDeviceSnapshot, bool]:
    """Construct and replay one device through the shared snapshot runtime."""
    snapshot = SimulateDeviceSnapshot(representation, device)
    if hooker is not None:
        snapshot.register_hooker(hooker)
    if allocator_hooker is not None:
        snapshot.register_allocator_hooker(allocator_hooker)
    return snapshot, snapshot.replay()


def load_and_replay_snapshot(
    snapshot_file: str | Path,
    snapshot_format: SnapshotFormat,
    device: int,
) -> tuple[dict[str, Any], SimulateDeviceSnapshot, bool]:
    """Load and replay either format through the shared validation entrypoint."""
    representation = load_snapshot_representation(snapshot_file, snapshot_format)
    snapshot, replayed = replay_snapshot(representation, device)
    return representation, snapshot, replayed
