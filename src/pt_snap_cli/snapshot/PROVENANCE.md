# Snapshot Runtime Provenance

## Source and license

- Source repository: <https://github.com/codeasier/MemSnapDump>
- Source tag: `v0.1.0`
- Source commit: `87ea207372e0985790e1a28dab499dccf3c3b9a4`
- First-party migration date: 2026-07-31
- Original copyright identity: Copyright (c) 2026 Liu Yekang / `codeasier`
  <liuyekang@huawei.com>
- License: MIT; terms are retained in `src/pt_snap_cli/snapshot/LICENSE`.
- Relicensing evidence: `docs/legal/memsnapdump-mit-relicensing.md`

Liu Yekang confirmed sole authorship and copyright ownership, the absence of
unaccounted copied or third-party contributed code, and the MIT grant for this
pt-snap-cli integration. The evidence file records the dated confirmation and
corroborating repository audit.

## Retained source mappings

Every URL is fixed to the audited commit rather than a moving branch or tag.

| First-party path | Audited upstream blob |
| --- | --- |
| `snapshot/__init__.py` | <https://github.com/codeasier/MemSnapDump/blob/87ea207372e0985790e1a28dab499dccf3c3b9a4/src/memsnapdump/__init__.py> |
| `snapshot/base/__init__.py` | <https://github.com/codeasier/MemSnapDump/blob/87ea207372e0985790e1a28dab499dccf3c3b9a4/src/memsnapdump/base/__init__.py> |
| `snapshot/base/entities.py` | <https://github.com/codeasier/MemSnapDump/blob/87ea207372e0985790e1a28dab499dccf3c3b9a4/src/memsnapdump/base/entities.py> |
| `snapshot/simulate/__init__.py` | <https://github.com/codeasier/MemSnapDump/blob/87ea207372e0985790e1a28dab499dccf3c3b9a4/src/memsnapdump/simulate/__init__.py> |
| `snapshot/simulate/allocator_context.py` | <https://github.com/codeasier/MemSnapDump/blob/87ea207372e0985790e1a28dab499dccf3c3b9a4/src/memsnapdump/simulate/allocator_context.py> |
| `snapshot/simulate/allocator_hook_dispatcher.py` | <https://github.com/codeasier/MemSnapDump/blob/87ea207372e0985790e1a28dab499dccf3c3b9a4/src/memsnapdump/simulate/allocator_hook_dispatcher.py> |
| `snapshot/simulate/hooker_defs.py` | <https://github.com/codeasier/MemSnapDump/blob/87ea207372e0985790e1a28dab499dccf3c3b9a4/src/memsnapdump/simulate/hooker_defs.py> |
| `snapshot/simulate/replay_executor.py` | <https://github.com/codeasier/MemSnapDump/blob/87ea207372e0985790e1a28dab499dccf3c3b9a4/src/memsnapdump/simulate/replay_executor.py> |
| `snapshot/simulate/simulate.py` | <https://github.com/codeasier/MemSnapDump/blob/87ea207372e0985790e1a28dab499dccf3c3b9a4/src/memsnapdump/simulate/simulate.py> |
| `snapshot/simulate/simulated_caching_allocator.py` | <https://github.com/codeasier/MemSnapDump/blob/87ea207372e0985790e1a28dab499dccf3c3b9a4/src/memsnapdump/simulate/simulated_caching_allocator.py> |
| `snapshot/simulate/snapshot_lookup.py` | <https://github.com/codeasier/MemSnapDump/blob/87ea207372e0985790e1a28dab499dccf3c3b9a4/src/memsnapdump/simulate/snapshot_lookup.py> |
| `snapshot/simulate/snapshot_mutator.py` | <https://github.com/codeasier/MemSnapDump/blob/87ea207372e0985790e1a28dab499dccf3c3b9a4/src/memsnapdump/simulate/snapshot_mutator.py> |
| `snapshot/tools/adaptors/database/__init__.py` | <https://github.com/codeasier/MemSnapDump/blob/87ea207372e0985790e1a28dab499dccf3c3b9a4/src/memsnapdump/tools/adaptors/database/__init__.py> |
| `snapshot/tools/adaptors/database/defs.py` | <https://github.com/codeasier/MemSnapDump/blob/87ea207372e0985790e1a28dab499dccf3c3b9a4/src/memsnapdump/tools/adaptors/database/defs.py> |
| `snapshot/tools/adaptors/database/entity2record.py` | <https://github.com/codeasier/MemSnapDump/blob/87ea207372e0985790e1a28dab499dccf3c3b9a4/src/memsnapdump/tools/adaptors/database/entity2record.py> |
| `snapshot/tools/adaptors/database/snapshot_db.py` | <https://github.com/codeasier/MemSnapDump/blob/87ea207372e0985790e1a28dab499dccf3c3b9a4/src/memsnapdump/tools/adaptors/database/snapshot_db.py> |
| `snapshot/tools/adaptors/snapshot2db.py` | <https://github.com/codeasier/MemSnapDump/blob/87ea207372e0985790e1a28dab499dccf3c3b9a4/src/memsnapdump/tools/adaptors/snapshot2db.py> |
| `snapshot/util/__init__.py` | <https://github.com/codeasier/MemSnapDump/blob/87ea207372e0985790e1a28dab499dccf3c3b9a4/src/memsnapdump/util/__init__.py> |
| `snapshot/util/file_util.py` | <https://github.com/codeasier/MemSnapDump/blob/87ea207372e0985790e1a28dab499dccf3c3b9a4/src/memsnapdump/util/file_util.py> |
| `snapshot/util/logger.py` | <https://github.com/codeasier/MemSnapDump/blob/87ea207372e0985790e1a28dab499dccf3c3b9a4/src/memsnapdump/util/logger.py> |
| `snapshot/util/sqlite_meta.py` | <https://github.com/codeasier/MemSnapDump/blob/87ea207372e0985790e1a28dab499dccf3c3b9a4/src/memsnapdump/util/sqlite_meta.py> |
| `snapshot/util/timer.py` | <https://github.com/codeasier/MemSnapDump/blob/87ea207372e0985790e1a28dab499dccf3c3b9a4/src/memsnapdump/util/timer.py> |

`snapshot/representation.py` is a pt-snap-cli-local shared loader/replay
entrypoint and has no direct upstream blob.

## Slice source mappings

| First-party path | Audited upstream blob |
| --- | --- |
| `snapshot/tools/slice_dump/__init__.py` | <https://github.com/codeasier/MemSnapDump/blob/87ea207372e0985790e1a28dab499dccf3c3b9a4/src/memsnapdump/tools/slice_dump/__init__.py> |
| `snapshot/tools/slice_dump/dump.py` | <https://github.com/codeasier/MemSnapDump/blob/87ea207372e0985790e1a28dab499dccf3c3b9a4/src/memsnapdump/tools/slice_dump/dump.py> |
| `snapshot/tools/slice_dump/hooker.py` | <https://github.com/codeasier/MemSnapDump/blob/87ea207372e0985790e1a28dab499dccf3c3b9a4/src/memsnapdump/tools/slice_dump/hooker.py> |

The upstream standalone split frontend is deliberately excluded, not deferred:
<https://github.com/codeasier/MemSnapDump/blob/87ea207372e0985790e1a28dab499dccf3c3b9a4/src/memsnapdump/tools/split.py>.

## Local modifications

- Commit `7a40d5c` retained the minimum import/replay closure and rewrote package
  imports for pt-snap-cli.
- Commit `a14ff77` added `PRAGMA journal_mode = MEMORY`, `PRAGMA synchronous =
  OFF`, and `PRAGMA cache_size = -65536` to the replaceable database writer.
- Commit `9740b3c` added indexes for trace `allocated`, `active`, and `reserved`
  columns and block `alloc_event_id`, `free_event_id`, and `size` columns.
- On 2026-07-31, Task 4 relocated the closure to `pt_snap_cli.snapshot`, rewrote
  internal/service/test/benchmark/CI imports, and removed the empty `vendor`
  package.
- Task 4 added `representation.py` so import pickle loading, device snapshot
  construction, hook registration, and replay pass through shared first-party
  functions designed for later split reuse.
- Task 4 removed standalone argparse parsing, exit codes, `main()`, timer wiring,
  and the module-entrypoint block from `snapshot2db.py`; callable `dump()` and
  `run_dump_to_db()` behavior remains retained.
- Task 4 mechanically formatted the snapshot tree with Black and applied Ruff's
  safe import, typing, f-string, export, and literal cleanups. The targeted
  `B024`/`B027` suppression preserves optional no-op allocator callbacks, and
  the targeted `B904` suppression preserves established corrupt-pickle exception
  context. No behavior-altering modernization was applied.
- On 2026-07-31, Tasks 5 and 6 ported `tools/slice_dump/{__init__.py,dump.py,hooker.py}`
  to the first-party namespace. Package imports and formatting changed; the
  standalone argparse parser and module-entrypoint block were removed. Callable
  engine return values, warnings, replay strategy, and legacy engine filenames
  remain unchanged.
- The product `SplitService` deliberately replaces the engine filenames with
  `<source-stem>__device-<id>__slice-<index>.<ext>`, selects every nonempty
  device when no device is requested, requires exactly one positive strategy,
  and replay-validates normalized pickle/JSON output before exclusive atomic
  directory publication. These are pt-snap product-boundary differences, not
  claims of byte-for-byte upstream frontend equivalence.
- `representation.py` now provides explicit pickle/JSON load, save, and
  serialization APIs, one load/replay validation path, and strict canonical
  bytes/SHA256 helpers for cross-format equivalence tests.
- The first-party slice payload extends the pinned upstream representation with
  an explicit `id` on every trace entry. This preserves the original snapshot's
  global event IDs across slice boundaries without mutating source `_origin`
  dictionaries. `TraceEntry` loading honors explicit IDs while retaining
  enumeration fallback for original snapshots, so established import
  observations remain unchanged. Upstream comparisons therefore treat IDs and
  product filenames as intentional required differences while continuing to
  compare selected devices, event ranges, allocator state, and slice counts.
- On 2026-07-31, PR #81 follow-up replaced quadratic front insertion in the
  slice event buffer with append plus reversal at serialization time. This
  preserves trace order while making buffer construction linear.
- A later PR #81 review follow-up corrected device upper/lower bounds in the
  retained representation and direct slice entrypoint, made direct JSON output
  explicitly UTF-8, corrected the slice initialization sentinel, and ensured a
  failed staging identity probe closes its newly opened descriptor.
- On 2026-08-01, PR #81 follow-up deferred slice buffer and boundary-state
  cleanup until serialization succeeds, preserving retryable state on I/O
  failure.
- On 2026-08-06, PR #82 optimized snapshot replay mutation and adjacent
  segment lookup by reusing discovered indices and standard-library keyed
  binary search. This is a local performance change against the first-party
  runtime; audited upstream source mappings and license terms are unchanged.
- On 2026-08-07, issue #84 added an internal database-import-only raw frame
  path and generator-based callstack formatting. Public snapshot construction
  remains eager, while database replay avoids reconstructing per-event `Frame`
  objects and preserves source frame dictionaries through synthetic segments.
  This is a local performance change; audited upstream mappings and licensing
  evidence are unchanged.
- On 2026-08-19, issue #98 added a first-party dump-time torch-npu workspace
  pool correction after inactive-block filtering. `_adapt_workspace_snapshot`
  is not present in audited MemSnapDump @87ea207; this is a local
  reimplementation of the grouping behavior specified in #98. Consecutive
  `workspace_snapshot` + `segment_alloc` + `alloc` groups rewrite the
  matching dump-time segment to a single `active_allocated` block and
  update device allocated/active totals. Size mismatches, missing
  segments, internally inconsistent triplets, and leftover live blocks
  warn and stop later groups. `workspace_flag` remains a
  fallback for unmatched workspace traces. Audited upstream source
  mappings and license terms are unchanged.
- On 2026-08-19, issue #97 made OOM trace loading tolerate missing `addr`/`stream`,
  read `device_free`, and mapped `"oom"` to action value `8` so import persists the
  event as an integer. Replay still skips OOM. This is a local first-party bugfix;
  audited upstream mappings and licensing evidence are unchanged.
- On 2026-08-19, issue #99 replaced unrestricted `pickle.load()` in
  `snapshot/util/file_util.py` with `SafeUnpickler`. Unpickling now allows only
  `builtins` container and scalar types (`dict`/`list`/`tuple`/`set`/`str`/
  `int`/`float`/`bool`/`bytes`/`NoneType`); any other `module.name` raises
  `UnpicklingError`. Import and split share this loader via
  `representation.load_pickle_representation`. The change tightens the
  deserialization allowlist; pickle loading remains not a sandbox. Corrupt
  streams still map to the established generic `UnpicklingError` wrapper.
- On 2026-08-19, PR #102 follow-up kept that wrapper prefix and path, and chained
  the original `UnpicklingError` so allowlist rejections keep the rejected
  `module.name` in the message and `__cause__`.
- On 2026-08-20, PR #102 follow-up removed `NoneType` from `ALLOWED_CLASSES`.
  `builtins.NoneType` is not an importable builtin (`hasattr(builtins, "NoneType")`
  is false); `None` is encoded by the `NONE` opcode. A GLOBAL of
  `builtins.NoneType` is now `UnsafePickleError` rather than an `AttributeError`
  swallowed as a corrupt-stream wrapper. `UnsafePickleError` subclasses
  `pickle.UnpicklingError`. Import maps it to `Snapshot pickle rejected:` and
  split maps it to `unsafe pickle:` so allowlist rejection is distinct from
  corrupt input. `dump()` re-raises `UnsafePickleError` instead of returning
  false.
- On 2026-09-06, issue #113 deduplicated database callstacks. A new local
  `snapshot/tools/adaptors/database/callstack.py` interns one id per distinct
  callstack text, `trace_entry_<device>` stores `callstackId` instead of an
  inlined `callstack` text column, and a shared device-suffix-free `callstack`
  table holds the text. `TraceEntry.callstack_frames()` exposes the frame
  container that already backed `get_callstack()` so interning can key on
  container identity; the interner holds a reference to every keyed container so
  an `id()` key cannot be reused by an unrelated object. `CallstackInterner` is
  not present in audited MemSnapDump @87ea207; it is a local addition.
  `sqlite_meta.SqliteTable.get_insert_values_by_records` now resolves per-column
  value maps once per batch instead of once per cell, and the default insert
  batch size moved from 1000 to 10000 because import stages rows in a temporary
  database and only publishes after a successful replay. Allocator replay,
  synthetic event and block identities, totals, and callstack text are
  unchanged: on `snapshot_with_multi_devices.pkl`, `snapshot_expandable.pkl`,
  `snapshot_with_empty_cache_expandable.pkl`,
  `snapshot_import_131k_sanitized.pickle`, and
  `snapshot_import_628k_sanitized.pickle`, every trace and block row matches the
  pre-change output after resolving `callstackId` through the join. This is a
  local performance and schema change; audited upstream source mappings and
  license terms are unchanged.

## Migration toolchain

- Ruff: `0.15.8`
- Black: `26.3.1` (CPython 3.13.11)

These are the actual versions queried and used during the 2026-07-31 migration.

## Future update policy

This record is append-only. The snapshot maintainer owns it and must append an
entry for every future update under `src/pt_snap_cli/snapshot/`, recording the
date, affected scope, source or local-change identity, and reason. Existing
source mappings, modification history, and licensing evidence must not be
rewritten or removed; corrections are appended with their rationale.
