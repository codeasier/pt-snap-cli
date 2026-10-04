from typing import Any

from ....base import Frame, TraceEntry
from .defs import CallstackFieldDefs


class CallstackInterner:
    """Intern structured frames and their ordered allocation callstacks.

    PyTorch snapshots repeat a small number of callstacks across a very large
    number of events, and the pickle memo already shares the frame containers
    behind them. Interning therefore turns the per-event callstack into an
    integer reference and keeps a single text copy per distinct callstack.

    The identity fast path retains frame containers to prevent object-id reuse.
    Value keys preserve filename, line and name independently: display text is
    not a lossless identity. Frame positions retain the snapshot's original
    order; the existing outermost-first text remains available to old readers.
    """

    def __init__(self) -> None:
        self._by_frames: dict[tuple[int, ...], tuple[object, int]] = {}
        self._by_stack: dict[tuple[int, ...], int] = {}
        self._by_frame: dict[tuple[str, int, str], int] = {}
        self._frames: list[dict[str, Any]] = []
        self._stacks: list[tuple[int, ...]] = []
        self._texts: list[str] = []

    def intern(self, event: TraceEntry) -> int:
        """Return the callstack id for ``event``, rendering text only on a miss."""
        frames = event.callstack_frames()
        frame_key = tuple(map(id, frames))
        by_frames = self._by_frames.get(frame_key)
        if by_frames is not None:
            callstack_id = by_frames[1]
        else:
            frame_ids = []
            for frame in frames:
                key: tuple[str, int, str] = (
                    (frame.filename, frame.line, frame.name)
                    if isinstance(frame, Frame)
                    else (frame["filename"], frame["line"], frame["name"])
                )
                frame_id = self._by_frame.get(key)
                if frame_id is None:
                    frame_id = len(self._frames)
                    self._by_frame[key] = frame_id
                    self._frames.append(
                        {"id": frame_id, "filename": key[0], "line": key[1], "name": key[2]}
                    )
                frame_ids.append(frame_id)
            stack = tuple(frame_ids)
            existing = self._by_stack.get(stack)
            if existing is None:
                callstack_id = len(self._texts)
                self._texts.append(event.get_callstack())
                self._stacks.append(stack)
                self._by_stack[stack] = callstack_id
            else:
                callstack_id = existing
            self._by_frames[frame_key] = (frames, callstack_id)

        return callstack_id

    def records(self) -> list[dict[str, Any]]:
        """Return one record per distinct callstack, ordered by id."""
        return [
            {CallstackFieldDefs.ID: callstack_id, CallstackFieldDefs.CALLSTACK: text}
            for callstack_id, text in enumerate(self._texts)
        ]

    def __len__(self) -> int:
        return len(self._texts)

    def frame_records(self) -> list[dict[str, Any]]:
        """Return deduplicated original frame fields shared by all devices."""
        return self._frames.copy()

    def stack_frame_records(self) -> list[dict[str, Any]]:
        """Return ordered frame references, including repeated recursive frames."""
        return [
            {"callstackId": stack_id, "position": position, "frameId": frame_id}
            for stack_id, stack in enumerate(self._stacks)
            for position, frame_id in enumerate(stack)
        ]
