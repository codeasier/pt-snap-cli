from collections.abc import Mapping, Sequence
from typing import Any

from ....base import Frame, TraceEntry
from .defs import CallstackFieldDefs


class CallstackInterner:
    """Intern callstacks by text, or opt into standalone structured identity.

    Native writers retain one id per distinct rendered text. Standalone v3
    writers explicitly use original frame fields and order instead, since text
    can contain delimiters that make different frame sequences look identical.
    Identity fast paths retain frame containers to prevent object-id reuse.
    """

    def __init__(self, *, structured_frames: bool = False) -> None:
        self._structured_frames: bool = structured_frames
        self._by_frames: dict[tuple[int, ...], tuple[object, int]] = {}
        self._by_text: dict[str, int] = {}
        self._by_stack: dict[tuple[int, ...], int] = {}
        self._by_frame: dict[tuple[str, int, str], int] = {}
        self._frames: list[dict[str, object]] = []
        self._stacks: list[tuple[int, ...]] = []
        self._texts: list[str] = []

    def intern(self, event: TraceEntry) -> int:
        """Return the callstack id for ``event``, rendering text only on a miss."""
        frames = event.callstack_frames()
        frame_key = tuple(map(id, frames))
        by_frames = self._by_frames.get(frame_key)
        if by_frames is not None:
            return by_frames[1]
        if self._structured_frames:
            callstack_id = self._intern_structured(event, frames)
        else:
            text = event.get_callstack()
            existing = self._by_text.get(text)
            if existing is None:
                callstack_id = len(self._texts)
                self._texts.append(text)
                self._by_text[text] = callstack_id
            else:
                callstack_id = existing
        self._by_frames[frame_key] = (frames, callstack_id)
        return callstack_id

    @staticmethod
    def _frame_key(frame: Frame | Mapping[str, object]) -> tuple[str, int, str]:
        filename, line, name = (
            (frame.filename, frame.line, frame.name)
            if isinstance(frame, Frame)
            else (frame["filename"], frame["line"], frame["name"])
        )
        # SQLite INTEGER affinity coerces bool/float/string values. Reject those
        # here rather than lose their types or conflate True, 1 and 1.0 as keys.
        # Keep this stricter standalone-v3 contract out of native text imports.
        if not isinstance(filename, str) or type(line) is not int or not isinstance(name, str):
            raise ValueError(
                "Structured frames require string filename/name and integer line (not bool)."
            )
        return filename, line, name

    def _intern_structured(
        self, event: TraceEntry, frames: Sequence[Frame | Mapping[str, object]]
    ) -> int:
        keys = [self._frame_key(frame) for frame in frames]
        frame_ids: list[int] = []
        for key in keys:
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
        if existing is not None:
            return existing
        callstack_id = len(self._texts)
        self._texts.append(event.get_callstack())
        self._stacks.append(stack)
        self._by_stack[stack] = callstack_id
        return callstack_id

    def records(self) -> list[dict[str, Any]]:
        """Return one record per distinct callstack, ordered by id."""
        return [
            {CallstackFieldDefs.ID: callstack_id, CallstackFieldDefs.CALLSTACK: text}
            for callstack_id, text in enumerate(self._texts)
        ]

    def __len__(self) -> int:
        return len(self._texts)

    def frame_records(self) -> list[dict[str, object]]:
        """Return deduplicated original frame fields for a structured interner."""
        return self._frames.copy()

    def stack_frame_records(self) -> list[dict[str, int]]:
        """Return original-order references, including repeated recursive frames."""
        return [
            {"callstackId": stack_id, "position": position, "frameId": frame_id}
            for stack_id, stack in enumerate(self._stacks)
            for position, frame_id in enumerate(stack)
        ]

    def stack_manifest_records(self) -> list[dict[str, int]]:
        """Attest every captured stack's size, including genuinely empty stacks."""
        return [
            {"callstackId": stack_id, "frameCount": len(stack)}
            for stack_id, stack in enumerate(self._stacks)
        ]
