from logging import Logger
from typing import Dict

from ..base import DeviceSnapshot
from ..util import get_logger

from .allocator_context import AllocatorContext
from .hooker_defs import AllocatorHooker, SimulateHooker
from .replay_executor import ReplayExecutor
from .simulated_caching_allocator import SimulatedCachingAllocator

loading_logger = get_logger("LOAD")
replay_logger = get_logger("REPLAY")


class SimulateDeviceSnapshot:
    device_snapshot: DeviceSnapshot
    hookers: Dict[int, SimulateHooker]

    device: int
    _loading_logger: Logger
    _replay_logger: Logger

    def __init__(self, snapshot_dict: dict, device: int):
        # 基于device初始化logger
        self._loading_logger = loading_logger.getChild(f"{device}")
        self._replay_logger = replay_logger.getChild(f"{device}")
        if not snapshot_dict:
            raise RuntimeError("Cannot init snapshot from empty data.")
        self._loading_logger.info("Loading snapshot data...")
        self.device_snapshot = DeviceSnapshot.from_dict(
            snapshot_dict, device, ignore_inactive_blocks=True
        )
        self._loading_logger.info(
            f"Finished to load snapshot data: total of {len(self.device_snapshot.trace_entries)} "
            f"entries and {len(self.device_snapshot.segments)} segments."
        )
        self.hookers = dict[int, SimulateHooker]()
        self.simulated_allocator_context = AllocatorContext(
            snapshot=self.device_snapshot
        )
        self.simulated_allocator = SimulatedCachingAllocator(
            self.simulated_allocator_context
        )
        self.replay_executor = ReplayExecutor(
            self.simulated_allocator, self._replay_logger
        )
        # 识别昇腾torch-npu采集的snapshot中的workspace事件
        if (
            self.device_snapshot.trace_entries
            and self.device_snapshot.trace_entries[0].action == "workspace_snapshot"
        ):
            self.simulated_allocator_context.workspace_flag = True

    def register_hooker(self, hooker: SimulateHooker) -> int:
        idx = hash(hooker)
        self.hookers[idx] = hooker
        return idx

    def unregister_hooker(self, hooker_id: int):
        if hooker_id in self.hookers:
            del self.hookers[hooker_id]

    def register_allocator_hooker(self, hooker: AllocatorHooker) -> int:
        return self.simulated_allocator.register_hooker(hooker)

    def unregister_allocator_hooker(self, hooker_id: int):
        self.simulated_allocator.unregister_hooker(hooker_id)

    def replay(self) -> bool:
        """
        开始仿真回放内存事件
        """
        # 倒序遍历
        total_size = len(self.device_snapshot.trace_entries)
        self._replay_logger.info(f"Replaying {total_size} entries in snapshot...")
        progress_update_point = [0.25, 0.5, 0.75]
        while self.device_snapshot.trace_entries:
            for hooker in self.hookers.values():
                if hooker and not hooker.pre_undo_event(
                    self.device_snapshot.trace_entries[-1], self.device_snapshot
                ):
                    self._replay_logger.error(
                        "An interruption occurred during the replay of the single event pre hook."
                    )
                    return False
            event = self.device_snapshot.trace_entries[-1]
            self.simulated_allocator_context.set_current_undo_event(event)
            if not self.replay_executor.execute(event):
                self._replay_logger.error(
                    "An interruption occurred during the replay of the single event."
                )
                return False
            self.device_snapshot.trace_entries.pop()
            current_size = len(self.device_snapshot.trace_entries)
            if (
                progress_update_point
                and progress_update_point[-1] * total_size >= current_size
            ):
                self._replay_logger.info(
                    f"{(1 - progress_update_point[-1]) * 100}% of entries have been processed, "
                    f"{current_size} entries remain."
                )
                progress_update_point.pop()
            for hooker in self.hookers.values():
                if hooker and not hooker.post_undo_event(event, self.device_snapshot):
                    self._replay_logger.error(
                        "An interruption occurred during the replay of the single event post hook."
                    )
                    return False
        self._replay_logger.info("All events have been successfully replayed.")
        return True
