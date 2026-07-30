from pathlib import Path

from ...base import Block, BlockState, DeviceSnapshot, TraceEntry
from ...representation import load_snapshot_representation, replay_snapshot
from ...simulate import AllocatorHooker, SimulateHooker
from ...util.logger import get_logger, set_global_log_file
from .database import SnapshotDb, block2record, event2record

dump_logger = get_logger("DatabaseDump")


class SnapshotDbHandler:
    def __init__(self, db_path: str, devices: list[int], insert_cache_size: int = 1000):
        self.db_path = db_path
        self.db = SnapshotDb(db_path)
        self._device_event_cache = {}
        self._device_block_cache = {}
        self._insert_cache_size = insert_cache_size
        for device in devices:
            self._device_block_cache[device] = []
            self._device_event_cache[device] = []
            self.db.create_trace_entry_table(device)
            self.db.create_block_table(device)

    def insert_event(self, event_record: dict, device: int = 0):
        if device not in self._device_event_cache:
            self._device_event_cache[device] = []
        self._device_event_cache[device].append(event_record)
        if len(self._device_event_cache[device]) >= self._insert_cache_size:
            self._do_insert_events(device)

    def insert_block(self, block_record: dict, device: int = 0):
        if device not in self._device_block_cache:
            self._device_block_cache[device] = []
        self._device_block_cache[device].append(block_record)
        if len(self._device_block_cache[device]) >= self._insert_cache_size:
            self._do_insert_blocks(device)

    def flush(self, device: int = 0):
        if self._device_event_cache.get(device, None):
            self._do_insert_events(device)
        if self._device_block_cache.get(device, None):
            self._do_insert_blocks(device)

    def _do_insert_events(self, device: int = 0):
        if device not in self._device_event_cache:
            self._device_event_cache[device] = []
            return
        self.db.get_trace_entry_table(device).insert_records(
            self.db.conn, self._device_event_cache[device]
        )
        self.db.conn.commit()
        self._device_event_cache[device].clear()

    def _do_insert_blocks(self, device: int = 0):
        if device not in self._device_block_cache:
            self._device_block_cache[device] = []
        self.db.get_block_table(device).insert_records(
            self.db.conn, self._device_block_cache[device]
        )
        self.db.conn.commit()
        self._device_block_cache[device].clear()

    def __del__(self):
        self.db.conn.commit()
        self.db.conn.close()


class DumpEventHooker(SimulateHooker, AllocatorHooker):
    def __init__(self, db_path: str, devices: list[int], dump_cache_size: int = 1000):
        self.db_handler = SnapshotDbHandler(db_path, devices, insert_cache_size=dump_cache_size)

    def post_undo_event(
        self, already_undo_event: TraceEntry, current_snapshot: DeviceSnapshot
    ) -> bool:
        # 回放完毕，dump剩余Segment及block数据, 注意应该先插入blocks
        if not current_snapshot.trace_entries:
            for seg in current_snapshot.segments:
                for block in seg.blocks:
                    if block.state != BlockState.INACTIVE:
                        self.db_handler.insert_block(block2record(block), current_snapshot.device)
                # segment不插入block表，而是以模拟事件插入事件表，便于后续重建segment
                mock_segment_alloc_event = TraceEntry(
                    idx=None,
                    action="segment_map" if seg.is_expandable else "segment_alloc",
                    addr=seg.address,
                    frames=seg.frames,
                    size=seg.total_size,
                    stream=seg.stream,
                )
                self.db_handler.insert_event(
                    event2record(
                        event=mock_segment_alloc_event,
                        allocated=current_snapshot.total_allocated,
                        active=current_snapshot.total_activated,
                        reserved=current_snapshot.total_reserved,
                    ),
                    current_snapshot.device,
                )
        return True

    def pre_undo_event(self, wait4undo_event: TraceEntry, current_snapshot: DeviceSnapshot) -> bool:
        # 每个事件回放前dump一次event
        self.db_handler.insert_event(
            event2record(
                event=wait4undo_event,
                allocated=current_snapshot.total_allocated,
                active=current_snapshot.total_activated,
                reserved=current_snapshot.total_reserved,
            ),
            current_snapshot.device,
        )
        return True

    def post_replay_free_block(self, released_block: Block, current_snapshot: DeviceSnapshot):
        self.db_handler.insert_block(block2record(released_block), current_snapshot.device)

    def flush(self, device: int = 0):
        self.db_handler.flush(device)


def dump(pickle_file: str, dump_file: str, device=None) -> bool:
    try:
        data = load_snapshot_representation(Path(pickle_file))
    except Exception as e:
        dump_logger.error(f"Failed to load pickle file: {e}")
        return False
    device_traces = data.get("device_traces", [])
    # 当指定device为空时dump所有记录了跟踪事件的device，否则仅dump指定device
    need_dump_devices = [device for device in range(len(device_traces)) if device_traces[device]]
    dump_logger.info(f"Recognized have trace events devices {need_dump_devices}.")
    if device is not None and device not in need_dump_devices:
        dump_logger.error(
            f"Specified device {device} is not found or has no trace events in the snapshot."
        )
        return False
    if device is not None:
        need_dump_devices = [device]
    dump_logger.info(f"Recognized need to dump devices {need_dump_devices}.")
    hooker = DumpEventHooker(dump_file, need_dump_devices)
    for device in need_dump_devices:
        dump_logger.info(f"Start to dump the snapshot to database for device {device}.")
        _, replayed = replay_snapshot(
            data,
            device,
            hooker=hooker,
            allocator_hooker=hooker,
        )
        if not replayed:
            dump_logger.error(f"Failed to dump the snapshot to database for device {device}.")
            return False
        dump_logger.info(f"Finished dump the snapshot to database for device {device}.")
        hooker.flush(device)
    dump_logger.info(f"Successfully dump the snapshot to database for devices {need_dump_devices}.")
    return True


def run_dump_to_db(
    snapshot_file: str,
    dump_dir: str = "",
    device: int | None = None,
    log_file: str = "",
) -> bool:
    resolved_dump_dir = dump_dir or str(Path(snapshot_file).parent)
    if log_file:
        set_global_log_file(log_file)

    return dump(
        snapshot_file,
        Path(resolved_dump_dir) / f"{Path(snapshot_file).name}.db",
        device,
    )
