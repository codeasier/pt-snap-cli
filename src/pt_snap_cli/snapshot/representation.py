from pathlib import Path
from typing import Any

from .simulate import AllocatorHooker, SimulateDeviceSnapshot, SimulateHooker
from .util.file_util import load_pickle_to_dict


def load_snapshot_representation(snapshot_file: str | Path) -> dict[str, Any]:
    """Load the first-party snapshot representation from a trusted pickle."""
    return load_pickle_to_dict(Path(snapshot_file))


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
