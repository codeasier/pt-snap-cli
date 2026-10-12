#!/usr/bin/env python3
"""Parameterized derivative of the successful pinned 101f65b acceptance client.
This derivative was syntax checked only; its business assertions were not rerun.
The client requires an already-loaded GUI project and never imports it.

Run only after the GUI WebSocket has disconnected. This client never launches
the producer or modifies snapshot files directly. Import may cause the server
to add derived SQLite cache tables: point --fixture at a runtime copy.
No project overwrite, conflict retry, deletion, or reparse request is performed.
Process-trace/reuse-log verification is deliberately a separate acceptance step.
"""

import argparse
import asyncio
import contextlib
import datetime as dt
import json
import math
import sys
from pathlib import Path


def now():
    return dt.datetime.now(dt.UTC).isoformat()


class AcceptanceError(RuntimeError):
    pass


class Evidence:
    def __init__(self, args):
        self.output = Path(args.output)
        self.output.mkdir(parents=True, exist_ok=True)
        names = ("requests.jsonl", "messages.jsonl", "checks.json")
        if any((self.output / name).exists() for name in names):
            raise AcceptanceError(
                "Evidence already exists; select a fresh --output directory. Nothing was overwritten."
            )
        self.requests = (self.output / names[0]).open("x", encoding="utf-8")
        self.messages = (self.output / names[1]).open("x", encoding="utf-8")
        self.result = {
            "startedAt": now(),
            "status": "running",
            "uri": args.uri,
            "fixture": args.fixture,
            "project": args.project,
            "skipImport": args.skip_import,
            "sourceRevision": "101f65b877a267ffd5f66ea3834706057ba243e5",
            "checks": [],
            "queryErrors": [],
            "importEvents": [],
            "limitations": [
                "Producer process trace and reuse logs must be checked separately.",
                "Snapshot source/artifact preservation must be checked separately.",
            ],
        }

    @staticmethod
    def append(handle, value):
        handle.write(json.dumps(value, ensure_ascii=False) + "\n")
        handle.flush()

    def check(self, name, actual, expected):
        # bool is an int subclass; protocol booleans must not pass integer checks.
        if isinstance(expected, bool):
            passed = actual is expected
        elif isinstance(expected, int):
            passed = type(actual) is int and actual == expected
        elif isinstance(expected, float):
            passed = type(actual) in (int, float) and math.isclose(
                actual, expected, rel_tol=0, abs_tol=1e-9
            )
        else:
            passed = type(actual) is type(expected) and actual == expected
        self.result["checks"].append(
            {"name": name, "passed": passed, "expected": expected, "actual": actual}
        )
        if not passed:
            raise AcceptanceError(f"{name}: expected {expected!r}, got {actual!r}")

    def finish(self, fatal=None):
        self.result["finishedAt"] = now()
        if fatal:
            self.result["fatalError"] = fatal
        checks = self.result["checks"]
        self.result["passedChecks"] = sum(item["passed"] for item in checks)
        self.result["failedChecks"] = sum(not item["passed"] for item in checks)
        self.result["status"] = (
            "passed"
            if not fatal and not self.result["queryErrors"] and not self.result["failedChecks"]
            else "failed"
        )
        with (self.output / "checks.json").open("x", encoding="utf-8") as handle:
            json.dump(self.result, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        self.requests.close()
        self.messages.close()
        return self.result["status"] == "passed"


class Client:
    def __init__(self, ws, evidence, args):
        self.ws, self.evidence, self.args = ws, evidence, args
        self.pending = {}
        self.events = []
        self.changed = asyncio.Event()
        self.next_id = 1
        self.reader_error = None
        self.task = asyncio.create_task(self.receive())

    async def receive(self):
        try:
            async for raw in self.ws:
                wire = raw.decode("utf-8") if isinstance(raw, bytes) else raw
                try:
                    message = json.loads(wire)
                except (TypeError, ValueError) as exc:
                    Evidence.append(
                        self.evidence.messages,
                        {"at": now(), "wire": wire, "decodeError": str(exc)},
                    )
                    raise AcceptanceError("Received non-JSON WebSocket message") from exc
                Evidence.append(
                    self.evidence.messages,
                    {"at": now(), "wire": wire, "message": message},
                )
                if not isinstance(message, dict):
                    raise AcceptanceError("Received JSON is not a protocol object")
                if message.get("type") == "response":
                    future = self.pending.get(message.get("requestId"))
                    if future is not None and not future.done():
                        future.set_result(message)
                elif message.get("type") == "event":
                    self.events.append(message)
                    self.changed.set()
            self.reader_error = AcceptanceError("Server closed the WebSocket")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.reader_error = exc
        finally:
            if self.reader_error is not None:
                for future in self.pending.values():
                    if not future.done():
                        future.set_exception(self.reader_error)
                self.changed.set()

    async def request(self, label, command, params, module="leaks", include_file=True):
        if self.reader_error:
            raise self.reader_error
        request_id = self.next_id
        self.next_id += 1
        payload = {
            "id": request_id,
            "type": "request",
            "moduleName": module,
            "command": command,
            "projectName": self.args.project,
            "params": params,
        }
        if include_file:
            payload["fileId"] = self.args.fixture
        wire = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        future = asyncio.get_running_loop().create_future()
        self.pending[request_id] = future
        Evidence.append(
            self.evidence.requests,
            {"at": now(), "label": label, "wire": wire, "request": payload},
        )
        try:
            await self.ws.send(wire)
            response = await asyncio.wait_for(future, timeout=self.args.request_timeout)
        finally:
            self.pending.pop(request_id, None)
        self.evidence.check(label + ".requestId", response.get("requestId"), request_id)
        self.evidence.check(label + ".command", response.get("command"), command)
        self.evidence.check(label + ".result", response.get("result"), True)
        return response

    async def wait_import(self, start):
        deadline = asyncio.get_running_loop().time() + self.args.import_timeout
        seen = start
        while True:
            self.changed.clear()
            for event in self.events[seen:]:
                self.evidence.result["importEvents"].append(event)
                body = event.get("body") or {}
                if event.get("event") == "parse/fail":
                    raise AcceptanceError("Snapshot import reported parse/fail; see messages.jsonl")
                if (
                    event.get("event") == "parse/leaksMemoryCompleted"
                    and body.get("module") == "memsnapshot"
                    and body.get("dbPath") == self.args.fixture
                    and body.get("snapshotParsingComplete") is True
                ):
                    slices = body.get("snapshotSlices", {}).get("0", {})
                    self.evidence.check("import.eventCount", slices.get("eventCount"), 8092)
                    self.evidence.check("import.sliceCount", slices.get("sliceCount"), 5)
                    self.evidence.check(
                        "import.readySlices", slices.get("readySlices"), [0, 1, 2, 3, 4]
                    )
                    return
            seen = len(self.events)
            if self.reader_error:
                raise self.reader_error
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise AcceptanceError("Timed out waiting for matching complete snapshot event")
            try:
                await asyncio.wait_for(self.changed.wait(), timeout=remaining)
            except TimeoutError as exc:
                raise AcceptanceError(
                    "Timed out waiting for matching complete snapshot event"
                ) from exc

    async def stop(self):
        self.task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self.task


def require_body(response):
    body = response.get("body")
    if not isinstance(body, dict):
        raise AcceptanceError("Response body is missing or not an object")
    return body


def find_one(items, key, value):
    matches = [item for item in items if item.get(key) == value]
    if len(matches) != 1:
        raise AcceptanceError(f"Expected one {key}={value!r}; got {len(matches)}")
    return matches[0]


async def run_checks(client, evidence):
    check = evidence.check

    async def query(label, suffix, params, validator):
        try:
            response = await client.request(label, "Memory/snapshot/" + suffix, params)
            validator(require_body(response))
        except Exception as exc:
            evidence.result["queryErrors"].append(
                {"query": label, "error": f"{type(exc).__name__}: {exc}"}
            )
            print(f"FAIL {label}: {exc}", flush=True)
        else:
            print(f"PASS {label}", flush=True)

    for index in (0, 1):
        low, high = ((0, 1999), (2000, 3999))[index]
        base = {"deviceId": "0", "sliceIndex": index}

        def bounds(label, body, low=low, high=high):
            check(label + ".minTimestamp", body.get("minTimestamp"), low)
            check(label + ".maxTimestamp", body.get("maxTimestamp"), high)

        def curve(body, index=index, low=low, high=high, bounds=bounds):
            label = f"curve.slice{index}"
            bounds(label, body)
            values = body.get("allocations")
            if not isinstance(values, list) or not values:
                raise AcceptanceError("Allocation curve missing or empty")
            first, last, maximum = (
                (94482944, 419457080, 463470592),
                (419465784, 536562752, 580911104),
            )[index]
            check(label + ".first", values[0], {"timestamp": low, "totalSize": first})
            check(label + ".last", values[-1], {"timestamp": high, "totalSize": last})
            check(label + ".maxSize", body.get("maxSize"), maximum)
            check(
                label + ".allPointsInRange",
                all(
                    type(x.get("timestamp")) is int and low <= x["timestamp"] <= high
                    for x in values
                ),
                True,
            )

        await query(f"curve.slice{index}", "allocations", {**base, "eventType": "malloc"}, curve)

        def reserved(body, index=index, low=low, high=high, bounds=bounds):
            label = f"reserved.slice{index}"
            bounds(label, body)
            values = body.get("reservedLine")
            if not isinstance(values, list) or not values:
                raise AcceptanceError("Reserved curve missing or empty")
            first, last = ((155189248, 463470592), (463470592, 580911104))[index]
            check(label + ".first", values[0], {"timestamp": low, "reservedSize": first})
            check(label + ".last", values[-1], {"timestamp": high, "reservedSize": last})

        await query(
            f"reserved.slice{index}",
            "allocationLines",
            {**base, "eventType": "malloc"},
            reserved,
        )

        boundary = 1999 + index
        address = (20623368406528, 20623368415232)[index]

        def events(
            body, index=index, low=low, high=high, bounds=bounds, boundary=boundary, address=address
        ):
            label = f"events.slice{index}"
            bounds(label, body)
            check(label + ".total", body.get("total"), 2000)
            check(
                label + ".events",
                body.get("events"),
                [
                    {
                        "id": boundary,
                        "action": "alloc",
                        "address": address,
                        "size": 8192,
                        "stream": 1276474240,
                    }
                ],
            )

        await query(
            f"events.slice{index}",
            "events",
            {
                **base,
                "isTable": False,
                "currentPage": 2000 if index == 0 else 1,
                "pageSize": 1,
            },
            events,
        )

        def event_range(
            body, index=index, low=low, high=high, bounds=bounds, boundary=boundary, address=address
        ):
            label = f"range.slice{index}"
            bounds(label, body)
            check(label + ".total", body.get("total"), 1)
            rows = body.get("events", [])
            check(label + ".length", len(rows), 1)
            row = rows[0]
            check(label + ".id", row.get("id"), boundary)
            check(label + ".action", row.get("action"), "alloc")
            check(label + ".address", row.get("address"), address)
            check(label + ".sizeKiB", row.get("size"), 8.0)
            check(
                label + ".headersPresent",
                isinstance(body.get("headers"), list) and bool(body["headers"]),
                True,
            )

        await query(
            f"range.slice{index}",
            "events",
            {
                **base,
                "isTable": True,
                "startTimestamp": 1999,
                "endTimestamp": 2000,
                "currentPage": 1,
                "pageSize": 10,
            },
            event_range,
        )

        def blocks(body, index=index, low=low, high=high, bounds=bounds):
            label = f"blocks.slice{index}"
            bounds(label, body)
            total = (1297, 1489)[index]
            check(label + ".total", body.get("total"), total)
            check(label + ".length", len(body.get("blocks", [])), total)
            block = find_one(body["blocks"], "id", 1669)
            check(
                label + ".crossingBlock",
                block,
                {
                    "id": 1669,
                    "addr": "20623386126336",
                    "size": 37632,
                    "_startTimestamp": (1669, 2000)[index],
                    "_endTimestamp": (1999, 2605)[index],
                    "allocEventId": 1669,
                    "freeEventId": 2605,
                },
            )

        await query(
            f"blocks.slice{index}",
            "blocks",
            {
                **base,
                "eventType": "malloc",
                "isTable": False,
                "currentPage": 1,
                "pageSize": 2000,
            },
            blocks,
        )

        def block_detail(body, index=index, low=low, high=high, bounds=bounds):
            label = f"blockDetail.slice{index}"
            check(label + ".id", body.get("ID"), 1669)
            check(label + ".address", body.get("Address"), "20623386126336")
            for field in ("Requested Size(MBytes)", "Size(MBytes)"):
                check(label + "." + field, body.get(field), 0.036)
            for field, event_id, action in (
                ("Alloc Event", 1669, "alloc"),
                ("Free Completed Event", 2605, "free_completed"),
            ):
                event = body.get(field, {})
                check(label + "." + field + ".id", event.get("ID"), event_id)
                check(label + "." + field + ".action", event.get("Action"), action)
                check(
                    label + "." + field + ".address",
                    event.get("Address"),
                    "0x12c1c19aa800",
                )
                check(label + "." + field + ".stream", event.get("Stream"), 1276474240)
            check(label + ".allocCallStack", body["Alloc Event"].get("CallStack"), "")
            check(
                label + ".freeCallStackNonempty",
                isinstance(body["Free Completed Event"].get("CallStack"), str)
                and bool(body["Free Completed Event"]["CallStack"]),
                True,
            )
            if index == 0:
                check(
                    label + ".freeRequestedCurrentSliceOnly",
                    body.get("Free Requested Event"),
                    {},
                )
            else:
                check(
                    label + ".freeRequestedID",
                    body.get("Free Requested Event", {}).get("ID"),
                    2604,
                )

        await query(
            f"blockDetail.slice{index}",
            "detail",
            {**base, "type": "block", "id": 1669},
            block_detail,
        )

        def cross_event(body, index=index, low=low, high=high, bounds=bounds):
            label = f"crossEvent.slice{index}"
            check(label + ".id", body.get("ID"), (2605, 1669)[index])
            check(
                label + ".action",
                body.get("Action"),
                ("free_completed", "alloc")[index],
            )
            check(label + ".address", body.get("Address"), "0x12c1c19aa800")
            check(label + ".sizeMiB", body.get("Size(MBytes)"), 0.036)

        await query(
            f"crossEvent.slice{index}",
            "detail",
            {**base, "type": "event", "id": (2605, 1669)[index]},
            cross_event,
        )

        def state(body, index=index, low=low, high=high, bounds=bounds):
            label = f"state.slice{index}"
            segments = body.get("segments", [])
            check(label + ".segmentCount", len(segments), 2)
            small = find_one(segments, "address", "0x12c1c0000000")
            large = find_one(segments, "address", "0x12d300000000")
            for segment, size in ((small, 44040192), (large, 419430400)):
                check(
                    label + "." + segment["address"] + ".size",
                    segment.get("size"),
                    size,
                )
                check(
                    label + "." + segment["address"] + ".stream",
                    segment.get("stream"),
                    1276474240,
                )
            check(label + ".smallBlocks", len(small.get("blocks", [])), 688 + index)
            check(label + ".largeBlocks", len(large.get("blocks", [])), 113)
            check(
                label + ".smallAllocated",
                small.get("allocated"),
                (27246136, 27254840)[index],
            )
            check(label + ".largeAllocated", large.get("allocated"), 392210944)
            check(
                label + ".crossingBlock",
                find_one(small["blocks"], "id", 1669),
                {"id": 1669, "size": 37632, "offset": 26912768},
            )
            if index == 0:
                check(
                    label + ".block2000Absent",
                    all(
                        block.get("id") != 2000
                        for segment in segments
                        for block in segment["blocks"]
                    ),
                    True,
                )
            else:
                check(
                    label + ".newBlock2000",
                    find_one(small["blocks"], "id", 2000),
                    {"id": 2000, "size": 8704, "offset": 9201664},
                )

        await query(f"state.slice{index}", "state", {**base, "eventId": boundary}, state)


async def main_async(args, evidence):
    try:
        import websockets
    except ImportError as exc:
        raise AcceptanceError(
            "The websockets package is required; no installation was attempted"
        ) from exc
    async with websockets.connect(
        args.uri,
        open_timeout=args.connect_timeout,
        close_timeout=5,
        max_size=32 * 1024 * 1024,
        ping_interval=20,
        ping_timeout=20,
    ) as ws:
        client = Client(ws, evidence, args)
        try:
            await client.request("readiness", "heartCheck", {}, module="global", include_file=False)
            if not args.skip_import:
                event_start = len(client.events)
                try:
                    await client.request(
                        "import",
                        "import/action",
                        {
                            "projectName": args.project,
                            "projectAction": 1,
                            "path": [args.fixture],
                            "isConflict": False,
                        },
                        module="timeline",
                        include_file=False,
                    )
                    await client.wait_import(event_start)
                except Exception as exc:
                    raise AcceptanceError(
                        f"Import stopped without overwrite or retry: {exc}. If the existing GUI project is already loaded, explicitly use --skip-import --project <known-name>."
                    ) from exc
            await run_checks(client, evidence)
        finally:
            # Keep all import/parse events, including any arriving during queries.
            evidence.result["allEvents"] = list(client.events)
            await client.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uri", default="ws://127.0.0.1:9000/")
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument(
        "--skip-import",
        action="store_true",
        required=True,
        help="Query a known already-loaded project; do not import or transfer it",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Fresh evidence directory; existing evidence is never overwritten",
    )
    parser.add_argument("--connect-timeout", type=float, default=15)
    parser.add_argument("--request-timeout", type=float, default=90)
    parser.add_argument("--import-timeout", type=float, default=180)
    args = parser.parse_args()
    if not Path(args.fixture).is_absolute():
        parser.error("--fixture must be the server's absolute runtime-copy path")
    if min(args.connect_timeout, args.request_timeout, args.import_timeout) <= 0:
        parser.error("Timeouts must be positive")
    import hashlib

    fixture = Path(args.fixture)
    if (
        fixture.stat().st_size != 581140
        or hashlib.sha256(fixture.read_bytes()).hexdigest()
        != "3afc9d1c5ef4ca4b417e58c0830e9eb8a913eb9459f4088b8c66c22325c68c40"
    ):
        parser.error("This oracle is only for the reviewed snapshot_expandable.pkl fixture")
    evidence = None
    fatal = None
    try:
        evidence = Evidence(args)
        asyncio.run(main_async(args, evidence))
    except KeyboardInterrupt:
        fatal = "Interrupted by operator"
    except Exception as exc:
        fatal = f"{type(exc).__name__}: {exc}"
    if evidence is None:
        print(fatal or "Unable to initialize evidence", file=sys.stderr)
        return 1
    success = evidence.finish(fatal)
    print(
        json.dumps(
            {
                "status": evidence.result["status"],
                "passedChecks": evidence.result["passedChecks"],
                "failedChecks": evidence.result["failedChecks"],
                "queryErrors": len(evidence.result["queryErrors"]),
                "fatalError": fatal,
                "results": str(evidence.output / "checks.json"),
            }
        )
    )
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
