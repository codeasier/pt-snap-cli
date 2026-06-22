from .defs import EventFieldDefs, BlockFieldDefs

from ....base import TraceEntry, Block


def make_default_id_counter(start: int = -1):
    count = start

    def next_id():
        nonlocal count
        current = count
        count -= 1
        return current

    return next_id


def get_timestamp_by_event_idx(event_idx: int) -> int:
    return event_idx * 10 if event_idx is not None else -1


next_default_block_id = make_default_id_counter()
next_default_event_id = make_default_id_counter()


def event2record(
    event: TraceEntry, allocated: int = 0, active: int = 0, reserved: int = 0
) -> dict:
    return {
        EventFieldDefs.ID: (
            event.idx if event.idx is not None else next_default_event_id()
        ),
        EventFieldDefs.ACTION: event.action,
        EventFieldDefs.ADDR: event.addr,
        EventFieldDefs.SIZE: event.size,
        EventFieldDefs.STREAM: event.stream,
        EventFieldDefs.ALLOCATED: allocated,
        EventFieldDefs.ACTIVE: active,
        EventFieldDefs.RESERVED: reserved,
        EventFieldDefs.CALLSTACK: event.get_callstack(),
    }


def block2record(block: Block) -> dict:
    return {
        BlockFieldDefs.ID: (
            block.alloc_event_idx
            if block.alloc_event_idx is not None
            else next_default_block_id()
        ),
        BlockFieldDefs.ADDR: block.address,
        BlockFieldDefs.SIZE: block.size,
        BlockFieldDefs.REQUESTED_SIZE: block.requested_size,
        BlockFieldDefs.STATE: block.state,
        BlockFieldDefs.ALLOC_EVENT_ID: (
            block.alloc_event_idx if block.alloc_event_idx is not None else -1
        ),
        BlockFieldDefs.FREE_EVENT_ID: (
            block.free_event_idx if block.free_event_idx is not None else -1
        ),
    }
