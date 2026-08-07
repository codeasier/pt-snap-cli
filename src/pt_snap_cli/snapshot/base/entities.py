from dataclasses import dataclass, field
from typing import Any, Literal


class Frame:
    filename: str = ""
    line: int = -1
    name: str = ""

    _origin: dict = None  # Readonly

    @classmethod
    def from_dict(cls, frame_dict: dict):
        frame = cls()
        frame.filename = frame_dict["filename"]
        frame.line = frame_dict["line"]
        frame.name = frame_dict["name"]
        frame._origin = frame_dict
        return frame

    def to_dict(self):
        return (
            self._origin
            if self._origin
            else {"filename": self.filename, "line": self.line, "name": self.name}
        )


def _format_callstack(frames: list[Frame] | list[dict]) -> str:
    if not frames:
        return ""
    if isinstance(frames[0], Frame):
        return "\n".join(
            [f"{frame.filename}:{frame.line} {frame.name}" for frame in reversed(frames)]
        )
    return "\n".join(
        [f"{frame['filename']}:{frame['line']} {frame['name']}" for frame in reversed(frames)]
    )


@dataclass
class TraceEntry:
    # When `torch.npu.memory._record_memory_history()` is enabled,
    # the snapshot will contain TraceEntry objects that record each
    # action the allocator took.
    """
    action: Literal[
        'alloc'  # memory allocated
        'free_requested',  # the allocated received a call to free memory
        'free_completed',  # the memory that was requested to be freed is now
            # able to be used in future allocation calls
        'segment_alloc',  # the caching allocator ask aclrtMalloc for more memory
            # and added it as a segment in its cache
        'segment_free',  # the caching allocator called aclrtFree to return memory
            # to npu possibly trying free up memory to
            # allocate more segments or because empty_caches was called
        'oom',  # the allocator threw an OOM exception. 'size' is
            # the requested number of bytes that did not succeed
        'snapshot'  # the allocator generated a memory snapshot
        # useful to coorelate a previously taken
        # snapshot with this trace
    ]
    """
    action: str = ""
    addr: int = -1  # not present for OOM
    frames: list[Frame] = field(default_factory=list)
    size: int = 0
    stream: int = 0
    device_free: int = -1  # only present for OOM, the amount of
    # memory npu still reports to be free

    _origin: dict = None  # Readonly
    idx: int = -1  # 索引，全局唯一
    _raw_frames: list[dict] | None = field(default=None, repr=False)

    @classmethod
    def from_dict(cls, trace_dict: dict, _raw_frames: bool = False):
        frame_dicts = trace_dict.get("frames", [])
        if _raw_frames:
            iter(frame_dicts)
        trace_entry = cls(
            action=trace_dict["action"],
            addr=int(trace_dict["addr"]),
            size=int(trace_dict["size"]),
            stream=int(trace_dict["stream"]),
            _origin=trace_dict,
            frames=[] if _raw_frames else [Frame.from_dict(frame) for frame in frame_dicts],
            _raw_frames=frame_dicts if _raw_frames else None,
            idx=int(trace_dict["id"]) if "id" in trace_dict else -1,
        )
        return trace_entry

    def get_callstack(self):
        return _format_callstack(self._raw_frames if self._raw_frames is not None else self.frames)

    def to_dict(self, include_id: bool = False):
        if self._origin and not include_id:
            return self._origin
        trace_dict = (
            dict(self._origin)
            if self._origin
            else {
                "action": self.action,
                "addr": self.addr,
                "size": self.size,
                "stream": self.stream,
                "frames": (
                    self._raw_frames
                    if self._raw_frames is not None
                    else [frame.to_dict() for frame in self.frames]
                ),
            }
        )
        if include_id:
            trace_dict["id"] = self.idx
        return trace_dict


class BlockState:
    ACTIVE_PENDING_FREE = "active_pending_free"
    ACTIVE_ALLOCATED = "active_allocated"
    INACTIVE = "inactive"


@dataclass
class Block:
    # A piece of memory returned from the allocator, or
    # current cached but inactive.
    size: int = 0
    requested_size: int = 0  # size requested during malloc, may be smaller than
    # size due to rounding
    address: int = -1
    state: Literal[
        "active_allocated",  # used by a tensor
        "active_pending_free",  # waiting for another stream to finish using this, then it will become free
        "inactive",
    ] = BlockState.INACTIVE  # free for reuse
    frames: list[Frame] = field(
        default_factory=list
    )  # stack trace from where the allocation occurred

    # 指向持有该block的segment对象
    segment_ptr: Any = None
    free_event_idx: int = None
    alloc_event_idx: int = None
    _raw_frames: list[dict] | None = field(default=None, repr=False)

    @classmethod
    def from_dict(cls, block_dict: dict, _raw_frames: bool = False):
        frame_dicts = block_dict.get("frames", [])
        if _raw_frames:
            iter(frame_dicts)
        block = cls(
            size=block_dict["size"],
            requested_size=block_dict["requested_size"],
            address=block_dict["address"],
            state=block_dict["state"],
            frames=[] if _raw_frames else [Frame.from_dict(frame) for frame in frame_dicts],
            _raw_frames=frame_dicts if _raw_frames else None,
        )
        return block

    @classmethod
    def build_from_event(cls, event: TraceEntry):
        block = cls(
            size=event.size,
            requested_size=event.size,
            address=event.addr,
            frames=event.frames,
            _raw_frames=event._raw_frames,
        )
        return block

    def to_dict(self):
        return {
            "size": self.size,
            "requested_size": self.requested_size,
            "address": self.address,
            "state": self.state,
            "frames": (
                self._raw_frames
                if self._raw_frames is not None
                else [frame.to_dict() for frame in self.frames]
            ),
        }


@dataclass
class Segment:
    # Segments are memory returned from a aclrtMalloc call.
    # The size of reserved memory is the sum of all Segments.
    # Segments are cached and reused for future allocations.
    # If the reuse is smaller than the segment, the segment
    # is split into more then one Block.
    # empty_cache() frees Segments that are entirely inactive.
    address: int = -1
    total_size: int = 0  # aclrtMalloc'd size of segment
    stream: int = 0
    segment_type: Literal["small", "large"] = ""  # 'large' (>1MB)
    allocated_size: int = 0  # size of memory in use
    active_size: int = 0  # size of memory in use or in active_awaiting_free state
    blocks: list[Block] = field(default_factory=list)
    device: int = 0
    frames: list[Frame] = field(default_factory=list)
    is_expandable: bool = False
    _origin: dict = None  # Readonly
    free_or_unmap_event_idx: int = None
    alloc_or_map_event_idx: int = None
    _raw_frames: list[dict] | None = field(default=None, repr=False)

    @classmethod
    def from_dict(
        cls, segment_dict: dict, ignore_inactive_blocks: bool = False, _raw_frames: bool = False
    ):
        frame_dicts = segment_dict.get("frames", [])
        if _raw_frames:
            iter(frame_dicts)
        segment = cls(
            address=segment_dict["address"],
            total_size=segment_dict["total_size"],
            stream=segment_dict["stream"],
            segment_type=segment_dict["segment_type"],
            allocated_size=segment_dict["allocated_size"],
            active_size=segment_dict["active_size"],
            frames=[] if _raw_frames else [Frame.from_dict(frame) for frame in frame_dicts],
            _raw_frames=frame_dicts if _raw_frames else None,
            device=segment_dict.get("device", 0),
            _origin=segment_dict,
            is_expandable=segment_dict.get("is_expandable", False),
        )
        for block in segment_dict["blocks"]:
            if ignore_inactive_blocks and block["state"] == BlockState.INACTIVE:
                continue
            _block = Block.from_dict(block, _raw_frames=_raw_frames)
            _block.segment_ptr = segment
            segment.blocks.append(_block)
        return segment

    @classmethod
    def build_from_event(cls, event: TraceEntry, with_inactive_block: bool = False):
        segment = cls(
            address=event.addr,
            total_size=event.size,
            stream=event.stream,
            frames=event.frames,
            _raw_frames=event._raw_frames,
            device=event.device if hasattr(event, "device") else 0,
            allocated_size=0,
            active_size=0,
            is_expandable=event.action in ["segment_map", "segment_unmap"],
        )
        segment.blocks = (
            []
            if not with_inactive_block
            else [
                Block(
                    size=event.size,
                    requested_size=event.size,
                    address=event.addr,
                    state=BlockState.INACTIVE,
                    segment_ptr=segment,
                )
            ]
        )
        return segment

    def to_dict(self):
        return {
            "address": self.address,
            "total_size": self.total_size,
            "stream": self.stream,
            "segment_type": self.segment_type,
            "allocated_size": self.allocated_size,
            "active_size": self.active_size,
            "device": self.device,
            "is_expandable": self.is_expandable,
            "frames": (
                self._raw_frames
                if self._raw_frames is not None
                else [frame.to_dict() for frame in self.frames]
            ),
            "blocks": [block.to_dict() for block in self.blocks],
        }


class DeviceSnapshot:
    segments: list[Segment]
    trace_entries: list[TraceEntry]

    total_allocated: int  # 二次分配总量
    total_reserved: int  # 内存池总量
    total_activated: int  # 活跃内存总量

    device: int

    @classmethod
    def from_dict(
        cls,
        snapshot_dict: dict,
        device: int,
        ignore_inactive_blocks: bool = False,
        _raw_frames: bool = False,
    ):
        segments_dict = snapshot_dict.get("segments", [])
        device_traces = snapshot_dict.get("device_traces", [])
        device_trace_list = device_traces[device] if 0 <= device < len(device_traces) else []
        snapshot = cls()
        snapshot.segments = []
        snapshot.trace_entries = []
        snapshot.total_allocated = 0
        snapshot.total_reserved = 0
        snapshot.total_activated = 0
        # 读取dump_snapshot时内存状态
        for segment_dict in segments_dict:
            # 当segment原始数据中缺少device字段明确指向其所属设备时，默认其归属为device0
            # 此时如果from_dict指定device为0或未指定而缺省为0，则未知归属的device也会纳入分析
            if segment_dict.get("device", 0) != device:
                continue
            _segment = Segment.from_dict(
                segment_dict,
                ignore_inactive_blocks=ignore_inactive_blocks,
                _raw_frames=_raw_frames,
            )
            snapshot.segments.append(_segment)
            snapshot.total_allocated += _segment.allocated_size
            snapshot.total_reserved += _segment.total_size
            snapshot.total_activated += _segment.active_size
        snapshot.segments.sort(key=lambda segment: (segment.address, segment.stream))
        # 读取事件序列
        for idx, trace_entry_dict in enumerate(device_trace_list):
            trace_entry = TraceEntry.from_dict(trace_entry_dict, _raw_frames=_raw_frames)
            if "id" not in trace_entry_dict:
                trace_entry.idx = idx
            snapshot.trace_entries.append(trace_entry)
        snapshot.device = device
        return snapshot

    def to_dict(self, include_trace_ids: bool = False):
        return {
            "segments": [segment.to_dict() for segment in self.segments],
            # 需要根据deviceId，将事件列表填入，如果deviceId不为0，前序还要padding空事件列表
            "device_traces": [[] for _ in range(self.device)]
            + [[trace.to_dict(include_id=include_trace_ids) for trace in self.trace_entries]],
        }
