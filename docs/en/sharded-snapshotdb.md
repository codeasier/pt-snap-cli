# Sharded SnapshotDB protocol (P0, compatibility v1)

[中文](../zh/sharded-snapshotdb.md) | English

## Scope and versions

This freezes an artifact contract and shared validation models, **not a new CLI
exporter or cross-slice query engine**. Existing `import` still defaults to one
native v2 DB; `split` still produces replayable pickle/JSON. Existing single-DB
v1/v2 single-DB analysis is unchanged. The P1 reader below additionally accepts a
complete compatibility-v1 manifest or directory as focus. The `complete` gate
applies only to datasets, not to legacy single-DB analysis.

`pt_snap_cli.core.dataset_contract` provides `parse_manifest`,
`validate_event_ids`, `validate_dataset`, immutable manifest/device/slice models,
`QueryScope`, and `DatasetContractError` (`location`, `code`). Producers can share
the same prepublication contract with readers. Validation never loads pickle,
creates missing databases, migrates SQLite, or writes focus.

Separate version axes:

- `schemaVersion=1`: manifest and compatibility base-table contract defined here.
- `pt_snap_metadata.import_format_version`: existing pt-snap importer format,
  currently 2; **not** the manifest version and not required for external artifacts.
- Future structured-frame extensions have their own version. Unknown extensions
  do not invalidate base reading or imply structured-frame support.

## Layout and manifest

The producer convention is `<original snapshot path>.msinsight/manifest.json`
with `device_<id>/slice_<index:05d>.db` relative to that artifact directory.
An explicitly supplied relocated directory can be validated; `sourceFile` records
origin, not a path to open. Never load the source pickle during inspection.

```json
{
  "schemaVersion": 1,
  "status": "complete",
  "sourceFile": "/capture/snapshot.pkl",
  "cacheHash": "producer-specific-opaque-identity",
  "eventsPerSlice": 2,
  "devices": {
    "0": {
      "eventCount": 4,
      "sliceCount": 2,
      "readySlices": [0, 1],
      "slices": [
        {"index": 0, "startEventId": 0, "endEventId": 1, "file": "device_0/slice_00000.db", "ready": true},
        {"index": 1, "startEventId": 2, "endEventId": 3, "file": "device_0/slice_00001.db", "ready": true}
      ]
    }
  }
}
```

All fields shown are required. Integers are not booleans/floats; counts/ranges
fit signed 64-bit integers, version/index/sliceCount/device IDs fit nonnegative
signed 32-bit integers. Device keys are canonical decimal IDs (`0`, not `00`).
`sourceFile` is nonempty. `cacheHash` is an opaque producer token, possibly empty
for an external artifact: it is **not** assumed to be SHA-256 or proof of source
content. A future cache must distinguish source content and producer/format,
base/extension versions, selected devices, capacity, and finalized generation;
source path, size/mtime, `cacheHash` alone, or a per-slice index is insufficient.
This P0 module performs no cache reuse.

`building` permits partial readiness for `parse_manifest(...,
require_complete=False)` inspection only. It still declares the complete planned
range layout. `complete` requires all slices ready **after identity/lifecycle
backfills finish**. Readiness indices must be unique, in range, and agree with each
slice's boolean. `validate_dataset` accepts only complete datasets with every
file present. Missing files are not created. Duplicate JSON members are rejected.

Per device, slices are in index order starting at 0; inclusive ranges continuously
cover `0..eventCount-1` without overlap/gaps. Each range has at most
`eventsPerSlice` real events (short intermediate slices are legal). Count real
positions, not `max(id)+1`. Compatibility v1 **rejects nonzero-start, sparse,
reordered or duplicate original real IDs**; no silent renumbering. Empty devices
and static-only devices cannot be represented: reject a requested such device,
never invent event 0. An all-empty dataset is rejected. Other devices may be
explicitly selected, but omission must be disclosed by the producer.

Paths must be exactly the declared device/index relative path: no absolute/drive/
UNC paths, `..`, `.`, empty components, backslashes, NUL, device mismatch, aliases
or symlink members/parents. Validation uses read-only SQLite (`mode=ro`) and closes
all handles, including failures. These checks are not an OS sandbox or a
concurrent-publication lock.

## Fixed base SQLite schema

Each slice has **actual tables**, not compatibility views, for exactly its device:
`trace_entry_<id>`, `block_<id>`, and `dictionary`. Their column order is normative
because the upstream reader uses positional `SELECT *`. Native v2 `callstackId`
is not a compatible substitute for inline text.

| Table | Columns, in order (SQLite declared type) |
| --- | --- |
| `trace_entry_<id>` | `id INTEGER PRIMARY KEY`, `action INTEGER`, `address INTEGER`, `size INTEGER`, `stream INTEGER`, `allocated INTEGER`, `active INTEGER`, `reserved INTEGER`, `callstack TEXT` |
| `block_<id>` | `id INTEGER PRIMARY KEY`, `address INTEGER`, `size INTEGER`, `requestedSize INTEGER`, `state INTEGER`, `allocEventId INTEGER`, `freeEventId INTEGER` |
| `dictionary` | `table TEXT`, `column TEXT`, `key TEXT`, `value TEXT` |

The dictionary stores decimal integer keys as text, with the actual suffixed
table name and column name. Each slice includes all these exact mappings:

| Column | Key → value |
| --- | --- |
| `trace_entry_<id>.action` | `0 → segment_map`, `1 → segment_unmap`, `2 → segment_alloc`, `3 → segment_free`, `4 → alloc`, `5 → free_requested`, `6 → free_completed`, `7 → workspace_snapshot` |
| `block_<id>.state` | `-1 → inactive`, `0 → active_pending_free`, `1 → active_allocated` |

No unknown base action/state is accepted. In particular, native pt-snap's `oom=8`
is outside this pinned compatibility baseline; a future exporter must reject it
or define a separately negotiated extension, not relabel it. Metrics and sizes
are bytes; event IDs are chronological identities, **not timestamps**.

## Boundary events and block lifetimes

- Real events have nonnegative original IDs. `eventCount`, capacity, ranges and
  real-event peaks count/filter only `id >= 0`.
- Negative trace IDs are separately identified synthetic left-boundary state rows
  (`segment_map=0` or `segment_alloc=2`). They may have large memory totals but
  must not compete for a real-event peak or consume capacity. IDs are slice-local;
  `(device, slice, negative ID)` identifies a boundary row. Repeated boundary
  segments do not represent new real allocations. Validation reports
  `real_event_count` and `boundary_event_count` separately; it does not execute peaks.
- Resolved block identity is `(device ID, original allocation event ID)`;
  `block.id == allocEventId >= 0` stays stable across every slice containing it.
  Reusing an address after a free creates a **different** block. Never deduplicate
  by address or by a slice-local row number.
- Preexisting/unresolved blocks have stable, dataset/device-local negative
  `block.id` values and `allocEventId=-1`. Repeated appearances keep their ID;
  distinct objects at the same address must not collide. Negative identity is
  not a known allocation event; a future enhanced identity/coverage table may
  distinguish preexisting from other unresolved cases.
- `freeEventId=-1` means no observed free (live **or unknown**, not proof of a leak).
  Otherwise it is a real ID in the device trace, not earlier than a known alloc.
  `allocEventId=-1` means unknown/preexisting, not event 0. Other negative
  lifecycle sentinels are invalid. Full finalized IDs/lifetimes may point outside
  a slice's range. Slice observations may differ in state, but repeated IDs must
  agree on address, size, requested size, alloc/free IDs. Finalization cannot
  leave temporary placeholder IDs for a resolved allocation.

The base format cannot prove that two colliding unresolved records are distinct
if a producer has discarded their identity; correct producer tracking is required.

## Extensions, scopes and capabilities

Keep optional metadata, deduplicated stacks and ordered frames in isolated
`pt_snap_*` extension tables or sidecars, never append columns to positional base
tables. In particular, **do not attach an unprefixed native `callstack` table to
inline v1**: the existing pt-snap layout detector correctly considers it a v1/v2
conflict. Native v2 remains a separate single-DB layout, not this compatibility
base. `pt_snap_metadata` and auxiliary reference tables are optional here.

Unknown `extensions` declarations/tables are ignored by base validation.
`DatasetValidation.text_callstacks=True` means an inline text column is available,
not that every event has a stack. `structured_frames=False` remains false even
when a manifest claims frames: complete structured-frame capability requires a
recognized extension version, ordered frame rows, valid references and coverage,
which P0 does not implement. Text stacks cannot substitute for these guarantees.

`QueryScope.validate(manifest)` defines selectors, not execution support:

| Scope | Required selectors and extent |
| --- | --- |
| `dataset` | No selectors; all declared devices and their full real traces |
| `device` | `device_id`; one declared device's full real trace |
| `slice` | `device_id`, `slice_index`; exactly that slice's real interval, boundary separate |
| `event_range` | `device_id`, inclusive `start_event_id/end_event_id` within the real trace, possibly across slices |

There is no global event order across devices. Boundary IDs cannot be range
endpoints. P0 `DatasetValidation.query_execution=False` describes validation,
not execution. P1 accepts complete manifests/directories through the resolver
below; cross-slice execution remains deferred.

```python
from pt_snap_cli.core.dataset_contract import QueryScope, validate_dataset

inspection = validate_dataset("/capture/snapshot.pkl.msinsight")
QueryScope("event_range", device_id=0, start_event_id=1, end_event_id=3).validate(
    inspection.manifest
)
assert not inspection.structured_frames
```

## Complete dataset focus and addressing (P1)

A relocated compatibility-v1 directory or its `manifest.json` can be focused
without the original pickle, import metadata, or reference/extension tables:

```bash
pt-snap focus /capture/snapshot.pkl.msinsight --device 0 --json
pt-snap overview --json
pt-snap query --template-use event --params '{"id": 3}' --json
pt-snap query --template-use event --slice 1 --json
```

`overview.dataset` reports format, manifest version/status, content fingerprint,
real/boundary counts, per-device slice paths/ranges and capabilities. Event bounds
exclude negative synthetic rows (also for standalone DB overview). Text stacks
are available, but not necessarily populated; structured frames and cross-slice
queries are **unavailable**, including when unknown extensions claim them.
Dataset-wide import metadata is unavailable; per-slice metadata is not a source
attestation for the entire dataset.

Path precedence stays explicit → `PT_SNAP_DB_PATH` → nearest project focus → legacy
global config; device precedence stays explicit → focused → first discovered.
CLI focus only writes the chosen project/global focus file, never the artifact or
detected layout. API session focus does not write it:

```python
from pathlib import Path
from pt_snap_cli import SnapshotAnalyzer

with SnapshotAnalyzer(Path("/capture/snapshot.pkl.msinsight"), device_id=0) as analyzer:
    event = analyzer.execute_query("event", {"id": 3})
    page = analyzer.execute_query("event", slice_index=1, exact_total=True)
    print(event["scope"], page["total_is_exact"])
```

Only the `event` template is currently supported through dataset focus: a real ID
routes to its containing slice; an inclusive `min_id/max_id` range must fit one
slice; `--slice`/`slice_index` lists that slice's real events. Negative IDs are not
whole-dataset selectors. Output `scope` identifies the actual DB/device/slice,
restricted real interval, dataset fingerprint and boundary exclusion. Totals and
pagination apply to this scope, **not** to an implicitly truncated full dataset.
Caller parameter defaults in CLI `effective_params` are additionally constrained
by `scope`. Cross-slice ranges, unbounded multi-slice queries and aggregate or
lifecycle templates fail explicitly; they never silently choose the first/latest
slice. Direct single-DB v1/v2 queries retain their existing semantics.

`core.dataset_resolver.DatasetResolver.inspect(path)` returns an immutable
`ResolvedDataset` (or `None` for a standalone DB). Its `paths(QueryScope(...))`
addresses all matching files even for a cross-slice range, but does not execute it.
It revalidates the finalized P0 contract on each call and hashes the manifest and
members; no unbounded manifest/connection cache is retained. Hashing uses bounded
chunks and is proportional to artifact size, not a performance claim. Context LRU
size defaults to four; dataset generation changes invalidate contexts on next
lookup even when size/mtime are unchanged. Analyzer-owned caches close on exit;
injected caches remain caller-owned. Validation opens/closes slices sequentially.

Building, missing/inconsistent slices, unknown base versions and unsafe paths
are rejected before focus writes or query execution. Before opening **any** slice,
the resolver checks every member's canonical non-symlink path, SQLite header and
WAL/journal/SHM sidecars (including dangling symlinks). Persistent WAL mode is
rejected even after checkpointing has removed its sidecars: `mode=ro` can recreate
them. The reader does not repair, checkpoint, delete sidecars or change journal
mode; standalone DB behavior is unchanged. This is read-only inspection, not a
filesystem sandbox or a concurrent producer lock. Native-v2 replay's private staging directory has **no published manifest**
and is rejected as a dataset; its individual DBs remain readable via the existing
single-DB entry. A future compatibility-v1 producer can use this same reader
without producer-specific metadata. No native-v2 manifest protocol, exporter,
cache publication, migration, or cross-slice lifecycle reconstruction is invented.

## Internal continuous replay (P1)

`core.sharded_replay_service.ShardedReplayService.stage(source, directory,
events_per_slice=..., device=None)` is an **internal producer boundary**, not a
new CLI/API import command. It loads trusted pickle once, constructs one persistent
simulator per selected event-bearing device, and writes windows from last to first
into a new, caller-owned **private staging directory**. `omitted_devices` discloses
all unselected/empty device positions. Existing `import`, `split`, `SnapshotAnalyzer`
and single-DB v1/v2 reading are unchanged.

The returned immutable result identifies **native-v2** slices, not compatibility-v1
artifacts: trace rows use `callstackId` plus a local `callstack` table and retain
native OOM action 8 and workspace events. Sparse/nonzero-start native real IDs are
preserved if nonnegative, unique and chronological; windows count list positions,
not `max(id)+1`. These native slices are **not** accepted by `validate_dataset`.
Compatibility export, a compatible manifest, cache/publication and dataset queries
remain separate work. No `manifest.json`, `readySlices`, or incremental ready
notification is emitted. Only a successful return after all devices finalize and
validate may be handed to later publication. Failure retains private partial
files for their owner; none is advertised as a complete dataset.

`SimulateDeviceSnapshot.replay_until(remaining_events)` undoes until that many
chronological list entries remain. The endpoint is a **position**, not an event ID;
repeated pauses/resumes share the full replay hook/error path. A real event row
records the state **after** its event (before undo). After undoing a window's first
event, active block observations and negative-ID `segment_alloc`/`segment_map`
rows reconstruct the state **before** that first event. Boundary rows do not count
against capacity or real-event peaks.

A device-local registry retains original block objects across writer switches,
not copied hook payloads or an address-only key. Allocation replay resolves every
appearance to the original alloc ID; unknown/preexisting lifetimes retain stable
negative identities. All writers close before per-DB transactional batch backfill
and validation. `freeEventId` stays `free_completed`, never `free_requested`;
boundary `active_pending_free` observations remain state 0. Address reuse and
same-address different-stream blocks remain distinct. Each native slice adds
`pt_snap_block_reference(blockId, stream, allocCallstack, freeCallstack)` so finalized
out-of-slice lifecycle references do not discard their text stack sources. NULL
means no observed source event; empty text means the observed event had no frames.
Legacy slice-local query JOINs do not automatically consume this internal table;
this is not a cross-slice query engine or structured-frame extension.

Pickle may still load entirely. Sharding bounds **real events per DB**, not block
rows, total staged bytes, registry size, or peak RSS. Synthetic regressions and
reviewed expandable/multi-device fixtures cover replay equivalence and resource
failure paths; no live upstream GUI or performance acceptance is claimed.

## Evidence and limits

Interoperability facts were read from fixed upstream
[manifest validation](https://github.com/Ascend/msinsight/blob/101f65b877a267ffd5f66ea3834706057ba243e5/server/src/modules/memsnapshot/service/MemSnapshotSliceService.cpp),
[positional SQLite reading](https://github.com/Ascend/msinsight/blob/101f65b877a267ffd5f66ea3834706057ba243e5/server/src/modules/memsnapshot/database/MemSnapshotDatabase.cpp),
[base schemas](https://api.github.com/repos/Ascend/msinsight/git/blobs/1fe50a5136f85365db55f4632d58f3cf7090431e),
and [publication/backfills](https://api.github.com/repos/Ascend/msinsight/git/blobs/95612509ef990ac6b7034919dae4938cc6acf3ad).
Those source files carry Huawei's Mulan PSL v2 notice. This contract, Python
validator and synthetic tests are original local implementation of interface
facts; no upstream implementation is copied into the package. The upstream docs
license is separately CC BY 4.0, not a replacement for those source notices.

Our complete-readiness and canonical-path rules are intentionally stricter than
the upstream parser (which also supports building). Synthetic contract tests and
source-function comparisons are not GUI acceptance, native exporter acceptance,
performance measurements, or proof of interoperability with a different revision.
