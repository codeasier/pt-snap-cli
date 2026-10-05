"""Internal P1 shared producer boundary, not a CLI import/export facade."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from ..snapshot.representation import load_snapshot_representation
from ..snapshot.tools.adaptors.sharded_replay import ReplaySlice, build_shards


@dataclass(frozen=True)
class ShardedReplayResult:
    directory: Path
    slices: tuple[ReplaySlice, ...]
    omitted_devices: tuple[int, ...]
    layout: str = "native-v2"


class ShardedReplayService:
    def stage(
        self,
        source: Path | str,
        directory: Path | str,
        *,
        events_per_slice: int,
        device: int | None = None,
    ) -> ShardedReplayResult:
        """Load once and finalize native shards in a NEW private staging directory.

        The caller owns partial files on failure. No manifest, ready slice, focus,
        cache reuse or final publication is exposed. Only a successful result can
        be handed to a subsequent exporter/publication service. Pickle is trusted
        executable input; this does not implement streaming or an RSS bound.
        """
        if type(events_per_slice) is not int or events_per_slice <= 0:
            raise ValueError("events_per_slice must be a positive integer")
        if device is not None and (type(device) is not int or device < 0):
            raise ValueError("device must be a nonnegative integer")
        target = Path(directory).absolute()
        if target.resolve() != target or target.is_symlink():
            raise ValueError("Staging directory must be canonical and non-symlink")
        if target.exists():
            raise FileExistsError(target)
        data = load_snapshot_representation(Path(source))
        traces = cast(list[list[object]], data.get("device_traces", []))
        available = tuple(index for index, entries in enumerate(traces) if entries)
        if not available or (device is not None and device not in available):
            raise ValueError("Requested device is absent or has no trace events")
        selected = available if device is None else (device,)
        # Exclusive allocation: never replace or adopt an existing directory.
        target.mkdir()
        slices = build_shards(data, target, events_per_slice, selected)
        return ShardedReplayResult(
            target, slices, tuple(index for index in range(len(traces)) if index not in selected)
        )
