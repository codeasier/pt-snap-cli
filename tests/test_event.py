"""Tests for MemoryEvent model."""

from pt_snap_cli.models import EventType, MemoryEvent


class TestMemoryEvent:
    """Test MemoryEvent dataclass."""

    def test_memory_event_creation(self) -> None:
        """Test creating a MemoryEvent instance."""
        event = MemoryEvent(
            id=1,
            action=EventType.ALLOC,
            address=0x12345678,
            size=1024,
            stream=0,
            allocated=1024,
            active=1024,
            reserved=2048,
            callstack="test.py:10",
        )
        assert event.id == 1
        assert event.action == EventType.ALLOC
        assert event.address == 0x12345678
        assert event.size == 1024

    def test_is_virtual_event_negative_id(self) -> None:
        """Test is_virtual_event returns True for negative ID."""
        event = MemoryEvent(
            id=-100,
            action=EventType.ALLOC,
            address=0x0,
            size=0,
            stream=0,
            allocated=0,
            active=0,
            reserved=0,
        )
        assert event.is_virtual_event is True
        assert event.is_runtime_event is False

    def test_is_runtime_event_non_negative_id(self) -> None:
        """Test is_runtime_event returns True for non-negative ID."""
        event = MemoryEvent(
            id=0,
            action=EventType.ALLOC,
            address=0x0,
            size=0,
            stream=0,
            allocated=0,
            active=0,
            reserved=0,
        )
        assert event.is_runtime_event is True
        assert event.is_virtual_event is False

    def test_memory_event_without_callstack(self) -> None:
        """Test creating MemoryEvent without callstack."""
        event = MemoryEvent(
            id=1,
            action=EventType.FREE_REQUESTED,
            address=0x1000,
            size=512,
            stream=1,
            allocated=512,
            active=0,
            reserved=1024,
        )
        assert event.callstack is None
