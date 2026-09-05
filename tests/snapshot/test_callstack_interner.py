from pt_snap_cli.snapshot.base import TraceEntry
from pt_snap_cli.snapshot.tools.adaptors.database.callstack import CallstackInterner

INNER = {"filename": "inner.py", "line": 10, "name": "inner"}
OUTER = {"filename": "outer.py", "line": 20, "name": "outer"}
EXPECTED_TEXT = "outer.py:20 outer\ninner.py:10 inner"


def _raw_event(frames: list[dict], idx: int = 0) -> TraceEntry:
    return TraceEntry.from_dict(
        {"action": "alloc", "addr": 0x1000, "size": 16, "stream": 0, "id": idx, "frames": frames},
        _raw_frames=True,
    )


def test_interned_text_matches_get_callstack():
    interner = CallstackInterner()
    event = _raw_event([INNER, OUTER])

    assert interner.intern(event) == 0
    assert interner.records() == [{"id": 0, "callstack": EXPECTED_TEXT}]
    assert interner.records()[0]["callstack"] == event.get_callstack()


def test_shared_frame_container_reuses_one_id():
    interner = CallstackInterner()
    frames = [INNER, OUTER]

    first = interner.intern(_raw_event(frames, idx=1))
    second = interner.intern(_raw_event(frames, idx=2))

    assert first == second == 0
    assert len(interner) == 1


def test_distinct_containers_with_equal_frames_reuse_one_id():
    interner = CallstackInterner()

    first = interner.intern(_raw_event([INNER, OUTER], idx=1))
    second = interner.intern(_raw_event([dict(INNER), dict(OUTER)], idx=2))

    assert first == second == 0
    assert len(interner) == 1


def test_different_callstacks_get_different_ids():
    interner = CallstackInterner()

    first = interner.intern(_raw_event([INNER], idx=1))
    second = interner.intern(_raw_event([OUTER], idx=2))

    assert {first, second} == {0, 1}
    assert len(interner) == 2
    assert [record["callstack"] for record in interner.records()] == [
        "inner.py:10 inner",
        "outer.py:20 outer",
    ]


def test_empty_frames_intern_to_empty_text():
    interner = CallstackInterner()

    first = interner.intern(_raw_event([], idx=1))
    second = interner.intern(_raw_event([], idx=2))

    assert first == second == 0
    assert interner.records() == [{"id": 0, "callstack": ""}]


def test_reclaimed_container_address_does_not_produce_a_false_hit():
    """A freed container must not let a new object inherit its callstack id."""
    interner = CallstackInterner()
    addresses = []

    for frames in ([INNER], [OUTER]):
        event = _raw_event(frames)
        addresses.append(id(event.callstack_frames()))
        interner.intern(event)
        del event

    # The interner pins each keyed container, so a later container cannot land
    # on a pinned address and inherit the wrong id.
    assert len(interner) == 2
    assert [record["callstack"] for record in interner.records()] == [
        "inner.py:10 inner",
        "outer.py:20 outer",
    ]
    assert len(set(addresses)) == 2


def test_eager_frame_objects_intern_to_the_same_text_as_raw_frames():
    interner = CallstackInterner()
    raw = _raw_event([INNER, OUTER], idx=1)
    eager = TraceEntry.from_dict(
        {
            "action": "alloc",
            "addr": 0x1000,
            "size": 16,
            "stream": 0,
            "id": 2,
            "frames": [INNER, OUTER],
        },
    )

    raw_id = interner.intern(raw)
    eager_id = interner.intern(eager)

    assert raw_id == eager_id == 0
    assert len(interner) == 1
