"""Dataset point-event lifecycle queries using the shared batched source layer."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from typing import cast

from pt_snap_cli.core.dataset_sources import DatasetSourceResolver, EventSource
from pt_snap_cli.core.errors import QueryExecutionError
from pt_snap_cli.core.models import QueryResult
from pt_snap_cli.core.stack_summary import summarize_stacks

STATIC_LABEL = "[static] allocEventId=-1, freeEventId=-1"
PREEXISTING_LABEL = "[preexisting live] allocEventId=-1"
MISSING_LABEL = "[missing callstack]"


def event_attribution(
    sources: DatasetSourceResolver,
    template: str,
    params: dict[str, object],
    max_rows: int | None,
    exact_total: bool,
    slice_index: int | None,
    semantics_version: int | None,
) -> QueryResult:
    event_id = cast(int, params["event_id"])
    item = sources.target(event_id, slice_index)
    path = sources.dataset.root / item.file
    blocks = sources.read(
        path,
        f'SELECT * FROM "block_{sources.device.device_id}" WHERE size>=? '
        "AND (allocEventId=-1 OR allocEventId<=?) AND (freeEventId=-1 OR freeEventId>?) "
        + ("AND allocEventId!=-1 " if not params["include_static"] else "")
        + "ORDER BY id",
        [params["min_size"], event_id, event_id],
    )
    references = sources.events(
        cast(int, block[field])
        for block in blocks
        for field in ("allocEventId", "freeEventId")
        if cast(int, block[field]) >= 0
    )
    allocation_events = allocation_stacks = free_events = ordered_blocks = dynamic_bytes = (
        captured_bytes
    ) = 0
    dynamic_blocks = preexisting_blocks = 0
    for block in blocks:
        sources.budget.remaining()
        alloc, free = cast(int, block["allocEventId"]), cast(int, block["freeEventId"])
        category = (
            "dynamic_live_at_event"
            if alloc >= 0
            else "static" if free == -1 else "preexisting_live_at_event"
        )
        block["category"] = category
        block["lifecycle_id"] = f"{sources.namespace}:" + (
            f"alloc:{alloc}" if alloc >= 0 else f"preexisting:{block['id']}"
        )
        # The stored state is a replay/slice observation, not necessarily state at E.
        block["state_scope"] = "slice_observation"
        allocation, completion = references.get(alloc), references.get(free)
        # Base schemas can be structurally valid yet have an invalid source action.
        # Preserve bytes/category and report the missing proof instead of guessing.
        allocation = (
            allocation if allocation is not None and allocation.event["action"] == 4 else None
        )
        completion = (
            completion if completion is not None and completion.event["action"] == 6 else None
        )
        block["allocation_source"] = allocation.to_dict() if allocation else None
        block["free_source"] = completion.to_dict() if completion else None
        block["allocation_source_status"] = (
            "unknown_preexisting" if alloc == -1 else "resolved" if allocation else "missing"
        )
        block["free_source_status"] = (
            "live_or_unknown" if free == -1 else "resolved" if completion else "missing"
        )
        if alloc >= 0:
            dynamic_blocks += 1
            dynamic_bytes += cast(int, block["size"])
            allocation_events += allocation is not None
            allocation_stacks += allocation is not None and allocation.stack_kind == "captured"
            ordered_blocks += allocation is not None and allocation.frames is not None
            if allocation is not None and allocation.stack_kind == "captured":
                captured_bytes += cast(int, block["size"])
        else:
            preexisting_blocks += 1
        free_events += completion is not None
    coverage: dict[str, object] = {
        "range_complete": True,
        "event_position": "after",
        "active_blocks": len(blocks),
        "active_bytes": sum(cast(int, b["size"]) for b in blocks),
        "dynamic_blocks": dynamic_blocks,
        "dynamic_bytes": dynamic_bytes,
        "allocation_events_resolved": allocation_events,
        "allocation_stacks_captured": allocation_stacks,
        "allocation_source_complete": allocation_events == dynamic_blocks,
        "captured_dynamic_bytes": captured_bytes,
        "unknown_preexisting_blocks": preexisting_blocks,
        "free_references": sum(cast(int, b["freeEventId"]) >= 0 for b in blocks),
        "free_events_resolved": free_events,
        "ordered_frame_blocks": ordered_blocks,
        "ordered_frames_complete": dynamic_blocks > 0 and ordered_blocks == dynamic_blocks,
        "frame_degradation": (
            None
            if dynamic_blocks > 0 and ordered_blocks == dynamic_blocks
            else "text_only_or_uncovered"
        ),
        "source_queries": sources.query_count,
    }
    scope: dict[str, object] = {
        "kind": "event",
        "device_id": sources.device.device_id,
        "slice_index": item.index,
        "first_event_id": event_id,
        "last_event_id": event_id,
        "db_path": str(path),
        "dataset_path": str(sources.dataset.root),
        "fingerprint": sources.dataset.fingerprint,
        "boundary_events_included": False,
        "source_coverage": coverage,
    }
    if template == "active_blocks_at_event":
        key = cast(str, params["order_by"])
        blocks.sort(key=lambda b: cast(int, b["id"]))
        blocks.sort(key=lambda b: cast(int, b[key]), reverse=params["order_dir"] == "DESC")
        all_rows = blocks
        rank_full = False
        limit = cast(int, params["limit"])
        offset = max(0, cast(int, params["offset"]))
        selected = all_rows[offset : offset + limit] if limit >= 0 else all_rows[offset:]
    else:
        all_rows = _groups(sources, blocks, references)
        top_n = cast(int, params["top_n"])
        dynamic = [row for row in all_rows if row["category"] == "dynamic_live_at_event"]
        rank_full = top_n >= 0 and bool(dynamic) and len(dynamic) >= top_n
        selected = [row for row in all_rows if row["category"] != "dynamic_live_at_event"] + (
            dynamic[:top_n] if top_n >= 0 else dynamic
        )
        selected.sort(key=_rank)
        denominator = sum(cast(int, row["size_bytes"]) for row in selected)
        # Use the same SQLite arithmetic/ROUND implementation as standalone SQL.
        # A Decimal conversion of a binary float changes some near-half values.
        # This connection evaluates scalars only: no source reads or merge tables.
        with _rounding_cursor(sources) as cursor:
            for row in selected:
                sources.budget.remaining()
                row["percent_of_active_blocks"] = cursor.execute(
                    "SELECT ROUND(? * 100.0 / NULLIF(?, 0), 4)",
                    (row["size_bytes"], denominator),
                ).fetchone()[0]
        offset = 0
    has_more = len(selected) < len(all_rows) - offset or rank_full
    if max_rows is not None and max_rows > 0:
        has_more = has_more or len(selected) > max_rows
        selected = selected[:max_rows]
    if exact_total:
        has_more = len(all_rows) > len(selected) + offset
    sources.budget.consume(selected)
    return QueryResult(
        total=len(all_rows) if exact_total else len(selected),
        returned=len(selected),
        device_id=sources.device.device_id,
        rows=selected,
        template=template,
        semantics_version=semantics_version,
        has_more=has_more,
        truncated=has_more or offset > 0,
        total_is_exact=exact_total or not has_more and offset == 0,
        timeout_s=sources.budget.timeout_s,
        scope=scope,
    )


def _rank(row: dict[str, object]) -> tuple[int, int, str, str]:
    return (
        -cast(int, row["size_bytes"]),
        -cast(int, row["block_count"]),
        cast(str, row["callstack"]),
        cast(str, row["source_stack_id"]),
    )


def _groups(
    sources: DatasetSourceResolver,
    blocks: list[dict[str, object]],
    references: dict[int, EventSource],
) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = {}
    for block in blocks:
        sources.budget.remaining()
        category = cast(str, block["category"])
        source = references.get(cast(int, block["allocEventId"]))
        if block["allocation_source"] is None:
            source = None
        kind = source.stack_kind if source is not None else "missing"
        if category != "dynamic_live_at_event":
            kind = category
        sourced = (
            source is not None
            and category == "dynamic_live_at_event"
            and (kind == "captured" or source.frames is not None)
        )
        identity = (
            source.stack_id
            if sourced and source is not None
            else f"{sources.namespace}:category:{kind}"
        )
        text = (
            source.event["callstack"]
            if kind == "captured" and source is not None and source.text_kind == "captured"
            else (
                STATIC_LABEL
                if kind == "static"
                else PREEXISTING_LABEL if kind == "preexisting_live_at_event" else MISSING_LABEL
            )
        )
        group = grouped.setdefault(
            identity,
            {
                "callstack": text,
                "category": category,
                "block_count": 0,
                "size_bytes": 0,
                "requested_bytes": 0,
                "source_stack_id": identity,
                "stack_kind": kind,
                "text_kind": source.text_kind if sourced and source else kind,
                "stack_id": identity,
                "stack_event_id": source.event["id"] if sourced and source else None,
                "frames": source.frames if sourced and source else None,
                "frames_status": (source.frames_status if sourced and source else "text_only"),
            },
        )
        group["block_count"] = cast(int, group["block_count"]) + 1
        group["size_bytes"] = cast(int, group["size_bytes"]) + cast(int, block["size"])
        group["requested_bytes"] = cast(int, group["requested_bytes"]) + cast(
            int, block["requestedSize"]
        )
        if source is not None and sourced:
            if group["text_kind"] != "captured" and source.text_kind == "captured":
                group["callstack"] = source.event["callstack"]
                group["text_kind"] = "captured"
                group["stack_event_id"] = source.event["id"]
            elif group["text_kind"] != "captured" or source.text_kind == "captured":
                group["stack_event_id"] = min(
                    cast(int, group["stack_event_id"]), cast(int, source.event["id"])
                )
    rows = list(grouped.values())
    # Reuse one scalar-only engine for this pass and close it on timeout as well
    # as success. Derived values do not add source IO; final output is still
    # charged by event_attribution's existing consume(selected) boundary.
    with _rounding_cursor(sources) as cursor:
        for row in rows:
            sources.budget.remaining()
            row["size_gib"], row["requested_gib"] = cursor.execute(
                "SELECT ROUND(? / 1073741824.0, 6), ROUND(? / 1073741824.0, 6)",
                (row["size_bytes"], row["requested_bytes"]),
            ).fetchone()
    rows.sort(key=_rank)
    return rows


def summarize_dataset_stacks(rows: list[dict[str, object]], budget: int) -> None:
    """Shorten display only; retain the already proved cross-shard identity."""
    identities = [(row["stack_id"], row["stack_kind"]) for row in rows]
    for row in rows:
        # Raw frames may be captured even when the formatted TEXT is absent.
        if not isinstance(row.get("callstack"), str):
            row["stack_kind"] = "missing"
    summarize_stacks(rows, budget, "v1")
    for row, (identity, kind) in zip(rows, identities, strict=True):
        row["stack_id"] = identity
        row["stack_kind"] = kind


@contextmanager
def _rounding_cursor(sources: DatasetSourceResolver) -> Iterator[sqlite3.Cursor]:
    """Keep scalar arithmetic failures on the same domain boundary as shard SQL."""
    try:
        with (
            closing(sqlite3.connect(":memory:")) as connection,
            closing(connection.cursor()) as cursor,
        ):
            yield cursor
    except (sqlite3.Error, OverflowError) as exc:
        sources.budget.remaining()  # Preserve a deadline that expired during SQLite work.
        raise QueryExecutionError(str(exc)) from exc
