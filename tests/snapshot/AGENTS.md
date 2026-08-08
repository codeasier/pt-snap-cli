<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-08-08 | Updated: 2026-08-08 -->

# snapshot tests

## Purpose
`tests/snapshot` verifies the first-party snapshot representation, entities, allocator simulation/replay, SQLite adaptors, and slice runtime using synthetic objects and repository-trusted fixtures.

## Key Files
| File | Description |
|------|-------------|
| `helpers.py` | Shared segment and device-snapshot invariant assertions. |
| `golden_observations.py` | Stable runtime row counts, schemas, action maps, and import observations. |
| `test_snapshot2db_runtime.py` | Replay-driven SnapshotDB generation and schema/runtime behavior. |
| `test_slice_dump_runtime.py` | Slice boundaries, formats, event IDs, replay, and output behavior. |
| `test_replay_executor.py`, `test_simulate.py` | Replay sequencing and allocator simulation behavior. |
| `test_entity2record.py`, `test_sqlite_meta.py` | Database record conversion and SQLite schema/value mapping. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| None | Snapshot runtime tests are grouped in this directory. |

## For AI Agents

### Working In This Directory
- Deserialize only committed trusted fixtures or temporary pickles generated inside the test itself; never load external untrusted pickle data.
- Keep synthetic fixtures minimal and preserve explicit event IDs when testing slice boundaries.
- Update golden observations only for intentional, reviewed runtime changes; do not regenerate them to hide regressions.

### Testing Requirements
- Run `pytest tests/snapshot` for runtime changes.
- Run affected `tests/core/test_import_*.py` or `tests/core/test_split_service.py` when behavior crosses the product boundary.
- Run `pytest tests/test_governance.py` for changes under `src/pt_snap_cli/snapshot/` or its provenance declaration.

### Common Patterns
- Tests validate allocator invariants after replay rather than comparing serialization bytes alone.
- Temporary paths isolate generated databases and slices; committed pickle fixtures remain read-only inputs.

## Dependencies

### Internal
- `src/pt_snap_cli/snapshot/` is the primary runtime under test.
- `tests/fixtures/snapshots/` contains trusted snapshot inputs used by runtime and import baselines.

### External
- `pytest` and Python standard-library pickle/SQLite behavior.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
