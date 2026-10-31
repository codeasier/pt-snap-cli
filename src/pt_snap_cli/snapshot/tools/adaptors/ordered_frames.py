"""Deduplicated, optional frame evidence independent of native text stack IDs."""

import json
import sqlite3

from ...base import Frame, TraceEntry


class OrderedFrameWriter:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        connection.executescript(
            "CREATE TABLE pt_snap_frame_value (id INTEGER PRIMARY KEY, frameJson TEXT);"
            "CREATE TABLE pt_snap_stack (stackId INTEGER PRIMARY KEY, frameCount INTEGER);"
            "CREATE TABLE pt_snap_stack_frame (stackId INTEGER, frameIndex INTEGER, frameId INTEGER,"
            " PRIMARY KEY(stackId,frameIndex));"
            "CREATE TABLE pt_snap_event_stack (eventId INTEGER PRIMARY KEY, stackId INTEGER);"
        )
        self.frames: dict[str, int] = {}
        self.stacks: dict[tuple[int, ...], int] = {}
        self.containers: dict[tuple[int, ...], tuple[object, int]] = {}

    def insert(self, event: TraceEntry) -> None:
        if event.idx is None or event.idx < 0:
            return
        frames = event.callstack_frames()
        key = tuple(map(id, frames))
        cached = self.containers.get(key)
        if cached is not None:
            stack_id = cached[1]
        else:
            try:
                encoded = [
                    json.dumps(
                        frame.to_dict() if isinstance(frame, Frame) else frame,
                        sort_keys=True,
                        ensure_ascii=True,
                        separators=(",", ":"),
                        allow_nan=False,
                    )
                    for frame in frames
                ]
            except (ValueError, TypeError, RecursionError, OverflowError):
                # Optional evidence must not change acceptance of native text inputs.
                return
            ids = []
            for value in encoded:
                if value not in self.frames:
                    frame_id = len(self.frames)
                    self.frames[value] = frame_id
                    self.connection.execute(
                        "INSERT INTO pt_snap_frame_value VALUES (?,?)", (frame_id, value)
                    )
                ids.append(self.frames[value])
            stack = tuple(ids)
            if stack not in self.stacks:
                stack_id = len(self.stacks)
                self.stacks[stack] = stack_id
                self.connection.execute(
                    "INSERT INTO pt_snap_stack VALUES (?,?)", (stack_id, len(stack))
                )
                self.connection.executemany(
                    "INSERT INTO pt_snap_stack_frame VALUES (?,?,?)",
                    [(stack_id, index, frame_id) for index, frame_id in enumerate(stack)],
                )
            stack_id = self.stacks[stack]
            self.containers[key] = (frames, stack_id)
        self.connection.execute(
            "INSERT INTO pt_snap_event_stack VALUES (?,?)", (event.idx, stack_id)
        )
