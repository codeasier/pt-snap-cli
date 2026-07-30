from ..base import DeviceSnapshot, TraceEntry


class AllocatorContext:
    def __init__(self, snapshot: DeviceSnapshot):
        self.device_snapshot = snapshot
        self.current_undo_event: TraceEntry = None
        self.workspace_flag = False

    def set_current_undo_event(self, undo_event: TraceEntry):
        self.current_undo_event = undo_event
