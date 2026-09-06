from ....base import TraceEntry
from .defs import CallstackFieldDefs


class CallstackInterner:
    """Assign one integer id per distinct callstack text.

    PyTorch snapshots repeat a small number of callstacks across a very large
    number of events, and the pickle memo already shares the frame containers
    behind them. Interning therefore turns the per-event callstack into an
    integer reference and keeps a single text copy per distinct callstack.

    Lookups use the identities of the individual frames and only render text
    on a miss. Distinct containers that render to the same text collapse onto
    one id, so the id-to-text mapping stays one-to-one and grouping by id
    matches grouping by text.
    """

    def __init__(self) -> None:
        self._by_frames: dict[tuple[int, ...], tuple[object, int]] = {}
        self._by_text: dict[str, int] = {}
        self._texts: list[str] = []

    def intern(self, event: TraceEntry) -> int:
        """Return the callstack id for ``event``, rendering text only on a miss."""
        frames = event.callstack_frames()
        frame_key = tuple(map(id, frames))
        by_frames = self._by_frames.get(frame_key)
        if by_frames is not None:
            callstack_id = by_frames[1]
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

    def records(self) -> list[dict]:
        """Return one record per distinct callstack, ordered by id."""
        return [
            {CallstackFieldDefs.ID: callstack_id, CallstackFieldDefs.CALLSTACK: text}
            for callstack_id, text in enumerate(self._texts)
        ]

    def __len__(self) -> int:
        return len(self._texts)
