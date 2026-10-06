"""Explicit built-in global algorithms; no local caps or temporary merge database.

Fetched work is cumulatively bounded by QueryBudget, including sources and final
output. Sorting/materialization is O(bounded work), NOT O(max_rows). A budget
failure rejects the operation rather than returning an alleged global answer.
"""

from __future__ import annotations

import hashlib
from typing import cast

from pt_snap_cli.core.dataset_contract import QueryScope, SliceRecord
from pt_snap_cli.core.dataset_sources import DatasetSourceResolver
from pt_snap_cli.core.errors import InvalidParameterError, QueryExecutionError
from pt_snap_cli.core.models import QueryResult

METRICS = ("allocated", "active", "reserved")


def _range(
    sources: DatasetSourceResolver, params: dict[str, object], slice_index: int | None
) -> tuple[int, int, list[SliceRecord]]:
    device = sources.device
    if slice_index is not None:
        sources.dataset.paths(QueryScope("slice", device.device_id, slice_index))
        members = [device.slices[slice_index]]
    else:
        members = list(device.slices)
    low, high = members[0].start_event_id, members[-1].end_event_id
    start = params.get("start_id", params.get("min_id"))
    end = params.get("end_id", params.get("max_id"))
    event = params.get("id")
    # `id` on block means block ID, so its caller does not pass it here.
    for endpoint in (start, end, event):
        if endpoint is not None and (type(endpoint) is not int or not low <= endpoint <= high):
            raise InvalidParameterError("Event range must lie within the selected real scope.")
    low = cast(int, start) if start is not None else low
    high = cast(int, end) if end is not None else high
    if event is not None:
        low, high = max(low, cast(int, event)), min(high, cast(int, event))
        # Contradictory filters remain an empty matching set, not a made-up event.
    elif low > high:
        raise InvalidParameterError("Event range start must not exceed end.")
    return low, high, [s for s in members if s.end_event_id >= low and s.start_event_id <= high]


def _scope(
    sources: DatasetSourceResolver, low: int, high: int, items: list[SliceRecord]
) -> dict[str, object]:
    return {
        "kind": "event_range",
        "device_id": sources.device.device_id,
        "slice_index": items[0].index if len(items) == 1 else None,
        "slice_indices": [s.index for s in items],
        "first_event_id": low,
        "last_event_id": high,
        "requested_range": {"first_event_id": low, "last_event_id": high},
        "dataset_path": str(sources.dataset.root),
        "fingerprint": sources.dataset.fingerprint,
        "boundary_events_included": False,
        "range_complete": True,
        "work_budget": {
            "max_rows": sources.budget.max_work_rows,
            "max_bytes": sources.budget.max_work_bytes,
            "unit": "cumulative_fetched_and_output_serialized_values; not_RSS",
        },
    }


def _traces(sources: DatasetSourceResolver, low: int, high: int, items: list[SliceRecord]):
    for item in items:
        rows = sources.read(
            sources.dataset.root / item.file,
            f'SELECT * FROM "trace_entry_{sources.device.device_id}" WHERE id>=0 AND id>=? AND id<=? ORDER BY id',
            [low, high],
        )
        yield item, rows


def _peaks(sources, low, high, items, template, scope):
    chosen: dict[str, dict[str, object]] = {}
    count, first, last = 0, None, None
    for _item, rows in _traces(sources, low, high, items):
        for row in rows:
            sources.budget.remaining()
            event = cast(int, row["id"])
            count += 1
            first = event if first is None else min(first, event)
            last = event if last is None else max(last, event)
            for metric in METRICS:
                if metric not in chosen or (cast(int, row[metric]), -event) > (
                    cast(int, chosen[metric][metric]),
                    -cast(int, chosen[metric]["id"]),
                ):
                    chosen[metric] = row
    result: dict[str, object] = {}
    for metric in METRICS:
        row = chosen.get(metric, {})
        result[f"peak_{metric}"] = row.get(metric)
        result[f"peak_{metric}_event_id"] = row.get("id")
        if template == "allocator_gap":
            for other in METRICS:
                if other != metric:
                    result[f"{other}_at_{metric}_peak"] = row.get(other)
            for other in ("active", "allocated"):
                result[f"reserved_{other}_gap_at_{metric}_peak"] = (
                    cast(int, row["reserved"]) - cast(int, row[other]) if row else None
                )
    if template == "allocator_gap":
        ids = [result[f"peak_{m}_event_id"] for m in METRICS]
        result["all_peaks_same_event"] = int(None not in ids and len(set(ids)) == 1)
        for a, b in (("allocated", "active"), ("active", "reserved"), ("allocated", "reserved")):
            result[f"{a}_{b}_same_event"] = int(
                result[f"peak_{a}_event_id"] is not None
                and result[f"peak_{a}_event_id"] == result[f"peak_{b}_event_id"]
            )
    scope["actual_range"] = {
        "first_event_id": first,
        "last_event_id": last,
        "real_event_count": count,
    }
    scope["peak_owner_slices"] = {
        m: sources.owner(cast(int, r["id"])).index for m, r in chosen.items()
    }
    return [result]


def _matches(row: dict[str, object], params: dict[str, object], fields: tuple[str, ...]) -> bool:
    for field in fields:
        value = params.get(field)
        if value is not None and row[field] != value:
            return False
        for prefix, predicate in (("min_", lambda a, b: a >= b), ("max_", lambda a, b: a <= b)):
            value = params.get(prefix + field)
            if value is not None and (row[field] is None or not predicate(row[field], value)):
                return False
    return True


def _sort(rows: list[dict[str, object]], key: str, descending: bool) -> None:
    # SQLite NULL placement and declared primary/id direction, plus full identity
    # tie-breaks for unusual unproved historical rows with the same local ID.
    rows.sort(key=lambda r: cast(str, r.get("lifecycle_id", "")), reverse=descending)
    rows.sort(key=lambda r: cast(int, r["id"]), reverse=descending)
    rows.sort(key=lambda r: (r[key] is not None, r[key]), reverse=descending)


def _events(sources, low, high, items, params, template, scope):
    rows = []
    first, last, count = None, None, 0
    for _item, batch in _traces(sources, low, high, items):
        for row in batch:
            sources.budget.remaining()
            event = cast(int, row["id"])
            first = event if first is None else min(first, event)
            last = event if last is None else max(last, event)
            count += 1
            fields = ("allocated", "active", "reserved")
            if template == "event":
                fields += ("id", "action", "address", "size", "stream")
            if _matches(row, params, fields):
                rows.append(row)
    scope["actual_range"] = {
        "first_event_id": first,
        "last_event_id": last,
        "real_event_count": count,
    }
    if template == "event":
        # Only returned events need formatted text; resolve separately after the
        # global window below. `order_by=callstack` requires text BEFORE sorting.
        if params["order_by"] == "callstack":
            refs = sources.events(cast(int, r["id"]) for r in rows)
            for row in rows:
                row["callstack"] = refs[cast(int, row["id"])].event.get("callstack")
    _sort(rows, params["order_by"], params["order_dir"] == "DESC")
    return rows


def _lifecycles(sources, items, scope):
    merged: dict[str, dict[str, object]] = {}
    terminal = sources.device.slices[-1].index
    resolved_alloc = resolved_free = unproved = 0
    for item in items:
        blocks = sources.read(
            sources.dataset.root / item.file,
            f'SELECT * FROM "block_{sources.device.device_id}" ORDER BY id',
        )
        refs = sources.events(
            cast(int, row[field])
            for row in blocks
            for field in ("allocEventId", "freeEventId")
            if type(row[field]) is int and cast(int, row[field]) >= 0
        )
        for block in blocks:
            sources.budget.remaining()
            alloc, free = cast(int, block["allocEventId"]), block["freeEventId"]
            allocation = refs.get(alloc)
            allocation = allocation if allocation and allocation.event["action"] == 4 else None
            completion = refs.get(cast(int, free))
            completion = completion if completion and completion.event["action"] == 6 else None
            proved = allocation is not None
            stable_negative = alloc == -1 and cast(int, block["id"]) < 0
            token = (
                f"alloc:{alloc}"
                if proved
                else (
                    f"preexisting:{block['id']}"
                    if stable_negative
                    else f"unproved:slice:{item.index}:block:{block['id']}"
                )
            )
            identity = f"{sources.namespace}:{token}"
            old = merged.get(identity)
            if old is not None:
                # A shared token with incompatible invariant observations is not
                # evidence to merge by address or guess which allocation wins.
                if any(
                    old[f] != block[f] for f in ("address", "size", "requestedSize", "allocEventId")
                ):
                    raise QueryExecutionError(
                        "Conflicting observations for a proved lifecycle identity."
                    )
                if old["free_source"] and completion and old["freeEventId"] != free:
                    raise QueryExecutionError(
                        "Conflicting free-completion events for one lifecycle."
                    )
                if old["free_source"] and not completion:
                    free = old["freeEventId"]
                    completion_dict = old["free_source"]
                else:
                    completion_dict = completion.to_dict() if completion else None
            else:
                completion_dict = completion.to_dict() if completion else None
            block.update(
                {
                    "lifecycle_id": identity,
                    "identity_status": (
                        "proved_allocation_event"
                        if proved
                        else "stable_negative_token" if stable_negative else "unproved_shard_local"
                    ),
                    "allocation_source": allocation.to_dict() if allocation else None,
                    "allocation_source_status": (
                        "resolved"
                        if proved
                        else "unknown_preexisting" if alloc == -1 else "missing"
                    ),
                    "free_source": completion_dict,
                    "free_source_status": (
                        "resolved"
                        if completion_dict
                        else "live_or_unknown" if free is None or cast(int, free) < 0 else "missing"
                    ),
                    "freeEventId": free,
                    "observation_slice_index": item.index,
                    "state_scope": "latest_slice_observation",
                    "terminal_survivor": item.index == terminal
                    and block["state"] in (0, 1)
                    and (free is None or cast(int, free) < 0),
                    "category": (
                        "dynamic" if alloc >= 0 else "static" if free == -1 else "preexisting"
                    ),
                }
            )
            merged[identity] = block
    rows = list(merged.values())
    for row in rows:
        resolved_alloc += row["allocation_source"] is not None
        resolved_free += row["free_source"] is not None
        unproved += row["identity_status"] == "unproved_shard_local"
    scope["source_coverage"] = {
        "coverage_scope": "all_deduplicated_lifecycles_before_filters_and_page",
        "range_complete": True,
        "lifecycles": len(rows),
        "allocation_events_resolved": resolved_alloc,
        "free_events_resolved": resolved_free,
        "unproved_identities": unproved,
        "allocation_source_complete": all(
            r["allocation_source"] is not None for r in rows if cast(int, r["allocEventId"]) >= 0
        ),
        "source_queries": sources.query_count,
    }
    return rows


def _stacks(sources, low, high, items, params, scope):
    grouped = {}
    events = ordered = 0
    for _item, batch in _traces(sources, low, high, items):
        refs = sources.events(cast(int, r["id"]) for r in batch)
        for source in refs.values():
            sources.budget.remaining()
            text = source.event.get("callstack")
            # Historical alloc_count is ALL stack-bearing real trace actions,
            # including free/segment/workspace. Never claim allocation-only.
            referenced = (
                sources.dataset.callstack_layout == "v2" and source.local_stack_id is not None
            )
            if text is None and source.frames is None and not referenced:
                continue
            identity = source.stack_id
            # Point attribution normalizes empty text into missing; statistics
            # historically count the non-NULL empty string as its own group.
            if text == "" and source.frames is None:
                identity = f"{sources.namespace}:text:sha256:{hashlib.sha256(b'').hexdigest()}"
            row = grouped.setdefault(
                identity,
                {
                    "callstack": text if text is not None else "[missing callstack]",
                    "stack_kind": source.stack_kind,
                    "text_kind": source.text_kind,
                    "alloc_count": 0,
                    "total_size": 0,
                    "max_size": 0,
                    "source_stack_id": identity,
                    "stack_event_id": source.event["id"],
                    "frames_status": source.frames_status,
                },
            )
            row["alloc_count"] += 1
            row["total_size"] += source.event["size"]
            row["max_size"] = max(row["max_size"], source.event["size"])
            if row["text_kind"] != "captured" and source.text_kind == "captured":
                row["callstack"], row["stack_event_id"] = text, source.event["id"]
                row["text_kind"] = "captured"
            events += 1
            ordered += source.frames is not None
    rows = [
        r
        for r in grouped.values()
        if r["alloc_count"] >= params["min_count"] and r["total_size"] >= params["min_size"]
    ]
    for row in rows:
        row["avg_size"] = row["total_size"] / row["alloc_count"]
    rows.sort(
        key=lambda r: (
            -r["total_size"],
            r["callstack"] or "",
            r["stack_kind"] == "missing",
            r["source_stack_id"],
        )
    )
    scope["source_coverage"] = {
        "range_complete": True,
        "coverage_scope": "all_real_stack_bearing_actions_before_global_thresholds",
        "stack_events": events,
        "ordered_frame_events": ordered,
        "source_queries": sources.query_count,
    }
    return rows


def global_query(
    sources: DatasetSourceResolver,
    template: str,
    params: dict[str, object],
    max_rows: int | None,
    exact_total: bool,
    slice_index: int | None,
    semantics_version: int | None,
) -> QueryResult:
    range_params = (
        params if template in ("event", "allocation", "memory_peak", "allocator_gap") else {}
    )
    low, high, items = _range(sources, range_params, slice_index)
    scope = _scope(sources, low, high, items)
    if template in ("memory_peak", "allocator_gap"):
        rows = _peaks(sources, low, high, items, template, scope)
    elif template in ("event", "allocation"):
        rows = _events(sources, low, high, items, params, template, scope)
    elif template == "callstack_analysis":
        rows = _stacks(sources, low, high, items, params, scope)
    elif template == "preexisting_live":
        event = cast(int, params["event_id"])
        item = sources.target(event, slice_index)
        blocks = sources.read(
            sources.dataset.root / item.file,
            f'SELECT COUNT(*) AS block_count, COALESCE(SUM(size),0) AS size_bytes FROM "block_{sources.device.device_id}" WHERE allocEventId=-1 AND (freeEventId IS NULL OR freeEventId> ? OR (freeEventId<0 AND freeEventId!=-1))',
            [event],
        )
        rows = blocks
        scope = _scope(sources, event, event, [item])
    else:
        if template == "leak_detection" and slice_index is not None:
            raise QueryExecutionError(
                "Dataset leak_detection requires terminal dataset scope, not --slice; select an explicit member for local observations."
            )
        rows = _lifecycles(sources, items, scope)
        if template == "block":
            rows = [
                r
                for r in rows
                if _matches(
                    r,
                    params,
                    ("id", "address", "size", "requestedSize", "allocEventId", "freeEventId"),
                )
            ]
            _sort(rows, cast(str, params["order_by"]), params["order_dir"] == "DESC")
        elif template == "leak_detection":
            rows = [
                r
                for r in rows
                if r["terminal_survivor"]
                and r["allocation_source"] is not None
                and cast(int, r["size"]) >= cast(int, params["min_size"])
            ]
            _sort(rows, "size", True)
        elif template == "freed_block_lifetime":
            buckets = {}
            for row in rows:
                if row["allocation_source"] is None or row["free_source"] is None:
                    continue
                distance = cast(int, row["freeEventId"]) - cast(int, row["allocEventId"])
                if distance < 0:
                    continue
                index = next(
                    (i for i, cap in enumerate((1000, 5000, 20000, 100000)) if distance < cap), 4
                )
                bucket = buckets.setdefault(
                    index,
                    {
                        "lifetime_events": ("<1k", "1k-5k", "5k-20k", "20k-100k", ">=100k")[index],
                        "block_count": 0,
                        "size_bytes": 0,
                    },
                )
                bucket["block_count"] += 1
                bucket["size_bytes"] += row["size"]
            rows = [buckets[i] for i in sorted(buckets)]
        else:
            raise QueryExecutionError("No dataset-global merge implementation for this template.")
    total = len(rows)
    offset = max(0, cast(int, params.get("offset", 0)))
    limit = cast(int, params.get("limit", -1))
    if max_rows is not None and max_rows > 0:
        limit = min(limit, max_rows) if limit >= 0 else max_rows
    selected = rows[offset : offset + limit] if limit >= 0 else rows[offset:]
    if template == "event":
        refs = sources.events(cast(int, r["id"]) for r in selected)
        detailed = (
            sources.dataset.ordered_frames_version == 1 or cast(int, params["stack_bytes"]) >= 0
        )
        selected = [dict(refs[cast(int, r["id"])].event) for r in selected]
        if detailed:
            for row in selected:
                source = refs[cast(int, row["id"])]
                row.update(
                    {
                        "source_stack_id": source.stack_id,
                        "stack_id": source.stack_id,
                        "stack_kind": source.stack_kind,
                        "text_kind": source.text_kind,
                        "stack_event_id": row["id"] if source.stack_kind == "captured" else None,
                        "frames": source.frames,
                        "frames_status": source.frames_status,
                    }
                )
        scope["source_coverage"] = {
            "range_complete": True,
            "event_position": "after",
            "coverage_scope": "returned_events",
            "events_resolved": len(refs),
            "ordered_frame_events": sum(s.frames is not None for s in refs.values()),
            "source_queries": sources.query_count,
        }
    elif template == "allocation":
        selected = [{k: r[k] for k in ("id", *METRICS)} for r in selected]
    sources.budget.consume(selected)
    more = total > offset + len(selected)
    return QueryResult(
        total=total if exact_total else len(selected),
        returned=len(selected),
        device_id=sources.device.device_id,
        rows=selected,
        template=template,
        semantics_version=semantics_version,
        has_more=more,
        truncated=more or offset > 0,
        total_is_exact=exact_total or not more and offset == 0,
        timeout_s=sources.budget.timeout_s,
        scope=scope,
    )
