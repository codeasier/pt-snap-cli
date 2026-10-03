# Library Domain Models

Parent scope: [package runtime](../AGENTS.md).

This scope owns exported dataclasses and allocator enums. It is separate from
`core/models.py` service payloads and `snapshot/base/entities.py` replay objects.

| File | Contract |
| --- | --- |
| `_enums.py` | Library event actions and block states |
| `block.py` | `MemoryBlock`; negative IDs are historical; `free_event_id` of `None` or `-1` is active |
| `event.py` | `MemoryEvent`; negative IDs are virtual, nonnegative IDs are runtime events |
| `__init__.py` | Public exports |

Preserve sentinel meanings and optional-field defaults when changing models.
Library snake_case attributes and SnapshotDB/query column spellings are different
boundaries; do not rename one by assuming every consumer uses the same shape.
Query `ResultMapper` conversions/model factories are in `query/mapper.py`.

From the repository root, run `pytest tests/models tests/test_models.py` for
model/enum changes and `pytest tests/query/test_mapper.py` for mapping changes.
Review `__init__.py` exports and both ResultMapper API guides when changing public
construction or conversion behavior.
