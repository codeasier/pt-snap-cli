# Snapshot Runtime Tests

Parent scope: [test contracts](../AGENTS.md).
Implementation: [snapshot runtime](../../src/pt_snap_cli/snapshot/AGENTS.md).

## Runtime Test Map

| Files | Boundary |
| --- | --- |
| `test_entities.py`, `test_file_util.py` | Entity normalization, representation/loading and trusted-input behavior |
| `test_replay_executor.py`, `test_simulate.py` | Replay ordering and allocator simulation |
| `test_replay_boundaries.py` | Rejected allocator/mutator operations, state preservation and edge conditions |
| `test_snapshot_mutator.py`, `test_snapshot_lookup.py`, `test_allocator_hook_dispatcher.py` | Mutation, lookup and callback contracts |
| `test_snapshot2db_runtime.py`, `test_entity2record.py`, `test_callstack_interner.py` | Replay-driven database generation, records and interned stacks |
| `test_sqlite_meta.py` | Schema/value conversion, optional/PEP 604 affinities and real SQLite round trips |
| `test_slice_dump_runtime.py` | Slice boundaries, formats, original IDs and replay validity |
| `helpers.py`, `golden_observations.py` | Reusable invariants and reviewed schema/action/import observations |
| `test_logger.py`, `test_timer.py` | Runtime utility behavior |

## Evidence Rules

- Use reviewed, checksum-verified committed fixtures or minimal temporary
  snapshots constructed in the test. Keep committed inputs read-only.
- After rejected operations, assert allocator state as well as the exception.
  For slices, replay and check event IDs/device/state, not just file existence or
  serialized bytes.
- Golden observations change only for intentional reviewed behavior/schema
  changes. Do not regenerate them to make a failing test pass without explaining
  the changed contract.
- Database tests own/close writer handles and verify actual column/value behavior;
  nullable-affinity tests should exercise sorting and NULL round trips.

Run `pytest tests/test_fixture_provenance.py` before `pytest tests/snapshot`.
Import publication/focus behavior lives in `tests/core/test_import_*.py`, while
product split validation/publication lives in `tests/core/test_split_service.py`.
Runtime/provenance edits also require `tests/test_governance.py`; the CI runtime
coverage floors are independent of the overall coverage result.
