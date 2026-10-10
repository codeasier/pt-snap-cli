"""Read-only relational lifecycle reduction over a bounded set of attached shards.

No rows are copied to a merge database. SQLite performs proof, conflict checks,
latest-observation selection and page ranking; only aggregate/page rows cross the
Python boundary. The fetched-row/byte budget does not bound SQLite's internal
scans or temporary space. Summary and page/buckets each evaluate the full CTE;
all statements share the operation deadline. Larger required shard sets keep
the budgeted general implementation.
"""

from __future__ import annotations

import math
import sqlite3
import time
from contextlib import closing
from typing import cast

from pt_snap_cli.core.dataset_contract import SliceRecord
from pt_snap_cli.core.dataset_files import require_readonly_member
from pt_snap_cli.core.dataset_sources import DatasetSourceResolver
from pt_snap_cli.core.errors import QueryExecutionError


class _AttachedSources:
    def __init__(
        self, sources: DatasetSourceResolver, items: list[SliceRecord] | None = None
    ) -> None:
        self.sources = sources
        self.items = sources.device.slices if items is None else items
        remaining = sources.budget.remaining()
        self.connection = sqlite3.connect(
            ":memory:", uri=True, timeout=min(5.0, remaining) if remaining is not None else 5.0
        )
        self.connection.row_factory = sqlite3.Row

    def _configure_deadline(self):
        budget = self.sources.budget
        remaining = budget.remaining()
        deadline = budget.started + budget.timeout_s if budget.timeout_s is not None else None
        self.connection.set_progress_handler(
            (lambda: int(time.monotonic() >= deadline)) if deadline is not None else None, 1000
        )
        # SQLite's default five-second lock wait must not outlive the operation.
        wait_ms = math.ceil(1000 * min(5.0, remaining)) if remaining is not None else 5000
        self.connection.execute(f"PRAGMA busy_timeout={wait_ms}")

    def __enter__(self):
        try:
            self._configure_deadline()
            self.connection.execute("PRAGMA trusted_schema=OFF")
            for item in self.items:
                self._configure_deadline()
                path = self.sources.dataset.root / item.file
                immutable = self.sources.dataset.callstack_layout == "v1"
                require_readonly_member(self.sources.dataset.root, path, immutable=immutable)
                uri = path.as_uri() + "?mode=ro" + ("&immutable=1" if immutable else "")
                self.connection.execute(f'ATTACH DATABASE ? AS "s{item.index}"', [uri])
            self.connection.execute("PRAGMA query_only=ON")
            self.sources.budget.remaining()
            return self
        except BaseException as exc:
            self.connection.set_progress_handler(None, 0)
            self.connection.close()
            if isinstance(exc, sqlite3.Error):
                self.sources.budget.remaining()
                raise QueryExecutionError(str(exc)) from exc
            raise

    def __exit__(self, exc_type, exc_value, traceback):
        self.connection.set_progress_handler(None, 0)
        self.connection.close()
        return False

    def read(self, sql: str, values: list[object] | None = None):
        budget = self.sources.budget
        cursor = self.connection.cursor()
        self.sources.query_count += 1
        try:
            self._configure_deadline()
            cursor.execute(sql, values or [])
            result = []
            while batch := cursor.fetchmany(256):
                rows = [dict(row) for row in batch]
                budget.consume(rows)
                result.extend(rows)
            budget.remaining()
            return result
        except (sqlite3.Error, OverflowError) as exc:
            budget.remaining()  # Preserve the domain timeout on interruption.
            raise QueryExecutionError(str(exc)) from exc
        finally:
            cursor.close()
            self.connection.set_progress_handler(None, 0)


def _attachment_limit() -> int:
    # getlimit is unavailable on supported Python 3.10. Ten is SQLite's default.
    with closing(sqlite3.connect(":memory:")) as connection:
        getter = getattr(connection, "getlimit", None)
        category = getattr(sqlite3, "SQLITE_LIMIT_ATTACHED", None)
        return getter(category) if getter is not None and category is not None else 10


def _required_slices(sources, items, limit):
    """Discover proof owners without fetching individual block/event references."""
    required = {item.index: item for item in items}
    if len(required) > limit:
        return None
    if len(required) == len(sources.device.slices):
        return list(required.values())
    for item in items:
        # Both references may point outside the observation scope. Discover all
        # owners before filtering/pagination so lifecycle conflicts remain visible.
        queries = []
        for field in ("allocEventId", "freeEventId"):
            cases = " ".join(
                f'WHEN "{field}" BETWEEN {owner.start_event_id} AND {owner.end_event_id} '
                f"THEN {owner.index}"
                for owner in sources.device.slices
                if owner.index not in required
            )
            queries.append(
                f"SELECT CASE {cases} END AS owner_index "
                f'FROM "block_{sources.device.device_id}"'
            )
        rows = sources.read(
            sources.dataset.root / item.file,
            "SELECT owner_index FROM (" + " UNION ".join(queries) + ") "
            "WHERE owner_index IS NOT NULL LIMIT ?",
            [limit - len(required) + 1],
        )
        for row in rows:
            owner = sources.device.slices[row["owner_index"]]
            required[owner.index] = owner
        if len(required) > limit:
            return None
        if len(required) == len(sources.device.slices):
            break
    return sorted(required.values(), key=lambda item: item.index)


def _proof(sources, items, field, action):
    device = sources.device.device_id
    cases = " ".join(
        f'WHEN b."{field}" BETWEEN {item.start_event_id} AND {item.end_event_id} '
        f'THEN EXISTS(SELECT 1 FROM "s{item.index}"."trace_entry_{device}" e '
        f'WHERE e.id=b."{field}" AND e.id>=0 AND e.action={action})'
        for item in items
    )
    return f"CASE {cases} ELSE 0 END"


def _lifecycle_cte(sources, items, proof_items):
    allocated = _proof(sources, proof_items, "allocEventId", 4)
    completed = _proof(sources, proof_items, "freeEventId", 6)
    observations = " UNION ALL ".join(
        f"SELECT b.*, {item.index} AS observation_slice_index, "
        f"{allocated} AS allocation_proved, "
        f"CASE WHEN {completed} THEN b.freeEventId END AS completed_free "
        f'FROM "s{item.index}"."block_{sources.device.device_id}" b'
        for item in items
    )
    invariants = ("address", "size", "requestedSize", "allocEventId")
    conflicts = " OR ".join(
        f'(MIN("{column}") IS NOT MAX("{column}") OR '
        f'(COUNT("{column}")>0 AND COUNT("{column}")<COUNT(*)))'
        for column in invariants
    )
    terminal = sources.device.slices[-1].index
    return f"""WITH observations AS ({observations}), identified AS (
        SELECT *, CASE WHEN allocation_proved THEN 'alloc:' || allocEventId
            WHEN allocEventId=-1 AND id<0 THEN 'preexisting:' || id
            ELSE 'unproved:slice:' || observation_slice_index || ':block:' || id
        END AS token FROM observations
    ), history AS (
        SELECT token, MAX(completed_free) AS known_free,
            ({conflicts}) AS invariant_conflict,
            MIN(completed_free) IS NOT MAX(completed_free) AS free_conflict
        FROM identified GROUP BY token
    ), ranked AS (
        SELECT *, ROW_NUMBER() OVER (
            PARTITION BY token ORDER BY observation_slice_index DESC, id DESC
        ) AS observation_rank FROM identified
    ), latest AS (
        SELECT r.id, r.address, r.size, r.requestedSize, r.state, r.allocEventId,
            COALESCE(h.known_free,r.freeEventId) AS freeEventId,
            r.observation_slice_index, r.allocation_proved, r.token,
            h.known_free IS NOT NULL AS completion_proved,
            h.invariant_conflict, h.free_conflict
        FROM ranked r JOIN history h ON h.token=r.token WHERE observation_rank=1
    ), lifecycles AS (
        SELECT *, (observation_slice_index={terminal} AND state IN (0,1)
            AND (freeEventId IS NULL OR freeEventId<0)) AS terminal_survivor
        FROM latest
    ) """


def _filter(template, params):
    if template == "leak_detection":
        return "terminal_survivor AND allocation_proved AND size>=?", [params["min_size"]]
    if template == "freed_block_lifetime":
        return "allocation_proved AND completion_proved AND freeEventId>=allocEventId", []
    clauses, values = [], []
    for field in ("id", "address", "size", "requestedSize", "allocEventId", "freeEventId"):
        for prefix, operator in (("", "="), ("min_", ">="), ("max_", "<=")):
            value = params.get(prefix + field)
            if value is not None:
                clauses.append(f'"{field}" {operator} ?')
                values.append(value)
    return " AND ".join(clauses) or "1", values


def lifecycle_query(sources, items, template, params, scope, candidate_limit):
    required = _required_slices(sources, items, _attachment_limit())
    if required is None:
        return None
    predicate, values = _filter(template, params)
    cte = _lifecycle_cte(sources, items, required)
    with _AttachedSources(sources, required) as database:
        summary = database.read(
            cte + f"""SELECT COUNT(*) AS lifecycles,
                COALESCE(SUM(allocation_proved),0) AS allocation_events_resolved,
                COALESCE(SUM(completion_proved),0) AS free_events_resolved,
                COALESCE(SUM(token LIKE 'unproved:%'),0) AS unproved_identities,
                COALESCE(SUM(allocEventId>=0 AND NOT allocation_proved),0) AS missing_allocations,
                COALESCE(MAX(invariant_conflict),0) AS invariant_conflict,
                COALESCE(MAX(free_conflict),0) AS free_conflict,
                COALESCE(SUM(CASE WHEN {predicate} THEN 1 ELSE 0 END),0) AS matching
                FROM lifecycles""",
            values,
        )[0]
        if summary["invariant_conflict"]:
            raise QueryExecutionError("Conflicting observations for a proved lifecycle identity.")
        if summary["free_conflict"]:
            raise QueryExecutionError("Conflicting free-completion events for one lifecycle.")
        scope["source_coverage"] = {
            "coverage_scope": "all_deduplicated_lifecycles_before_filters_and_page",
            "range_complete": True,
            **{
                key: summary[key]
                for key in (
                    "lifecycles",
                    "allocation_events_resolved",
                    "free_events_resolved",
                    "unproved_identities",
                )
            },
            "allocation_source_complete": not summary["missing_allocations"],
            "source_queries": sources.query_count,
        }
        if template == "freed_block_lifetime":
            buckets = database.read(
                cte + f"""SELECT CASE
                    WHEN freeEventId-allocEventId<1000 THEN 0
                    WHEN freeEventId-allocEventId<5000 THEN 1
                    WHEN freeEventId-allocEventId<20000 THEN 2
                    WHEN freeEventId-allocEventId<100000 THEN 3 ELSE 4 END AS bucket,
                    COUNT(*) AS block_count, SUM(size) AS size_bytes
                    FROM lifecycles WHERE {predicate} GROUP BY bucket ORDER BY bucket""",
                values,
            )
            for row in buckets:
                row["lifetime_events"] = ("<1k", "1k-5k", "5k-20k", "20k-100k", ">=100k")[
                    row.pop("bucket")
                ]
            scope["source_coverage"]["source_queries"] = sources.query_count
            return buckets, len(buckets)
        order = params["order_by"] if template == "block" else "size"
        direction = params["order_dir"] if template == "block" else "DESC"
        rows = database.read(
            cte + f"SELECT * FROM lifecycles WHERE {predicate} "
            f'ORDER BY "{order}" {direction}, id {direction}, token {direction} LIMIT ?',
            [*values, candidate_limit],
        )
    refs = sources.events(
        cast(int, row[field])
        for row in rows
        for field in ("allocEventId", "freeEventId")
        if type(row[field]) is int and cast(int, row[field]) >= 0
    )
    for row in rows:
        alloc, free = row["allocEventId"], row["freeEventId"]
        allocation = refs.get(alloc) if row.pop("allocation_proved") else None
        completion = refs.get(free) if row.pop("completion_proved") else None
        token = row.pop("token")
        row.pop("invariant_conflict")
        row.pop("free_conflict")
        row.update(
            {
                "lifecycle_id": f"{sources.namespace}:{token}",
                "identity_status": (
                    "proved_allocation_event"
                    if allocation
                    else (
                        "stable_negative_token"
                        if token.startswith("preexisting:")
                        else "unproved_shard_local"
                    )
                ),
                "allocation_source": allocation.to_dict() if allocation else None,
                "allocation_source_status": (
                    "resolved"
                    if allocation
                    else ("unknown_preexisting" if alloc == -1 else "missing")
                ),
                "free_source": completion.to_dict() if completion else None,
                "free_source_status": (
                    "resolved"
                    if completion
                    else ("live_or_unknown" if free is None or free < 0 else "missing")
                ),
                "state_scope": "latest_slice_observation",
                "terminal_survivor": bool(row["terminal_survivor"]),
                "category": "dynamic" if alloc >= 0 else "static" if free == -1 else "preexisting",
            }
        )
    scope["source_coverage"]["source_queries"] = sources.query_count
    return rows, summary["matching"]
