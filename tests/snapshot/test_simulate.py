import os
import unittest
from collections import Counter
from pathlib import Path

import pytest

from pt_snap_cli.vendor.memsnapdump.base import BlockState
from pt_snap_cli.vendor.memsnapdump.simulate import SimulateDeviceSnapshot, SimulateHooker
from pt_snap_cli.vendor.memsnapdump.simulate.hooker_defs import AllocatorHooker
from pt_snap_cli.vendor.memsnapdump.simulate.snapshot_lookup import find_overlapping_segment
from pt_snap_cli.vendor.memsnapdump.util.file_util import load_pickle_to_dict
from pt_snap_cli.vendor.memsnapdump.util.logger import restore_logs, suppress_logs

from .golden_observations import FIXTURE_REPLAY_GOLDEN
from .helpers import FIXTURE_DIR, assert_valid_segments, assert_valid_snapshot


class ReplayEventHooker(SimulateHooker):
    def __init__(self, valid_interval=100):
        self.replay_count = 0
        self.valid_interval = valid_interval

    def pre_undo_event(self, wait4undo_event, current_snapshot):
        return True

    def post_undo_event(self, already_undo_event, current_snapshot):
        if self.replay_count % self.valid_interval == 0:
            assert_valid_segments(current_snapshot.segments)
        self.replay_count += 1
        return True


class ReplayBlockHooker(AllocatorHooker):
    def __init__(self, test_util):
        self.test_util = test_util
        self._segment = None
        self.pre_seg_allocated_size = 0
        self.pre_seg_active_size = 0
        self.pre_snapshot_total_allocated_size = 0
        self.pre_snapshot_total_active_size = 0

    def pre_replay_alloc_block(self, wait4alloc_block, current_snapshot):
        super().pre_replay_alloc_block(wait4alloc_block, current_snapshot)
        self.test_util.assertNotEqual(wait4alloc_block.state, BlockState.INACTIVE)
        segment_idx, self._segment = find_overlapping_segment(
            current_snapshot, wait4alloc_block.address
        )
        self.test_util.assertTrue(0 <= segment_idx < len(current_snapshot.segments))
        self.pre_seg_allocated_size = self._segment.allocated_size
        self.pre_seg_active_size = self._segment.active_size
        self.pre_snapshot_total_allocated_size = current_snapshot.total_allocated
        self.pre_snapshot_total_active_size = current_snapshot.total_activated

    def post_replay_alloc_block(self, allocated_block, current_snapshot):
        super().post_replay_alloc_block(allocated_block, current_snapshot)
        self.test_util.assertEqual(
            self.pre_seg_active_size + allocated_block.size, self._segment.active_size
        )
        self.test_util.assertEqual(
            self.pre_snapshot_total_active_size + allocated_block.size,
            current_snapshot.total_activated,
        )
        if allocated_block.state == BlockState.ACTIVE_ALLOCATED:
            self.test_util.assertEqual(
                self.pre_seg_allocated_size + allocated_block.size,
                self._segment.allocated_size,
            )
            self.test_util.assertEqual(
                self.pre_snapshot_total_allocated_size + allocated_block.size,
                current_snapshot.total_allocated,
            )


class TestSimulate(unittest.TestCase):
    snapshot_path = FIXTURE_DIR / "snapshot_1768383987920985470.pkl"
    expandable_path = FIXTURE_DIR / "snapshot_expandable.pkl"
    empty_cache_path = FIXTURE_DIR / "snapshot_with_empty_cache.pkl"
    expandable_empty_cache_path = FIXTURE_DIR / "snapshot_with_empty_cache_expandable.pkl"

    @classmethod
    def setUpClass(cls):
        if os.getenv("UT_VERBOSE_LOG") != "1":
            suppress_logs()

    @classmethod
    def tearDownClass(cls):
        restore_logs()

    @staticmethod
    def get_simulate_snapshot(snapshot_path: Path):
        return SimulateDeviceSnapshot(load_pickle_to_dict(snapshot_path), 0)

    def _assert_block_hook_replay(self, path):
        snapshot = self.get_simulate_snapshot(path)
        assert_valid_segments(snapshot.device_snapshot.segments)
        snapshot.register_allocator_hooker(ReplayBlockHooker(self))
        self.assertTrue(snapshot.replay())

    def _assert_event_hook_replay(self, path):
        snapshot = self.get_simulate_snapshot(path)
        snapshot.register_hooker(ReplayEventHooker())
        self.assertTrue(snapshot.replay())

    def test_block_hooker_in_snapshot(self):
        self._assert_block_hook_replay(self.snapshot_path)

    def test_block_hooker_in_expandable_snapshot(self):
        self._assert_block_hook_replay(self.expandable_path)

    def test_block_hooker_in_snapshot_with_empty_cache(self):
        self._assert_block_hook_replay(self.empty_cache_path)

    def test_block_hooker_in_expandable_snapshot_with_empty_cache(self):
        self._assert_block_hook_replay(self.expandable_empty_cache_path)

    def test_replay_snapshot(self):
        self._assert_event_hook_replay(self.snapshot_path)

    def test_replay_expandable_snapshot(self):
        self._assert_event_hook_replay(self.expandable_path)

    def test_replay_snapshot_with_empty_cache(self):
        self._assert_event_hook_replay(self.empty_cache_path)

    def test_replay_expandable_snapshot_with_empty_cache(self):
        self._assert_event_hook_replay(self.expandable_empty_cache_path)


class Hooker:
    def __init__(self, pre=True, post=True):
        self.pre = pre
        self.post = post
        self.calls = []

    def pre_undo_event(self, event, snapshot):
        self.calls.append(("pre", event.idx))
        return self.pre

    def post_undo_event(self, event, snapshot):
        self.calls.append(("post", event.idx))
        return self.post


class MinimalAllocatorHooker:
    pass


def make_snapshot_dict(action="alloc", with_segment=False):
    payload = {
        "segments": [],
        "device_traces": [[{"action": action, "addr": 1, "size": 1, "stream": 0, "frames": []}]],
    }
    if with_segment:
        payload["segments"] = [
            {
                "address": 1,
                "total_size": 16,
                "stream": 0,
                "segment_type": "small",
                "allocated_size": 0,
                "active_size": 0,
                "device": 0,
                "is_expandable": False,
                "frames": [],
                "blocks": [],
            }
        ]
    return payload


def test_simulate_device_snapshot_raises_on_empty_snapshot():
    with pytest.raises(RuntimeError):
        SimulateDeviceSnapshot({}, 0)


def test_simulate_device_snapshot_sets_workspace_flag_from_first_event():
    snapshot = SimulateDeviceSnapshot(make_snapshot_dict("workspace_snapshot"), 0)

    assert snapshot.simulated_allocator_context.workspace_flag is True


def test_simulate_register_unregister_hookers_and_allocator_hookers():
    snapshot = SimulateDeviceSnapshot(make_snapshot_dict(), 0)
    hooker = Hooker()
    allocator_hooker = MinimalAllocatorHooker()

    hook_id = snapshot.register_hooker(hooker)
    allocator_id = snapshot.register_allocator_hooker(allocator_hooker)
    snapshot.unregister_hooker(hook_id)
    snapshot.unregister_allocator_hooker(allocator_id)

    assert hook_id not in snapshot.hookers
    assert allocator_id not in snapshot.simulated_allocator.dispatcher.hookers


def test_simulate_replay_stops_when_pre_hook_returns_false():
    snapshot = SimulateDeviceSnapshot(make_snapshot_dict(), 0)
    hooker = Hooker(pre=False)
    snapshot.register_hooker(hooker)

    assert snapshot.replay() is False
    assert hooker.calls == [("pre", 0)]


def test_simulate_replay_stops_when_post_hook_returns_false():
    snapshot = SimulateDeviceSnapshot(make_snapshot_dict("free", with_segment=True), 0)
    hooker = Hooker(post=False)
    snapshot.register_hooker(hooker)

    assert snapshot.replay() is False
    assert hooker.calls == [("pre", 0), ("post", 0)]


def snapshot_observation(snapshot):
    device_snapshot = snapshot.device_snapshot
    return (
        len(device_snapshot.segments),
        sum(len(segment.blocks) for segment in device_snapshot.segments),
        len(device_snapshot.trace_entries),
        device_snapshot.total_allocated,
        device_snapshot.total_activated,
        device_snapshot.total_reserved,
    )


@pytest.mark.parametrize(("fixture_name", "device"), FIXTURE_REPLAY_GOLDEN)
def test_fixture_replay_matches_pre_relocation_golden(fixture_name, device):
    golden = FIXTURE_REPLAY_GOLDEN[(fixture_name, device)]
    snapshot = SimulateDeviceSnapshot(load_pickle_to_dict(FIXTURE_DIR / fixture_name), device)

    assert snapshot_observation(snapshot) == golden["initial"]
    assert (
        Counter(event.action for event in snapshot.device_snapshot.trace_entries)
        == golden["actions"]
    )
    assert_valid_snapshot(snapshot.device_snapshot)

    assert snapshot.replay() is True
    assert snapshot_observation(snapshot) == golden["final"]
    assert_valid_snapshot(snapshot.device_snapshot)


def test_multi_device_fixture_keeps_device_state_isolated():
    data = load_pickle_to_dict(FIXTURE_DIR / "snapshot_with_multi_devices.pkl")
    device_zero = SimulateDeviceSnapshot(data, 0)
    device_one = SimulateDeviceSnapshot(data, 1)
    device_one_before = snapshot_observation(device_one)

    assert device_zero.replay() is True

    assert snapshot_observation(device_one) == device_one_before
    assert snapshot_observation(device_zero) != snapshot_observation(device_one)


def test_minimal_workspace_input_only_establishes_tolerance_flag_and_skip_behavior():
    snapshot = SimulateDeviceSnapshot(make_snapshot_dict("workspace_snapshot"), 0)

    assert snapshot.simulated_allocator_context.workspace_flag is True
    assert snapshot.replay() is True
    assert snapshot.device_snapshot.trace_entries == []
