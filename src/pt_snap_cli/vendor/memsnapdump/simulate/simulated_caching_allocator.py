import copy

from ..base import BlockState, Block, Segment, TraceEntry
from ..util import get_logger

from .allocator_context import AllocatorContext
from .allocator_hook_dispatcher import AllocatorHookDispatcher
from . import snapshot_lookup, snapshot_mutator

allocator_logger = get_logger("ALLOCATOR")


class SimulatedCachingAllocator:
    def __init__(self, ctx: AllocatorContext):
        self.ctx = ctx
        self.dispatcher = AllocatorHookDispatcher()

    def register_hooker(self, hooker) -> int:
        return self.dispatcher.register_hooker(hooker)

    def unregister_hooker(self, hooker_id: int):
        self.dispatcher.unregister_hooker(hooker_id)

    def alloc_block(self, new_block: Block) -> bool:
        """
            回放时模拟分配一个新的block
        :param new_block: 待分配的block
        """
        _error = "Failed to simulate alloc block"
        gap_result = snapshot_lookup.find_gap_for_alloc_block(
            self.ctx.device_snapshot,
            new_block.address,
            new_block.size,
            self.ctx.current_undo_event.stream if self.ctx.current_undo_event else None,
        )
        if gap_result is None:
            allocator_logger.error(
                f"{_error}: cannot find gap for block (addr={new_block.address}, size={new_block.size})"
            )
            return False
        segment, insert_idx = gap_result
        if self.ctx.current_undo_event:
            new_block.free_event_idx = self.ctx.current_undo_event.idx
        if (
            self.ctx.current_undo_event
            and self.ctx.current_undo_event.action == "free_completed"
        ):
            new_block.state = BlockState.ACTIVE_PENDING_FREE
        else:
            new_block.state = BlockState.ACTIVE_ALLOCATED
        self.dispatcher.pre_replay_alloc_block(new_block, self.ctx.device_snapshot)
        snapshot_mutator.attach_block(
            self.ctx.device_snapshot, segment, new_block, insert_idx
        )
        self.dispatcher.post_replay_alloc_block(new_block, self.ctx.device_snapshot)
        return True

    def free_block(self, alloc_event: TraceEntry) -> bool:
        """
            回放时模拟释放一个block，可能涉及到拆分合并
        :param alloc_event: 待回滚的alloc事件
        """
        _error = "Failed to simulate free block"
        seg_idx, segment = snapshot_lookup.find_overlapping_segment(
            self.ctx.device_snapshot, alloc_event.addr, alloc_event.stream
        )
        if seg_idx == -1 or segment is None:
            allocator_logger.error(
                f"{_error}: cannot find segment for block (addr={alloc_event.addr})"
            )
            return False
        block_idx, exist_block = snapshot_lookup.find_block(segment, alloc_event.addr)
        if block_idx == -1 or exist_block is None:
            # workspace场景容忍
            if self.ctx.workspace_flag:
                allocator_logger.warning(
                    f"{_error}: cannot find block (addr={alloc_event.addr}), workspace scenario tolerance"
                )
                return True
            allocator_logger.error(
                f"{_error}: cannot find block (addr={alloc_event.addr})"
            )
            return False
        if exist_block.size < alloc_event.size:
            allocator_logger.error(
                f"{_error}: block size ({exist_block.size}) < event size ({alloc_event.size})"
            )
            return False
        exist_block.alloc_event_idx = alloc_event.idx
        self.dispatcher.pre_replay_free_block(exist_block, self.ctx.device_snapshot)
        if not snapshot_mutator.detach_block(self.ctx.device_snapshot, exist_block):
            allocator_logger.error(f"{_error}: block has no segment_ptr")
            return False
        self.dispatcher.post_replay_free_block(
            exist_block, self.ctx.device_snapshot, use_copy=True
        )
        return True

    def active_block(self, free_requested_event: TraceEntry) -> bool:
        """
            回放时模拟active一个block
        :param free_requested_event: 待回放的free_requested请求
        """
        _error = "Failed to simulate active block"
        seg_idx, segment = snapshot_lookup.find_overlapping_segment(
            self.ctx.device_snapshot,
            free_requested_event.addr,
            free_requested_event.stream,
        )
        if seg_idx == -1 or segment is None:
            allocator_logger.error(
                f"{_error}: cannot find segment for block (addr={free_requested_event.addr})"
            )
            return False
        block_idx, active_pending_free_block = snapshot_lookup.find_block(
            segment, free_requested_event.addr
        )
        if block_idx == -1 or active_pending_free_block is None:
            allocator_logger.error(
                f"{_error}: cannot find block (addr={free_requested_event.addr})"
            )
            return False
        if active_pending_free_block.state != BlockState.ACTIVE_PENDING_FREE:
            # workspace场景容忍异常
            if self.ctx.workspace_flag:
                allocator_logger.warning(
                    f"{_error}: block (addr={free_requested_event.addr}) is not in {BlockState.ACTIVE_PENDING_FREE} state, "
                    f"but workspace_flag is True, skipping"
                )
                return True
            allocator_logger.error(
                f"{_error}: block (addr={free_requested_event.addr}) is not in {BlockState.ACTIVE_PENDING_FREE} state, "
                f"current state: {active_pending_free_block.state}"
            )
            return False
        if not snapshot_mutator.promote_pending_free_block(
            self.ctx.device_snapshot, active_pending_free_block
        ):
            allocator_logger.error(
                f"{_error}: the found active pending block's segment is none."
            )
            return False
        return True

    def alloc_or_map_segment(self, new_segment: Segment, merge: bool = False) -> bool:
        """
            回放时模拟alloc或map一个新的内存段
        :param new_segment: 新内存段
        :param merge: 是否合并，map时对应虚拟内存场景，否则仅为alloc
        """
        _error = "Failed to alloc or map segment"
        segments = self.ctx.device_snapshot.segments
        self.dispatcher.pre_replay_map_or_alloc_segment(
            new_segment, self.ctx.device_snapshot
        )
        if self.ctx.current_undo_event:
            new_segment.free_or_unmap_event_idx = self.ctx.current_undo_event.idx
        if not merge:
            snapshot_mutator.insert_segment(self.ctx.device_snapshot, new_segment)
            self.dispatcher.post_replay_map_or_alloc_segment(
                new_segment, self.ctx.device_snapshot
            )
            return True
        new_seg_start = new_segment.address
        new_seg_end = new_seg_start + new_segment.total_size
        left_adjacent_idx = -1
        right_adjacent_idx = -1
        for i, seg in enumerate(segments):
            if seg.stream != new_segment.stream:
                continue
            if seg.address + seg.total_size == new_seg_start:
                left_adjacent_idx = i
            elif new_seg_end == seg.address:
                right_adjacent_idx = i
        if left_adjacent_idx == -1 and right_adjacent_idx == -1:
            snapshot_mutator.insert_segment(self.ctx.device_snapshot, new_segment)
            self.dispatcher.post_replay_map_or_alloc_segment(
                new_segment, self.ctx.device_snapshot
            )
            return True
        virtual_map_segment = copy.deepcopy(new_segment)
        if not snapshot_mutator.merge_mapped_segment(
            self.ctx.device_snapshot,
            new_segment,
            left_adjacent_idx,
            right_adjacent_idx,
        ):
            allocator_logger.error(f"{_error}: failed to merge adjacent segments")
            return False
        snapshot_mutator.increase_reserved(
            self.ctx.device_snapshot, virtual_map_segment.total_size
        )
        self.dispatcher.post_replay_map_or_alloc_segment(
            virtual_map_segment, self.ctx.device_snapshot
        )
        return True

    def free_segment(self, alloc_seg_event: TraceEntry) -> bool:
        """
            回放时模拟free一个内存段（非虚拟内存场景）
        :param alloc_seg_event: 待回滚的alloc事件
        """
        _error = "Free segment failed"
        seg_addr = alloc_seg_event.addr
        exist_seg_idx, exist_seg = snapshot_lookup.find_segment(
            self.ctx.device_snapshot, seg_addr, alloc_seg_event.stream
        )
        if exist_seg_idx == -1 or exist_seg is None:
            allocator_logger.error(
                f"{_error}: cannot found segment(addr={seg_addr}, stream={alloc_seg_event.stream})"
            )
            return False
        if exist_seg.total_size != alloc_seg_event.size:
            allocator_logger.error(
                f"{_error}: cannot free segment(addr={seg_addr}, size={alloc_seg_event.size}) in "
                f"exist segment(addr={exist_seg.address}, size={exist_seg.total_size})"
            )
            return False
        if exist_seg.active_size > 0:
            allocator_logger.error(
                f"{_error}: cannot free a segment that still has active allocations."
            )
            return False

        exist_seg.alloc_or_map_event_idx = alloc_seg_event.idx
        self.dispatcher.pre_replay_unmap_or_free_segment(
            exist_seg, self.ctx.device_snapshot
        )
        snapshot_mutator.remove_segment(self.ctx.device_snapshot, exist_seg)
        self.dispatcher.post_replay_unmap_or_free_segment(
            exist_seg, self.ctx.device_snapshot
        )
        return True

    def unmap_segment(self, map_event):
        """
            回放时模拟unmap一个已有的内存段（虚拟内存场景）
        :param map_event: 待回滚的map事件
        """
        _error = "Unmap segment failed"
        segments = self.ctx.device_snapshot.segments
        virtual_free_segment = Segment.build_from_event(map_event)
        seg_addr = virtual_free_segment.address
        unmap_size = virtual_free_segment.total_size
        exist_seg_idx, exist_seg = snapshot_lookup.find_overlapping_segment(
            self.ctx.device_snapshot, seg_addr, map_event.stream
        )
        if exist_seg_idx < 0 or exist_seg is None or exist_seg_idx >= len(segments):
            allocator_logger.error(f"{_error}: cannot found segment(addr={seg_addr})")
            return False
        virtual_free_segment.free_or_unmap_event_idx = exist_seg.free_or_unmap_event_idx
        virtual_free_segment.alloc_or_map_event_idx = map_event.idx
        if not (
            seg_addr >= exist_seg.address
            and seg_addr + unmap_size <= exist_seg.address + exist_seg.total_size
        ):
            allocator_logger.error(
                f"{_error}: cannot unmap segment(addr={seg_addr}, unmap_size={unmap_size}) in exist segment("
                f"addr={exist_seg.address}, total_size={exist_seg.total_size})"
            )
            return False
        self.dispatcher.pre_replay_unmap_or_free_segment(
            virtual_free_segment, self.ctx.device_snapshot
        )
        if exist_seg.stream != map_event.stream:
            allocator_logger.error(
                f"{_error}: stream mismatch (segment: {exist_seg.stream}, event: {map_event.stream})"
            )
            return False
        if not snapshot_mutator.split_or_shrink_segment(
            self.ctx.device_snapshot, exist_seg_idx, seg_addr, unmap_size
        ):
            allocator_logger.error(f"{_error}: failed to split or shrink segment")
            return False
        snapshot_mutator.decrease_reserved(self.ctx.device_snapshot, unmap_size)
        self.dispatcher.post_replay_unmap_or_free_segment(
            virtual_free_segment, self.ctx.device_snapshot
        )
        return True
