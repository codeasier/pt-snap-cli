"""Memory block data model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pt_snap_analyzer.models._enums import BlockState


@dataclass
class MemoryBlock:
    """Represents a memory block from PyTorch snapshot."""

    id: int
    address: int
    size: int
    requested_size: int
    state: BlockState
    alloc_event_id: int | None = None
    free_event_id: int | None = None

    @property
    def is_historical_block(self) -> bool:
        """Check if this is a historical block (ID < 0)."""
        return self.id < 0

    @property
    def is_active(self) -> bool:
        """Check if this block is still active (not freed)."""
        return self.free_event_id is None or self.free_event_id == -1
