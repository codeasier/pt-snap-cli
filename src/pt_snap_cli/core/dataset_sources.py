"""Read-only, batched device/event source lookup over a validated dataset.

No address joins, foreign-event insertion, text-to-frame reconstruction, or retained
cross-operation source cache. The caller owns the Context LRU and the entire operation's deadline.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import time
from bisect import bisect_right
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from pt_snap_cli.context import DatabaseNotFoundError, SchemaVersionError
from pt_snap_cli.core.context_cache import ContextCache
from pt_snap_cli.core.dataset_contract import SliceRecord, _unique_object
from pt_snap_cli.core.dataset_files import require_readonly_member
from pt_snap_cli.core.dataset_resolver import ResolvedDataset
from pt_snap_cli.core.errors import (
    DatabaseSchemaError,
    InvalidParameterError,
    QueryExecutionError,
    QueryTimeoutError,
)
from pt_snap_cli.query.executor import QueryExecutionError as ExecutorError
from pt_snap_cli.query.executor import QueryExecutor
from pt_snap_cli.query.executor import QueryTimeoutError as ExecutorTimeout

SOURCE_BATCH_SIZE = 256


def _invalid_constant(value: str) -> object:
    raise ValueError(f"Non-JSON numeric constant: {value}")


def _finite_float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Non-finite frame number")
    return result


def _bounded_depth(value: object) -> bool:
    pending = [(value, 0)]
    while pending:
        current, depth = pending.pop()
        if depth > 128:
            return False
        if isinstance(current, dict):
            pending.extend((item, depth + 1) for item in current.values())
        elif isinstance(current, list):
            pending.extend((item, depth + 1) for item in current)
    return True


@dataclass
class QueryBudget:
    timeout_s: float | None
    started: float
    max_work_rows: int = 100_000
    max_work_bytes: int = 64 * 1024 * 1024
    work_rows: int = 0
    work_bytes: int = 0

    def consume(self, rows: list[dict[str, object]]) -> None:
        """Bound cumulative fetched rows/serialized values, not merely output.

        Includes repeated source reads. Exceeding either ceiling fails the whole
        operation, never returning a silently partial global conclusion. This is
        not an RSS ceiling: SQLite and one fetched batch have their own overhead.
        """
        self.remaining()
        self.work_rows += len(rows)
        self.work_bytes += sum(
            len(json.dumps(row, ensure_ascii=True, default=str).encode("utf-8")) for row in rows
        )
        if self.work_rows > self.max_work_rows or self.work_bytes > self.max_work_bytes:
            raise QueryExecutionError(
                "Dataset query work budget exceeded (100000 fetched rows / 64 MiB serialized "
                "values by default); no partial global result. Narrow the scope or select a member."
            )

    def remaining(self) -> float | None:
        if self.timeout_s is None:
            return None
        left = self.timeout_s - (time.monotonic() - self.started)
        if left <= 0:
            raise QueryTimeoutError(f"Query timed out after {self.timeout_s} seconds")
        return left


@dataclass(frozen=True)
class EventSource:
    event: dict[str, object]
    slice_index: int
    stack_id: str
    stack_kind: str
    frames: list[dict[str, object]] | None = None
    frames_status: str = "text_only"
    local_stack_id: int | None = None

    @property
    def text_kind(self) -> str:
        text = self.event.get("callstack")
        return "captured" if isinstance(text, str) and text != "" else "missing"

    def to_dict(self) -> dict[str, object]:
        return {
            "event": self.event,
            "slice_index": self.slice_index,
            "local_stack_id": self.local_stack_id,
            "stack_id": self.stack_id,
            "stack_kind": self.stack_kind,
            "text_kind": self.text_kind,
            "frames": self.frames,
            "frames_status": self.frames_status,
        }


class DatasetSourceResolver:
    """One operation's sources; at most one SQL batch per shard/256 distinct IDs.

    Schema/optional frame checks add a constant number of queries per visited
    shard. Connections are sequential and bounded by the borrowed LRU, not blocks.
    """

    def __init__(
        self, dataset: ResolvedDataset, device_id: int, cache: ContextCache, budget: QueryBudget
    ) -> None:
        self.dataset = dataset
        self.device = dataset.device(device_id)
        self.cache = cache
        self.budget = budget
        self.query_count = 0
        self._starts = [s.start_event_id for s in self.device.slices]
        # Lifetime is one budgeted operation. Each retained source was charged
        # when fetched; reusing the same object performs no further database work.
        self._events: dict[int, EventSource] = {}

    @property
    def namespace(self) -> str:
        return f"dataset:{self.dataset.fingerprint}:device:{self.device.device_id}"

    def owner(self, event_id: int) -> SliceRecord | None:
        if type(event_id) is not int or event_id < 0:
            return None
        index = bisect_right(self._starts, event_id) - 1
        if index < 0:
            return None
        item = self.device.slices[index]
        return item if event_id <= item.end_event_id else None

    def target(self, event_id: int, slice_index: int | None = None) -> SliceRecord:
        item = self.owner(event_id)
        if item is None or (slice_index is not None and item.index != slice_index):
            raise InvalidParameterError("Event ID must be a real ID within the selected scope.")
        if event_id not in self.events([event_id]):
            raise InvalidParameterError(
                f"No real event at ID {event_id}; sparse gaps are not events."
            )
        return item

    def _consume(self, rows: list[dict[str, object]]) -> None:
        # The executor intentionally knows only its own errors. Translate the
        # core callback's timeout before its generic exception boundary, so
        # cancellation keeps the domain kind and CLI QUERY_TIMEOUT code.
        try:
            self.budget.consume(rows)
        except QueryTimeoutError as exc:
            raise ExecutorTimeout(str(exc)) from exc
        except QueryExecutionError as exc:
            raise ExecutorError(str(exc)) from exc

    def read(
        self, path: Path, sql: str, values: list[object] | None = None
    ) -> list[dict[str, object]]:
        self.budget.remaining()
        require_readonly_member(
            self.dataset.root, path, immutable=self.dataset.callstack_layout == "v1"
        )
        try:
            context = self.cache.get(
                path,
                generation=self.dataset.fingerprint,
                immutable=self.dataset.callstack_layout == "v1",
            )
            self.query_count += 1
            return QueryExecutor(context).execute(
                sql, values, timeout_s=self.budget.remaining(), consume=self._consume
            )
        except ExecutorTimeout as exc:
            raise QueryTimeoutError(
                f"Query timed out after {self.budget.timeout_s} seconds"
            ) from exc
        except ExecutorError as exc:
            raise QueryExecutionError(str(exc)) from exc
        except (DatabaseNotFoundError, SchemaVersionError, sqlite3.DatabaseError) as exc:
            raise DatabaseSchemaError(str(exc)) from exc

    def events(self, event_ids: Iterable[int]) -> dict[int, EventSource]:
        grouped: dict[int, list[int]] = defaultdict(list)
        result: dict[int, EventSource] = {}
        for event in sorted(set(event_ids)):
            self.budget.remaining()
            if event in self._events:
                result[event] = self._events[event]
                continue
            item = self.owner(event)
            if item is not None:
                grouped[item.index].append(event)
        for index, ids in grouped.items():
            item = self.device.slices[index]
            path = self.dataset.root / item.file
            trace = f'"trace_entry_{self.device.device_id}"'
            for start in range(0, len(ids), SOURCE_BATCH_SIZE):
                batch = ids[start : start + SOURCE_BATCH_SIZE]
                placeholders = ",".join("?" for _ in batch)
                sql = (
                    f"SELECT t.*, cs.callstack FROM {trace} t LEFT JOIN callstack cs ON t.callstackId=cs.id"
                    if self.dataset.callstack_layout == "v2"
                    else f"SELECT t.* FROM {trace} t"
                )
                rows = self.read(
                    path, sql + f" WHERE t.id IN ({placeholders}) AND t.id>=0", list(batch)
                )
                result.update(self.events_from_rows(item, rows))
        self.budget.remaining()
        return result

    def events_from_rows(
        self, item: SliceRecord, rows: list[dict[str, object]]
    ) -> dict[int, EventSource]:
        """Resolve already charged full event rows without fetching them again.

        Native rows must include joined callstack text and the local callstackId.
        Frame reads still incur the same work budget as events() source lookup.
        """
        result: dict[int, EventSource] = {}
        for original in rows:
            self.budget.remaining()
            event_id = cast(int, original["id"])
            if event_id in self._events:
                result[event_id] = self._events[event_id]
                continue
            if self.owner(event_id) != item:
                raise QueryExecutionError("Source event does not belong to the selected shard.")
            row = dict(original)
            event_id = cast(int, row["id"])
            text = row.get("callstack")
            captured = isinstance(text, str) and text != ""
            local_id = cast(int | None, row.pop("callstackId", None))
            # V2 IDs select text WITHIN the owning DB; they are provenance,
            # not dataset grouping keys. Global interning equivalence uses
            # the full captured text, never a shortened display prefix.
            identity = (
                "text:sha256:"
                + hashlib.sha256(
                    (text if isinstance(text, str) else "").encode("utf-8")
                ).hexdigest()
            )
            result[event_id] = EventSource(
                row,
                item.index,
                (
                    f"{self.namespace}:{identity}"
                    if captured
                    else f"{self.namespace}:category:missing"
                ),
                "captured" if captured else "missing",
                local_stack_id=local_id,
            )
        fresh = {event: source for event, source in result.items() if event not in self._events}
        if fresh:
            self._attach_frames(self.dataset.root / item.file, list(fresh), fresh)
        self._events.update(fresh)
        result.update(fresh)
        self.budget.remaining()
        return result

    def _attach_frames(self, path: Path, ids: list[int], sources: dict[int, EventSource]) -> None:
        # This is a NEW, explicit read contract, not a guessed original-producer
        # schema. Existing pt_snap_block_reference has formatted text only.
        if self.dataset.ordered_frames_version != 1:
            return
        expected = {
            "pt_snap_frame_coverage": [("eventId", "INTEGER", 1), ("frameCount", "INTEGER", 0)],
            "pt_snap_frame": [
                ("eventId", "INTEGER", 1),
                ("frameIndex", "INTEGER", 2),
                ("frameJson", "TEXT", 0),
            ],
        }
        for table, columns in expected.items():
            kind = self.read(path, "SELECT type FROM sqlite_master WHERE name=?", [table])
            schema = self.read(path, f'PRAGMA table_info("{table}")')
            if (
                kind != [{"type": "table"}]
                or [(r["name"], r["type"], r["pk"]) for r in schema] != columns
            ):
                return  # Unknown/absent schemas never imply precision.
        for start in range(0, len(ids), SOURCE_BATCH_SIZE):
            batch = ids[start : start + SOURCE_BATCH_SIZE]
            placeholders = ",".join("?" for _ in batch)
            coverage = self.read(
                path,
                f"SELECT * FROM pt_snap_frame_coverage WHERE eventId IN ({placeholders})",
                list(batch),
            )
            frames = self.read(
                path,
                f"SELECT * FROM pt_snap_frame WHERE eventId IN ({placeholders}) ORDER BY eventId,frameIndex",
                list(batch),
            )
            by_event: dict[int, list[dict[str, object]]] = defaultdict(list)
            for row in frames:
                by_event[cast(int, row["eventId"])].append(row)
            for row in coverage:
                event = cast(int, row["eventId"])
                count = row["frameCount"]
                entries = by_event[event]
                if (
                    event not in sources
                    or type(count) is not int
                    or count < 0
                    or len(entries) != count
                ):
                    continue
                if any(
                    type(entry["frameIndex"]) is not int or not isinstance(entry["frameJson"], str)
                    for entry in entries
                ) or [entry["frameIndex"] for entry in entries] != list(range(count)):
                    continue
                try:
                    decoded = [
                        json.loads(
                            cast(str, entry["frameJson"]),
                            object_pairs_hook=_unique_object,
                            parse_constant=_invalid_constant,
                            parse_float=_finite_float,
                        )
                        for entry in entries
                    ]
                    if not all(isinstance(frame, dict) for frame in decoded) or not _bounded_depth(
                        decoded
                    ):
                        continue
                    # Canonical raw arrays retain order, duplicates and typed fields.
                    # Text formatting and shard-local IDs are only provenance here.
                    digest = hashlib.sha256(
                        json.dumps(
                            decoded,
                            sort_keys=True,
                            ensure_ascii=True,
                            separators=(",", ":"),
                            allow_nan=False,
                        ).encode("utf-8")
                    ).hexdigest()
                except (ValueError, TypeError, RecursionError, OverflowError):
                    continue
                old = sources[event]
                sources[event] = EventSource(
                    old.event,
                    old.slice_index,
                    f"{self.namespace}:frames:sha256:{digest}",
                    "captured",
                    decoded,
                    "ordered",
                    old.local_stack_id,
                )
