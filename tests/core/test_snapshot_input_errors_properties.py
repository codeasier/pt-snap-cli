"""Trace input failures through real replay/SQLite; never deserialize a pickle."""

from __future__ import annotations

import copy
import importlib
import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

from pt_snap_cli.core.errors import ImportExecutionError
from pt_snap_cli.core.snapshot_import_backend import SnapshotImportBackend
from pt_snap_cli.snapshot.base import Block, DeviceSnapshot, TraceEntry

PROPERTY_SETTINGS = settings(
    max_examples=25, derandomize=True, database=None, deadline=None, print_blob=True
)
SCALARS = st.one_of(st.none(), st.booleans(), st.integers(-100, 100), st.text(max_size=12))
BAD_NUMBERS = st.one_of(
    st.none(),
    st.lists(SCALARS, max_size=3),
    st.dictionaries(st.text(max_size=8), SCALARS, max_size=3),
    st.sampled_from([float("nan"), float("inf"), float("-inf")]),
)
SOURCE_BYTES = b"inert placeholder; only the patched in-memory loader may be used"


def _valid_representation() -> dict[str, object]:
    return {
        "segments": [
            {
                "address": 4096,
                "total_size": 16,
                "stream": 0,
                "segment_type": "small",
                "allocated_size": 16,
                "active_size": 16,
                "frames": [],
                "blocks": [
                    {
                        "size": 16,
                        "requested_size": 8,
                        "address": 4096,
                        "state": "active_allocated",
                        "frames": [],
                    }
                ],
            }
        ],
        "device_traces": [
            [
                {
                    "action": "oom",
                    "size": 1,
                    "frames": [{"filename": "generated.py", "line": 1, "name": "run"}],
                }
            ]
        ],
    }


def _assert_representation_rejected(
    representation: object,
    cause: type[Exception],
    existing: bool,
    *,
    device: int | None = 0,
) -> Exception:
    before = copy.deepcopy(representation)
    with TemporaryDirectory() as directory, pytest.MonkeyPatch.context() as monkeypatch:
        root = Path(directory)
        source = root / "trusted-in-memory.pkl"
        source.write_bytes(SOURCE_BYTES)
        output = root / "output"
        output.mkdir()
        backend = SnapshotImportBackend()
        destination = backend.target_db_path(source, output)
        previous = b"existing destination must remain byte-for-byte unchanged"
        if existing:
            destination.write_bytes(previous)
        loads = []

        def load_representation(path: Path) -> object:
            assert path == source
            loads.append(path)
            return representation

        # Older lazy-import tests evict snapshot2db from sys.modules. Always
        # patch the current module, not a collection-time reference.
        snapshot2db = importlib.import_module("pt_snap_cli.snapshot.tools.adaptors.snapshot2db")
        monkeypatch.setattr(snapshot2db, "load_snapshot_representation", load_representation)
        with pytest.raises(ImportExecutionError, match="Snapshot import backend failed") as error:
            backend.dump_to_db(source, output, device=device)
        underlying = error.value.__cause__
        assert isinstance(underlying, cause)
        assert loads == [source]
        assert representation == before
        assert source.read_bytes() == SOURCE_BYTES
        if existing:
            assert destination.read_bytes() == previous
        else:
            assert not destination.exists()
        assert list(output.iterdir()) == ([destination] if existing else [])
        return underlying


def _assert_rejected(event: object, cause: type[Exception], existing: bool) -> Exception:
    return _assert_representation_rejected(
        {"segments": [], "device_traces": [[event]]}, cause, existing
    )


@PROPERTY_SETTINGS
@given(size=st.integers(0, 1 << 20), existing=st.booleans())
def test_generated_missing_action_rejects_without_publication(size: int, existing: bool) -> None:
    cause = _assert_rejected({"size": size, "frames": []}, ValueError, existing)
    assert "Trace field 'action'" in str(cause)


@PROPERTY_SETTINGS
@given(
    action=st.one_of(
        st.none(),
        st.booleans(),
        st.integers(-(1 << 65), 1 << 65),
        st.lists(SCALARS, max_size=3),
        st.dictionaries(st.text(max_size=8), SCALARS, max_size=3),
        st.sampled_from(["", " ", "\t\n"]),
    ),
    existing=st.booleans(),
)
def test_generated_malformed_action_rejects_without_publication(
    action: object, existing: bool
) -> None:
    cause = _assert_rejected({"action": action, "frames": []}, ValueError, existing)
    assert "Trace field 'action'" in str(cause)


@PROPERTY_SETTINGS
@given(event=st.one_of(SCALARS, st.lists(SCALARS, max_size=3)), existing=st.booleans())
def test_generated_non_mapping_trace_rejects_without_publication(
    event: object, existing: bool
) -> None:
    cause = _assert_rejected(event, ValueError, existing)
    assert "Trace entry must be a mapping" in str(cause)


@pytest.mark.parametrize("field", ["addr", "size", "stream", "device_free", "id"])
@PROPERTY_SETTINGS
@given(value=BAD_NUMBERS, existing=st.booleans())
def test_generated_wrong_numeric_types_and_nonfinite_values_retain_conversion_cause(
    field: str, value: object, existing: bool
) -> None:
    event = {"action": "oom", "size": 1, "frames": [], field: value}
    cause = _assert_rejected(event, ValueError, existing)
    assert f"Trace field '{field}'" in str(cause)
    assert isinstance(cause.__cause__, (TypeError, ValueError, OverflowError))


@pytest.mark.parametrize("field", ["addr", "size", "stream", "id"])
@PROPERTY_SETTINGS
@given(
    extra=st.integers(0, 1 << 128),
    negative=st.booleans(),
    as_text=st.booleans(),
    existing=st.booleans(),
)
def test_generated_sqlite_integer_overflow_is_a_controlled_import_error(
    field: str, extra: int, negative: bool, as_text: bool, existing: bool
) -> None:
    # The existing SQLite INTEGER boundary, not a new snapshot-wide upper
    # bound: device_free is deliberately absent because it is not stored here.
    value = -(1 << 63) - 1 - extra if negative else (1 << 63) + extra
    event = {"action": "oom", "size": 1, "frames": [], field: str(value) if as_text else value}
    _assert_rejected(event, OverflowError, existing)


@pytest.mark.parametrize("device", [None, 0])
@PROPERTY_SETTINGS
@example(size=0, stream=0, event_id=0, as_text=False)
@example(size=0, stream=0, event_id=-1, as_text=True)
@example(size=(1 << 63) - 1, stream=(1 << 63) - 1, event_id=(1 << 63) - 1, as_text=True)
@given(
    size=st.integers(0, (1 << 63) - 1),
    stream=st.integers(0, (1 << 63) - 1),
    event_id=st.integers(0, (1 << 63) - 1),
    as_text=st.booleans(),
)
def test_generated_valid_numeric_strings_and_sentinels_still_import(
    device: int | None, size: int, stream: int, event_id: int, as_text: bool
) -> None:
    event = {
        "action": "oom",
        "size": str(size) if as_text else size,
        "stream": str(stream) if as_text else stream,
        "id": str(event_id) if as_text else event_id,
    }
    # Valid empty list/tuple entries remain empty devices, not malformed data.
    representation = {"segments": [], "device_traces": [[event], [], ()]}
    before = copy.deepcopy(representation)
    trace = TraceEntry.from_dict(event)
    assert (trace.addr, trace.device_free, trace.frames) == (-1, -1, [])
    assert (trace.size, trace.stream, trace.idx) == (size, stream, event_id)
    assert TraceEntry.from_dict({**event, "device_free": str(1 << 128)}).device_free == 1 << 128
    with TemporaryDirectory() as directory, pytest.MonkeyPatch.context() as monkeypatch:
        root = Path(directory)
        source = root / "trusted-in-memory.pkl"
        source.write_bytes(SOURCE_BYTES)
        output = root / "output"
        loads = []

        def load_representation(path: Path) -> dict[str, object]:
            assert path == source
            loads.append(path)
            return representation

        snapshot2db = importlib.import_module("pt_snap_cli.snapshot.tools.adaptors.snapshot2db")
        monkeypatch.setattr(snapshot2db, "load_snapshot_representation", load_representation)
        destination = SnapshotImportBackend().dump_to_db(source, output, device=device)
        with closing(sqlite3.connect(destination)) as connection:
            assert connection.execute(
                "SELECT id, address, size, stream FROM trace_entry_0"
            ).fetchall() == [(event_id, -1, size, stream)]
        assert loads == [source]
        assert representation == before
        assert source.read_bytes() == SOURCE_BYTES
        assert list(output.iterdir()) == [destination]


@pytest.mark.parametrize("error_type", [KeyError, TypeError, AttributeError])
def test_unrelated_backend_programming_errors_are_not_reclassified(error_type) -> None:
    with TemporaryDirectory() as directory, pytest.MonkeyPatch.context() as monkeypatch:
        root = Path(directory)
        source = root / "trusted-in-memory.pkl"
        source.write_bytes(SOURCE_BYTES)
        output = root / "output"
        output.mkdir()
        backend = SnapshotImportBackend()
        destination = backend.target_db_path(source, output)
        destination.write_bytes(b"previous database")
        failure = error_type("unrelated implementation error")

        def fail(**kwargs):
            raise failure

        monkeypatch.setattr(backend, "_load_run_dump_to_db", lambda: fail)
        with pytest.raises(error_type) as error:
            backend.dump_to_db(source, output)
        assert error.value is failure
        assert destination.read_bytes() == b"previous database"
        assert source.read_bytes() == SOURCE_BYTES
        assert list(output.iterdir()) == [destination]


@pytest.mark.parametrize("location", ["root", "segment", "block", "frame"])
@PROPERTY_SETTINGS
@given(value=st.one_of(SCALARS, st.lists(SCALARS, max_size=3)), existing=st.booleans())
def test_generated_non_mapping_snapshot_records_are_controlled(
    location: str, value: object, existing: bool
) -> None:
    representation = _valid_representation()
    if location == "root":
        representation = value
    elif location == "segment":
        representation["segments"][0] = value
    elif location == "block":
        representation["segments"][0]["blocks"][0] = value
    else:
        representation["device_traces"][0][0]["frames"][0] = value
    cause = _assert_representation_rejected(representation, ValueError, existing)
    assert "must be a mapping" in str(cause)


@pytest.mark.parametrize(
    "location",
    ["device_traces", "segments", "blocks", "trace_frames", "segment_frames", "block_frames"],
)
@PROPERTY_SETTINGS
@given(
    value=st.one_of(SCALARS, st.dictionaries(st.text(max_size=8), SCALARS, max_size=3)),
    existing=st.booleans(),
)
def test_generated_non_sequence_snapshot_containers_are_controlled(
    location: str, value: object, existing: bool
) -> None:
    representation = _valid_representation()
    if location in ("device_traces", "segments"):
        representation[location] = value
    elif location == "blocks":
        representation["segments"][0]["blocks"] = value
    elif location == "segment_frames":
        representation["segments"][0]["frames"] = value
    elif location == "block_frames":
        representation["segments"][0]["blocks"][0]["frames"] = value
    else:
        representation["device_traces"][0][0]["frames"] = value
    cause = _assert_representation_rejected(representation, ValueError, existing)
    assert "must be a list or tuple" in str(cause)


@PROPERTY_SETTINGS
@given(value=SCALARS, existing=st.booleans())
def test_generated_mapping_instead_of_device_trace_sequence_is_controlled(
    value: object, existing: bool
) -> None:
    representation = {"segments": [], "device_traces": [{"invalid": value}]}
    cause = _assert_representation_rejected(representation, ValueError, existing)
    assert "Snapshot device_traces[0] must be a list or tuple" in str(cause)


@pytest.mark.parametrize("device", [None, 0])
@pytest.mark.parametrize("position", [0, 1])
@PROPERTY_SETTINGS
@example(value=None, existing=False)
@example(value={}, existing=True)
@example(value=False, existing=True)
@example(value=0, existing=False)
@example(value="", existing=False)
@given(
    value=st.one_of(SCALARS, st.dictionaries(st.text(max_size=8), SCALARS, max_size=3)),
    existing=st.booleans(),
)
def test_generated_invalid_inner_device_traces_reject_before_device_selection(
    device: int | None, position: int, value: object, existing: bool
) -> None:
    # Truthiness must not let malformed empty values masquerade as an empty
    # device, either when dumping every device or selecting device zero.
    cause = _assert_representation_rejected(
        {"segments": [], "device_traces": [[] for _ in range(position)] + [value]},
        ValueError,
        existing,
        device=device,
    )
    assert f"Snapshot device_traces[{position}] must be a list or tuple" in str(cause)


@pytest.mark.parametrize(
    ("entity", "missing"),
    [("frame", key) for key in ("filename", "line", "name")]
    + [("block", key) for key in ("size", "requested_size", "address", "state")]
    + [
        ("segment", key)
        for key in (
            "address",
            "total_size",
            "stream",
            "allocated_size",
            "active_size",
            "segment_type",
            "blocks",
        )
    ],
)
@PROPERTY_SETTINGS
@given(line=st.integers(0, 1000), existing=st.booleans())
def test_generated_missing_required_snapshot_fields_are_controlled(
    entity: str, missing: str, line: int, existing: bool
) -> None:
    representation = _valid_representation()
    frame = representation["device_traces"][0][0]["frames"][0]
    frame["line"] = line
    record = {
        "frame": frame,
        "block": representation["segments"][0]["blocks"][0],
        "segment": representation["segments"][0],
    }[entity]
    del record[missing]
    cause = _assert_representation_rejected(representation, ValueError, existing)
    assert f"missing required field '{missing}'" in str(cause)


@pytest.mark.parametrize(
    ("entity", "field"),
    [("block", key) for key in ("size", "requested_size", "address")]
    + [
        ("segment", key)
        for key in ("address", "total_size", "stream", "allocated_size", "active_size")
    ],
)
@PROPERTY_SETTINGS
@given(value=st.one_of(BAD_NUMBERS, st.text(max_size=16)), existing=st.booleans())
def test_generated_non_numeric_allocator_metadata_is_controlled(
    entity: str, field: str, value: object, existing: bool
) -> None:
    representation = _valid_representation()
    record = representation["segments"][0]
    if entity == "block":
        record = record["blocks"][0]
    record[field] = value
    cause = _assert_representation_rejected(representation, ValueError, existing)
    assert f"field '{field}' must be a finite number" in str(cause)


@PROPERTY_SETTINGS
@given(value=st.one_of(st.none(), st.integers(-100, 100), st.lists(SCALARS, max_size=3)))
def test_generated_non_string_block_state_is_controlled(value: object) -> None:
    representation = _valid_representation()
    representation["segments"][0]["blocks"][0]["state"] = value
    cause = _assert_representation_rejected(representation, ValueError, True)
    assert "Block field 'state' must be a string" in str(cause)


@PROPERTY_SETTINGS
@given(
    state=st.one_of(
        st.sampled_from(["", "unknown", "99", "active", "ACTIVE_ALLOCATED"]),
        st.text(max_size=24).map(lambda value: f"unsupported:{value}"),
    ),
    existing=st.booleans(),
)
def test_generated_unknown_block_states_are_controlled(state: str, existing: bool) -> None:
    representation = _valid_representation()
    representation["segments"][0]["blocks"][0]["state"] = state
    cause = _assert_representation_rejected(representation, ValueError, existing)
    assert "Block field 'state' must be one of:" in str(cause)


@pytest.mark.parametrize("state", ["active_allocated", "active_pending_free", "inactive"])
@pytest.mark.parametrize("raw_frames", [False, True])
@PROPERTY_SETTINGS
@given(size=st.integers(1, 4096))
def test_generated_declared_block_states_preserve_eager_and_raw_inputs(
    state: str, raw_frames: bool, size: int
) -> None:
    block_data = {
        "size": size,
        "requested_size": size // 2,
        "address": 4096,
        "state": state,
        "frames": [{"filename": "generated.py", "line": 1, "name": "run"}],
    }
    before = copy.deepcopy(block_data)
    block = Block.from_dict(block_data, _raw_frames=raw_frames)
    assert block.state == state
    assert block.to_dict() == before
    assert block_data == before


@pytest.mark.parametrize("raw_frames", [False, True])
@PROPERTY_SETTINGS
@example(size=16.0, use_tuples=False)
@given(size=st.integers(1, 4096), use_tuples=st.booleans())
def test_generated_valid_entity_containers_preserve_input_and_defaults(
    raw_frames: bool, size: int | float, use_tuples: bool
) -> None:
    representation = _valid_representation()
    segment = representation["segments"][0]
    segment.update(total_size=size, allocated_size=size, active_size=size)
    segment["blocks"][0].update(size=size, requested_size=size)
    if use_tuples:
        segment["blocks"] = tuple(segment["blocks"])
        representation["segments"] = tuple(representation["segments"])
        event = representation["device_traces"][0][0]
        event["frames"] = tuple(event["frames"])
        representation["device_traces"] = ((event,),)
    before = copy.deepcopy(representation)
    snapshot = DeviceSnapshot.from_dict(representation, 0, _raw_frames=raw_frames)
    assert snapshot.total_reserved == snapshot.total_allocated == snapshot.total_activated == size
    assert snapshot.segments[0].blocks[0].size == size
    assert snapshot.segments[0].device == 0
    assert snapshot.segments[0].is_expandable is False
    trace = snapshot.trace_entries[0]
    assert (trace.idx, trace.addr, trace.stream, trace.device_free) == (0, -1, 0, -1)
    assert trace.get_callstack() == "generated.py:1 run"
    assert representation == before
