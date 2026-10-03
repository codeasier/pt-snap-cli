# Snapshot Runtime

Parent scope: [package runtime](../AGENTS.md).

This is the first-party mechanism layer for representation loading, allocator
replay, database adaptation and slicing. Product validation/publication belongs
to [core](../core/AGENTS.md). Read [fixture acceptance](../../../tests/fixtures/AGENTS.md)
before running code that loads committed pickle inputs.

## Runtime Map

| Path | Responsibility |
| --- | --- |
| `representation.py` | Pickle/JSON load/save, canonicalization/hash, device construction and shared replay entry |
| `base/entities.py` | Frames, traces, blocks, segments and device snapshots |
| `simulate/simulate.py`, `replay_executor.py` | Replay construction and event sequencing |
| `simulate/simulated_caching_allocator.py`, `snapshot_mutator.py` | Allocator transitions, split/merge/map/unmap mutations |
| `simulate/snapshot_lookup.py`, `allocator_context.py`, `allocator_hook_dispatcher.py` | Lookup/state context and hook dispatch |
| `tools/adaptors/snapshot2db.py` | Replay-driven database generation and cleanup |
| `tools/adaptors/database/` | Records, schema, callstack interning and SnapshotDb indexes/write behavior |
| `tools/slice_dump/` | Boundary-state reconstruction and per-device serialization |
| `util/` | File, logger, timer and SQLite type/schema helpers |

## Runtime Invariants

- The restricted pickle loader is not a sandbox. Trusted pickle is still code
  execution; do not deserialize a new snapshot merely to investigate its trust.
- Preserve original event IDs, representation compatibility and replay-valid
  allocator state across slices. Canonical comparison is separate from byte-for-
  byte pickle serialization. Keep the representation boundary's strict type gates.
- A rejected allocator/mutator operation must preserve valid prior state. Verify
  preconditions and hook sequencing as well as the happy-path final totals.
- Callstack storage uses interning in the database adaptor; readers select v1/v2
  through Context/query variants. Coordinate schema/index changes with those
  readers, `core/import_metadata.py`, and English/Chinese database guides.
- `util/sqlite_meta.py` must give `T | None` and `Optional[T]` the same scalar
  SQLite affinity; unsupported/multi-type unions retain their TEXT fallback.

## Provenance and Verification

`PROVENANCE.md` records source/license decisions and local runtime changes;
existing content is append-only. `LICENSE` and provenance ship with the package.
The guard checks all paths here, including this guide. Use the exact decision
labels from the [PR template](../../../.github/pull_request_template.md): either
`updated` with new provenance content, or `no-update` with a specific reason when
source mappings, rights and runtime history do not need an entry.

After `pytest tests/test_fixture_provenance.py`, run `pytest tests/snapshot` and
the affected import/split suites. See [runtime tests](../../../tests/snapshot/AGENTS.md)
for replay boundaries and golden observations. Provenance changes also require
`tests/test_governance.py`; performance measurements are opt-in and do not replace
these correctness tests.
