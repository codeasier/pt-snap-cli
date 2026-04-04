"""Enum types for memory events and block states."""

from enum import IntEnum


class EventType(IntEnum):
    """Memory event types for PyTorch snapshot tracking."""

    SEGMENT_MAP = 0
    SEGMENT_UNMAP = 1
    SEGMENT_ALLOC = 2
    SEGMENT_FREE = 3
    ALLOC = 4
    FREE_REQUESTED = 5
    FREE_COMPLETED = 6
    WORKSPACE_SNAPSHOT = 7


class BlockState(IntEnum):
    """Memory block states."""

    INACTIVE = -1
    ACTIVE_PENDING_FREE = 0
    ACTIVE_ALLOCATED = 1
    UNKNOWN = 99
