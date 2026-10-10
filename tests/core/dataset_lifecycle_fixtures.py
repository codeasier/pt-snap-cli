"""Deterministic synthetic v1 fixtures with replay-faithful window membership.

These fixtures exercise SQL/query contracts, not the snapshot producer/exporter.
The independent model retains full lifecycle IDs across windows, includes only
carry-in/new allocations, and drops lifetimes completed before a window starts.
"""

import json
import random
import sqlite3
from contextlib import closing

from pt_snap_cli.core.dataset_contract import ACTION_NAMES, BLOCK_STATES, validate_dataset

EVENT_COUNT = 80
CAPACITY = 10
SCHEMA = """CREATE TABLE dictionary ("table" TEXT,"column" TEXT,"key" TEXT,"value" TEXT);
CREATE TABLE trace_entry_0 (id INTEGER PRIMARY KEY, action INTEGER,address INTEGER,size INTEGER,stream INTEGER,allocated INTEGER,active INTEGER,reserved INTEGER,callstack TEXT);
CREATE TABLE block_0 (id INTEGER PRIMARY KEY,address INTEGER,size INTEGER,requestedSize INTEGER,state INTEGER,allocEventId INTEGER,freeEventId INTEGER);"""


def timeline(seed):
    rng = random.Random(seed)
    blocks = {
        -2: {
            "id": -2,
            "address": 900,
            "size": 48,
            "requestedSize": 40,
            "alloc": -1,
            "free": -1,
            "request": -1,
            "stack": None,
        },
        -1: {
            "id": -1,
            "address": 800,
            "size": 96,
            "requestedSize": 80,
            "alloc": -1,
            "free": -1,
            "request": -1,
            "stack": None,
        },
    }
    trace = []
    nextaddr = 2000
    fixed = {
        0: ("a", 1000, "shared"),
        1: ("a", 1100, None),
        2: ("a", 1200, ""),
        3: ("a", 1300, "[missing callstack]"),
        4: ("a", 1400, " \n"),
        17: ("r", -1),
        18: ("f", -1),
        22: ("r", 0),
        23: ("f", 0),
        24: ("a", 1000, "reuse"),
        60: ("r", 24),
        61: ("f", 24),
    }
    protected = {-2, -1, 0, 1, 2, 3, 4, 24}
    for event in range(EVENT_COUNT):
        if event in fixed:
            op = fixed[event]
        else:
            live = [
                b["id"] for b in blocks.values() if b["free"] == -1 and b["id"] not in protected
            ]
            pending = [i for i in live if blocks[i]["request"] >= 0]
            ready = [i for i in live if blocks[i]["request"] == -1]
            coin = rng.random()
            if coin < 0.23 and pending:
                op = ("f", rng.choice(pending))
            elif coin < 0.48 and ready:
                op = ("r", rng.choice(ready))
            elif coin < 0.87:
                available = [
                    b["address"]
                    for b in blocks.values()
                    if b["free"] >= 0
                    and b["address"] >= 2000
                    and all(c["address"] != b["address"] or c["free"] >= 0 for c in blocks.values())
                ]
                address = rng.choice(available) if available and rng.random() < 0.6 else nextaddr
                if address == nextaddr:
                    nextaddr += 100
                op = (
                    "a",
                    address,
                    rng.choice(
                        [
                            "shared",
                            "stack-A",
                            "stack-B",
                            None,
                            "",
                            "[missing callstack]",
                            " \n",
                            "长栈",
                        ]
                    ),
                )
            else:
                op = ("w",)
        kind = op[0]
        if kind == "a":
            size = rng.choice([16, 32, 64, 128, 256])
            req = size - rng.randrange(0, size // 4 + 1)
            blocks[event] = {
                "id": event,
                "address": op[1],
                "size": size,
                "requestedSize": req,
                "alloc": event,
                "free": -1,
                "request": -1,
                "stack": op[2],
            }
            action, address, stack = 4, op[1], op[2]
        elif kind in ("r", "f"):
            b = blocks[op[1]]
            size, address = b["size"], b["address"]
            stack = rng.choice(["free-A", "free-B", None, ""])
            if kind == "r":
                b["request"] = event
                action = 5
            else:
                b["free"] = event
                action = 6
        else:
            action, address, size, stack = 7, 0, 0, rng.choice(["workspace", None, ""])
        alive = [b for b in blocks.values() if b["free"] == -1]
        active = sum(b["size"] for b in alive)
        allocated = sum(b["size"] for b in alive if b["request"] == -1)
        reserved = ((active + 255) // 256) * 256 + 1024
        trace.append(
            (event, action, address, size, rng.choice([0, 1]), allocated, active, reserved, stack)
        )
    return trace, list(blocks.values())


def member(b, lo, hi):
    return (b["alloc"] == -1 or b["alloc"] <= hi) and (b["free"] == -1 or b["free"] >= lo)


def state_at_left(b, lo):
    return 0 if b["request"] >= 0 and b["request"] < lo else 1


def row(b, state):
    return (b["id"], b["address"], b["size"], b["requestedSize"], state, b["alloc"], b["free"])


def db(path, trace, rows, boundary=True):
    with closing(sqlite3.connect(path)) as c, c:
        c.executescript(SCHEMA)
        c.executemany(
            "INSERT INTO dictionary VALUES (?,?,?,?)",
            [("trace_entry_0", "action", str(i), n) for i, n in enumerate(ACTION_NAMES)]
            + [("block_0", "state", str(i), n) for i, n in BLOCK_STATES],
        )
        c.executemany("INSERT INTO trace_entry_0 VALUES (?,?,?,?,?,?,?,?,?)", trace)
        if boundary:
            c.execute(
                "INSERT INTO trace_entry_0 VALUES (-1,2,0,1048576,0,999999,999999,999999,'boundary-excluded')"
            )
        c.executemany("INSERT INTO block_0 VALUES (?,?,?,?,?,?,?)", rows)


def build(out, seed):
    root = out / f"seed-{seed:04d}"
    root.mkdir()
    dataset = root / "dataset"
    (dataset / "device_0").mkdir(parents=True)
    trace, blocks = timeline(seed)
    slices = []
    layout = []
    for i, lo in enumerate(range(0, EVENT_COUNT, CAPACITY)):
        hi = lo + CAPACITY - 1
        rows = [row(b, state_at_left(b, lo)) for b in blocks if member(b, lo, hi)]
        assert all(b[5] == -1 or b[5] <= hi for b in rows)
        assert all(b[6] == -1 or b[6] >= lo for b in rows)
        file = f"device_0/slice_{i:05d}.db"
        db(dataset / file, trace[lo : hi + 1], rows)
        slices.append(
            {"index": i, "startEventId": lo, "endEventId": hi, "file": file, "ready": True}
        )
        layout.append({"slice": i, "lo": lo, "hi": hi, "block_ids": [r[0] for r in rows]})
    manifest = {
        "schemaVersion": 1,
        "status": "complete",
        "sourceFile": "/synthetic/no-pickle",
        "cacheHash": "",
        "eventsPerSlice": CAPACITY,
        "devices": {
            "0": {
                "eventCount": EVENT_COUNT,
                "sliceCount": len(slices),
                "readySlices": list(range(len(slices))),
                "slices": slices,
            }
        },
    }
    (dataset / "manifest.json").write_text(json.dumps(manifest))
    single = root / "single.db"
    # Global block uses latest containing observation, matching its documented state_scope;
    # point-event comparisons exclude stored state, which is not state at requested E.
    finalrows = [
        row(
            b,
            state_at_left(
                b,
                max(
                    i * CAPACITY
                    for i in range(EVENT_COUNT // CAPACITY)
                    if member(b, i * CAPACITY, (i + 1) * CAPACITY - 1)
                ),
            ),
        )
        for b in blocks
    ]
    db(single, trace, finalrows)
    (root / "timeline.json").write_text(
        json.dumps(
            {"seed": seed, "trace": trace, "blocks": blocks, "layout": layout},
            ensure_ascii=False,
            indent=2,
        )
    )
    validate_dataset(dataset)
    return root, dataset, single, trace, blocks


def shapes(seed):
    event = random.Random(seed + 10000).choice(
        [0, 9, 10, 17, 18, 19, 20, 22, 23, 24, 29, 30, 39, 40, 59, 60, 61, 69, 70, 79]
    )
    return [
        ("memory_peak", {}),
        ("memory_peak", {"start_id": 10, "end_id": 61}),
        ("allocator_gap", {}),
        ("allocator_gap", {"start_id": 10, "end_id": 61}),
        ("allocation", {"min_id": 0}),
        (
            "allocation",
            {
                "min_id": 10,
                "max_id": 61,
                "order_by": "active",
                "order_dir": "DESC",
                "limit": 7,
                "offset": 2,
            },
        ),
        ("event", {"min_id": 0}),
        (
            "event",
            {"min_id": 0, "order_by": "callstack", "order_dir": "ASC", "limit": 9, "offset": 2},
        ),
        ("event", {"min_id": 0, "action": 4}),
        ("event", {"id": event}),
        ("block", {}),
        ("block", {"address": 1000}),
        ("block", {"min_size": 32, "order_by": "id", "order_dir": "ASC", "limit": 6, "offset": 2}),
        ("leak_detection", {}),
        ("freed_block_lifetime", {}),
        ("callstack_analysis", {"min_count": 1}),
        ("preexisting_live", {"event_id": event}),
        ("active_blocks_at_event", {"event_id": event}),
        ("active_memory_callstack_at_event", {"event_id": event, "top_n": -1}),
        (
            "active_memory_callstack_at_event",
            {"event_id": event, "top_n": 1, "include_static": False, "min_size": 16},
        ),
    ]
