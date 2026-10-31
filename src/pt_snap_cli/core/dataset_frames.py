"""Read the version-2 normalized frame extension without reconstructing text."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Protocol, cast

from pt_snap_cli._frame_json import _bounded_depth, _finite_float, _invalid_constant

from .dataset_contract import _unique_object


class FrameBudget(Protocol):
    def remaining(self) -> float | None: ...


class FrameResolver(Protocol):
    _frame_schemas: dict[Path, bool]

    @property
    def budget(self) -> FrameBudget: ...

    def read(
        self, path: Path, sql: str, values: list[object] | None = None
    ) -> list[dict[str, object]]: ...


SCHEMA = {
    "pt_snap_frame_value": [("id", "INTEGER", 1), ("frameJson", "TEXT", 0)],
    "pt_snap_stack": [("stackId", "INTEGER", 1), ("frameCount", "INTEGER", 0)],
    "pt_snap_stack_frame": [
        ("stackId", "INTEGER", 1),
        ("frameIndex", "INTEGER", 2),
        ("frameId", "INTEGER", 0),
    ],
    "pt_snap_event_stack": [("eventId", "INTEGER", 1), ("stackId", "INTEGER", 0)],
}


def attach_frames(
    resolver: FrameResolver, path: Path, ids: list[int]
) -> dict[int, tuple[list[dict[str, object]], str]]:
    result: dict[int, tuple[list[dict[str, object]], str]] = {}
    batch_size = 256

    if path not in resolver._frame_schemas:
        valid = True
        for table, columns in SCHEMA.items():
            kind = resolver.read(path, "SELECT type FROM sqlite_master WHERE name=?", [table])
            schema = resolver.read(path, f'PRAGMA table_info("{table}")')
            if (
                kind != [{"type": "table"}]
                or [(r["name"], r["type"], r["pk"]) for r in schema] != columns
            ):
                valid = False
                break
        resolver._frame_schemas[path] = valid
    if not resolver._frame_schemas[path]:
        return result
    for start in range(0, len(ids), batch_size):
        batch = ids[start : start + batch_size]
        marks = ",".join("?" for _ in batch)
        coverage = resolver.read(
            path,
            "SELECT e.eventId,e.stackId,s.frameCount FROM pt_snap_event_stack e "
            f"LEFT JOIN pt_snap_stack s ON s.stackId=e.stackId WHERE e.eventId IN ({marks})",
            list(batch),
        )
        entries = resolver.read(
            path,
            "SELECT sf.stackId,sf.frameIndex,sf.frameId,f.frameJson FROM pt_snap_stack_frame sf "
            "LEFT JOIN pt_snap_frame_value f ON f.id=sf.frameId "
            f"WHERE sf.stackId IN (SELECT stackId FROM pt_snap_event_stack WHERE eventId IN ({marks})) "
            "ORDER BY sf.stackId,sf.frameIndex",
            list(batch),
        )
        grouped: dict[int, list[dict[str, object]]] = defaultdict(list)
        for row in entries:
            grouped[cast(int, row["stackId"])].append(row)
        decoded_stacks: dict[int, tuple[list[dict[str, object]], str] | None] = {}
        for row in coverage:
            resolver.budget.remaining()
            event, stack, count = row["eventId"], row["stackId"], row["frameCount"]
            if event not in ids or type(stack) is not int or type(count) is not int or count < 0:
                continue
            stack = cast(int, stack)
            if stack not in decoded_stacks:
                decoded_stacks[stack] = None
                frames = grouped[stack]
                if len(frames) != count or any(
                    type(frame["frameIndex"]) is not int
                    or frame["frameIndex"] != index
                    or type(frame["frameId"]) is not int
                    or not isinstance(frame["frameJson"], str)
                    for index, frame in enumerate(frames)
                ):
                    continue
                try:
                    decoded = [
                        json.loads(
                            cast(str, frame["frameJson"]),
                            object_pairs_hook=_unique_object,
                            parse_constant=_invalid_constant,
                            parse_float=_finite_float,
                        )
                        for frame in frames
                    ]
                    if not all(isinstance(frame, dict) for frame in decoded) or not _bounded_depth(
                        decoded
                    ):
                        continue
                    canonical = json.dumps(
                        decoded,
                        sort_keys=True,
                        ensure_ascii=True,
                        separators=(",", ":"),
                        allow_nan=False,
                    )
                    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
                except (ValueError, TypeError, RecursionError, OverflowError):
                    continue
                decoded_stacks[stack] = (decoded, digest)
            value = decoded_stacks[stack]
            if value is not None:
                decoded, digest = value
                result[cast(int, event)] = (decoded, digest)
    return result
