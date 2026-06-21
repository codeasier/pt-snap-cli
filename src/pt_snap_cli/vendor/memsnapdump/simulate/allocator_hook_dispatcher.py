import copy
from typing import Dict

from ..base import Block, DeviceSnapshot, Segment

from .hooker_defs import AllocatorHooker


class AllocatorHookDispatcher:
    def __init__(self):
        self.hookers: Dict[int, AllocatorHooker] = {}

    def register_hooker(self, hooker: AllocatorHooker) -> int:
        idx = hash(hooker)
        self.hookers[idx] = hooker
        return idx

    def unregister_hooker(self, hooker_id: int):
        if hooker_id in self.hookers:
            del self.hookers[hooker_id]

    def pre_replay_alloc_block(self, block: Block, snapshot: DeviceSnapshot):
        for hooker in self.hookers.values():
            hooker.pre_replay_alloc_block(block, snapshot)

    def post_replay_alloc_block(self, block: Block, snapshot: DeviceSnapshot):
        for hooker in self.hookers.values():
            hooker.post_replay_alloc_block(block, snapshot)

    def pre_replay_free_block(self, block: Block, snapshot: DeviceSnapshot):
        for hooker in self.hookers.values():
            hooker.pre_replay_free_block(block, snapshot)

    def post_replay_free_block(
        self, block: Block, snapshot: DeviceSnapshot, use_copy: bool = False
    ):
        payload = copy.copy(block) if use_copy else block
        for hooker in self.hookers.values():
            hooker.post_replay_free_block(payload, snapshot)

    def pre_replay_map_or_alloc_segment(
        self, segment: Segment, snapshot: DeviceSnapshot
    ):
        for hooker in self.hookers.values():
            hooker.pre_replay_map_or_alloc_segment(segment, snapshot)

    def post_replay_map_or_alloc_segment(
        self, segment: Segment, snapshot: DeviceSnapshot
    ):
        for hooker in self.hookers.values():
            hooker.post_replay_map_or_alloc_segment(segment, snapshot)

    def pre_replay_unmap_or_free_segment(
        self, segment: Segment, snapshot: DeviceSnapshot
    ):
        for hooker in self.hookers.values():
            hooker.pre_replay_unmap_or_free_segment(segment, snapshot)

    def post_replay_unmap_or_free_segment(
        self, segment: Segment, snapshot: DeviceSnapshot
    ):
        for hooker in self.hookers.values():
            hooker.post_replay_unmap_or_free_segment(segment, snapshot)
