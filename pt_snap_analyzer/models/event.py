"""Memory event data model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pt_snap_analyzer.models._enums import EventType


@dataclass
class MemoryEvent:
    """Represents a memory event from PyTorch snapshot."""

    id: int
    action: EventType
    address: int
    size: int
    stream: int
    allocated: int
    active: int
    reserved: int
    callstack: str | None = None

    @property
    def is_virtual_event(self) -> bool:
        """Check if this is a virtual event (ID < 0)."""
        return self.id < 0

    @property
    def is_runtime_event(self) -> bool:
        """Check if this is a runtime event (ID >= 0)."""
        return self.id >= 0
