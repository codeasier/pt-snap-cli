# Querying

[中文](../zh/querying.md) | English

Run memory analysis queries against your snapshot database.

Use the catalog's SAME YAML `dataset_support`/declared row fields and an explicit
validated target/device/scope. [Offline acceptance and measured query latency](interop-acceptance.md)
separate source/range/frame coverage from `has_more`/`truncated`, explain text-only
downgrades and all-action stack statistics, and retain included-byte denominators.
Bounded `report peak-memory --start-id ... --end-id ...` uses the SAME selected
metric event for gap/active attribution/coverage; custom SQL/overrides remain
unsupported for whole datasets. Measurements are not speed assertions.

## The Query Command

```bash
pt-snap query [DB_PATH] [--template-use <template_name>] [--params <json>] \
  [--device <id>] [--list] [--category <category>] \
  [--template-info <template>] [-n <rows>] [--exact-total] [--timeout <seconds>] [--json]
```

**Parameters:**

| Flag | Description |
|------|-------------|
| `db_path` | Standalone SQLite file or COMPLETE validated dataset directory/manifest (optional if focus is configured) |
| `--template-use` | Query template name (required unless using `--list` or `--template-info`) |
| `--params` | Query parameters in JSON format |
| `--device` | Device ID |
| `--list` | List available query templates |
| `--category` | Filter templates by category: `basic`, `statistical`, `business` |
| `--template-info` | Show template details (parameters, output schema, and field semantics) |
| `-n` | Maximum displayed rows; zero or a negative value means unlimited. Separate from `--timeout`. |
| `--exact-total` | Count the complete matching set: standalone SQL COUNT or dataset post-merge count. Default `total` is returned rows. |
| `--timeout` | Wall-clock budget for one `query` / `QueryService` call (page query and optional `--exact-total` COUNT share it) via a SQLite progress handler. `<= 0` disables. Default: `PT_SNAP_QUERY_TIMEOUT` or unlimited. The environment variable applies to every template query, including `report peak-memory`. |
| `--json` | Emit machine-readable JSON (execute, `--list`, and `--template-info`) |

## Compact callstack text

`event` and `active_memory_callstack_at_event` accept the explicit opt-in
`stack_bytes` parameter. `report peak-memory` accepts `--stack-bytes` for its
callstack groups. The default `-1` (or any negative value) preserves full text
and the existing row shape. `0` returns identity-only stack text; a positive
value returns a UTF-8-safe prefix of at most that many bytes per callstack.

```bash
pt-snap query '<db_path>' --device 0 --template-use event --params '{"action":0,"limit":1000,"stack_bytes":256}' --json
pt-snap query '<db_path>' --device 0 --template-use active_memory_callstack_at_event --params '{"event_id":100,"top_n":20,"stack_bytes":256}' --json
pt-snap report peak-memory '<db_path>' --device 0 --stack-bytes 256 --json
```

Replace the path, device and event with values from your database. The Python
API uses the same parameter through
`analyzer.execute_query("event", params={"stack_bytes": 256, "limit": 1000})`.
Discover support and field definitions through `capabilities --json` or template
info; other templates do not accept this parameter.

Each compact row adds `stack_id`, `stack_kind`, `stack_event_id`, `stack_bytes`
(effective budget), `stack_original_bytes` and `stack_truncated`. Numbers and
`category` remain unchanged. The budget applies only to the UTF-8 text value:
JSON escaping, identity and other metadata consume additional bytes. It is
neither a hard response-size cap nor a model-token budget. A short prefix may
end within a frame; retrieve full text before interpreting omitted frames.

`stack_truncated` signals **text shortening**, independently of the query's
`has_more`, `truncated`, `total` and `total_is_exact`, which still describe the
evidence row set. A complete row set can contain shortened text. Report row
limits retain their existing semantics; text summaries do not prove coverage.

Within the same unchanged database/device, use `stack_id` for identity: v1 uses
the SHA-256 of the full captured text; v2 uses the actual `callstackId` (identical
text can have different IDs). Missing, static and preexisting attribution use
separate category identities. Never merge groups by the prefix or display label.
`stack_kind` distinguishes captured text from synthetic/missing attribution.

For a captured stack, use its `stack_event_id` with the **same database/device**
and omit `stack_bytes` to retrieve the full text:

```bash
pt-snap query '<db_path>' --device 0 --template-use event --params '{"id":123}' --json
```

Replace `123` with the returned locator. This representative event is not the
group identity. Missing/static/preexisting groups have no captured allocation
stack to retrieve; omit `stack_bytes` on the original query to see their full
display labels. Results are read-only and summaries do not change the database.

## Dataset-global built-in support (P3)

Complete native-v2 and compatibility-v1 datasets share the following **one-device**
query support matrix, also exposed as each catalog/template-info `dataset_support`.
Device selection stays explicit → focused → first discovered; peaks are never summed
across devices and there is no shared cross-device event order.

| Template | Dataset semantics before the final output window |
| --- | --- |
| `event`, `allocation` | Filter all selected real events, globally sort with the declared ID tie-break, then offset/limit/max_rows; negative boundaries excluded |
| `memory_peak` | Independent allocated/active/reserved maxima over real events; earliest real ID wins ties; `start_id/end_id` may cross shards |
| `allocator_gap` | The same independently selected global events, with each gap computed from counters **at that event** |
| `active_blocks_at_event`, `active_memory_callstack_at_event` | Route a real event to its owner and resolve full cross-shard sources before grouping/top_n (details below) |
| `preexisting_live` | Owner-event preexisting occupancy, not a leak count |
| `block` | Merge proved allocation-event lifetimes and stable negative tokens once, then apply filters/order/page; latest containing-shard state is an observation, not state at arbitrary E |
| `freed_block_lifetime` | Deduplicated captured allocations with a proved `free_completed` source; event-ID distance buckets, not time |
| `leak_detection` | Captured dynamic lifetimes still present without completion in the **terminal dataset shard**, not union of per-shard unfreed lists; survival is only a candidate, not a confirmed leak; `--slice` is rejected |
| `callstack_analysis` | All real stack-bearing trace actions, including free/segment/workspace, merged by full canonical source identity before global thresholds/ranking; weighted `avg_size=total_size/alloc_count` |
| Runtime overrides/custom templates/arbitrary SQL | Explicitly unsupported on datasets, even when named after a built-in; pass an explicit standalone member to use local SQL |

`memory_peak` and `allocator_gap` semantics version **2** exclude negative synthetic
rows in **standalone** SQL too. `callstack_analysis` version **2** retains the legacy
`alloc_count` column name but does **not** mean allocation count: v1 counts all real
non-NULL-text rows; v2 counts all real non-NULL stack references, retaining absent/NULL
joined text as one distinct missing group. Empty text counts as its own group, separate
from missing and captured literal labels. Both standalone layouts now group full text,
not local v2 IDs. Datasets also accept explicitly covered ordered
raw arrays as stack evidence; missing text does not change raw-array identity. Size
sums include nonallocation actions and are not instantaneous live occupancy.

The shared YAML output schemas declare every optional dataset-only row column;
standalone row shapes stay unchanged. `block` and dataset `leak_detection` expose
`lifecycle_id`, proof/source statuses, source payloads, latest observation slice/state
scope, category and terminal survival; leak rows additionally retain `requestedSize`,
`state` and `freeEventId`. These observations and proofs are not leak confirmation.
Dataset statistics expose `source_stack_id`, `stack_kind`, `text_kind`,
`stack_event_id` and `frames_status`. The representative real event prefers nonempty
captured text when available but is not the canonical group identity and need not be
an allocation action; otherwise it may have empty/NULL text. `text_kind` is provenance
only and never changes raw-array identity. Retrieve actual text/arrays using `event`
on that same dataset/device; `frames_status` is not frame reconstruction.

```bash
pt-snap query '<dataset_dir>' --device 0 --template-use memory_peak --params '{"start_id":100,"end_id":700}' --json
pt-snap query '<dataset_dir>' --device 0 --template-use event --params '{"min_id":100,"max_id":700,"limit":20,"offset":20}' --exact-total --json
pt-snap query '<dataset_dir>' --device 0 --template-use leak_detection -n 20 --exact-total --json
pt-snap report peak-memory '<dataset_dir>' --device 0 --metric reserved --start-id 100 --end-id 700 --timeout 10 --json
```

Use actual bounds. Ranges may include sparse gaps; they never create an event.
An empty real range has NULL peak values/IDs. Outside/negative/reversed range
endpoints fail; `event(id=gap)` may return no rows, while active-at-gap fails.
Global filters/dedup/source identity/thresholds/sort precede the final window.
`exact_total` ignores row caps; default total is returned rows with honest exactness
flags. Result `has_more/truncated` describes the window, not source/range completeness.
`scope` records requested bounds, actual real-event coverage where applicable,
involved `slice_indices`, device, fingerprint and boundary exclusion. Source coverage
is separate. Unproved historical lifecycle identities are shard-local, explicitly
marked, never guessed by address/local stack ID and never asserted as proved leaks.

Dataset reads detach batches before foreign-owner lookups, using the borrowed bounded
Context LRU. One diminishing deadline includes all shards, sources, grouping and exact
totals; reports explicitly share **one** budget across peak selection and attribution. Cumulative
fetched/output work is limited to **100000 rows / 64 MiB serialized values**, including
repeated source reads. Exceeding either fails the entire operation, never an alleged
complete partial result. Python materialization/sort are bounded by this work ceiling, **not**
by max_rows. This is not a process RSS limit: Python/SQLite, one batch and individual
cells have overhead. Strong manifest/member validation and hashing remain the default
and share that deadline: hash chunks, Python row batches and SQLite progress handlers
check cancellation. Individual filesystem calls are not OS-level hard-preempted.
`PT_SNAP_DATASET_CACHE=immutable` explicitly opts into process-local validation reuse
only when the caller guarantees immutable finalized files and reliable filesystem
change times; see [dataset validation and cache contracts](sharded-snapshotdb.md).
No temporary merge DB, repair or artifact write.

Global peak queries fetch scalar range evidence and at most three counter rows per
shard. Event/allocation pages apply SQL filters and ordering per shard, merge at most
`offset + limit` candidates per shard, and count matches separately. Range evidence
is measured before non-range filters. Ordinary text-stack statistics merge full
per-shard groups before global thresholds; averages use summed sizes and counts.
Canonical ordered-frame statistics retain the bounded source-reading path because
formatted text is not their identity. Block/leak/lifetime reductions use read-only
attached shards for proof, conflicts and latest observations before pagination;
the attachment limit (normally ten) counts selected observation shards plus any
other shards owning their allocation/free references. Slice queries discover those
proof owners before filtering or paging; exceeding the limit retains the budgeted
source-reading path. SQLite internal scans and temporary space are not bounded by
the fetched-row/byte budget. Summary and page (or lifetime buckets) each evaluate
the full lifecycle CTE, sharing the same deadline. No intermediate merged database
is created.

A million-event dataset can therefore answer aggregates and small pages within the
default work budget. Use `-n 5` or an explicit finite `limit` for large row-returning
queries. Unlimited output, large offsets, many distinct stack groups, ordered-frame
reads or the attachment-limit fallback can still exceed the budget and fail honestly.
The limit counts rows fetched into Python and serialized output, not internal SQL
scans, SQLite sorting space or total process memory.

## Dataset point-event attribution

A complete compatibility-v1 or native-v2 directory/manifest supports `event`
addressing plus `active_blocks_at_event` and `active_memory_callstack_at_event`
with a real `event_id`. The latter two route one device's actual event and use
its shard's complete lifecycle observations **after** that forward event:
`allocEventId <= E` and completed `freeEventId > E` (or `-1`). `free_requested`
does not remove active memory. Negative boundary rows represent the instant
before a shard's first event and are not query endpoints. Native sparse IDs are
not renumbered: `event(id=gap)` may return no rows inside an addressed slice;
active attribution at a nonexistent ID fails instead of inventing event 0.

```bash
pt-snap query '<dataset_dir>' --device 0 --template-use active_memory_callstack_at_event --params '{"event_id":700,"top_n":20}' --json
pt-snap query '<dataset_dir>' --device 0 --template-use active_blocks_at_event --params '{"event_id":700,"limit":10}' --exact-total --json
```

Replace the path/device/event with actual values. Foreign alloc/free events and
full v1 inline or v2 local-ID stacks are resolved **before** grouping/top_n, in
batches of at most 256 distinct event IDs per owning shard. No foreign real rows
are inserted. Original artifacts need neither metadata nor reference tables.
Lifetimes use dataset generation/device/alloc-event or stable negative identity,
not addresses; `state_scope=slice_observation` warns that stored `state` is not
necessarily the pending-free state at E. Block rows expose `allocation_source`,
`free_source`, their statuses and `lifecycle_id`. Missing dynamic sources retain
bytes and dynamic category, separate from static/preexisting unknown history.
`free=-1` means live **or unknown**, not a proven leak.

Dataset groups always expose full `source_stack_id`/`stack_id`, `stack_kind` and
`stack_event_id`. Default no-extension `event` rows keep their original nine
values; source/frame row fields appear with `stack_bytes>=0` or a recognized
ordered-frame declaration. `scope.source_coverage` is still supplied. Both dataset
layouts use full-text canonical identity; v2 looks up the owning slice's actual
local ID, returned as source `local_stack_id`/`slice_index` provenance, not a
cross-shard grouping key. Covered ordered arrays use only exact raw-frame identity,
independent of formatted text availability; `text_kind` reports that availability
separately. Explicitly covered arrays (including empty arrays) are captured raw
evidence. Groups prefer an available captured-text representative for retrieval. Nonempty whitespace and a captured literal `[missing callstack]`
are not missing. Never merge by local IDs or shortened display labels. `stack_bytes`
shortens display only; use `event(id=stack_event_id)` on the same dataset/device
for full text. Ordered raw frames, when explicitly covered, also participate in
identity; no text parsing reconstructs frames.

`scope.source_coverage` is independent of `has_more`/`truncated`/exact row totals:
active-query coverage describes **all filtered blocks before top_n/paging**, with
active/dynamic bytes, resolved allocation/free counts, captured dynamic bytes,
unknown/preexisting counts, ordered-frame coverage and degradation. For `event`,
its coverage scope is only `returned_events`. A complete manifest/range does not
prove complete historical sources or frames. Percentages still use included
bytes **after dynamic top_n but before max_rows**, not the dataset active counter.
Exact totals ignore row/rank caps, but do not change that percentage denominator.

One call shares its deadline across source batches, grouping and exact totals.
Manifest validation/hash and Context setup elapsed time are charged. Validation checks
cancellation between hash chunks and Python row batches, and within SQLite via
cleared-on-exit progress handlers. Individual filesystem calls are not hard-preempted;
no OS-level time guarantee is claimed.
The Context LRU remains bounded (default four) and borrowed caches remain caller-owned.
No merged temporary database is created. `ReportService.event_attribution(E, ...)`
reuses this same query path for a supplied event. Dataset-global queries and reports
follow the explicit support matrix above; arbitrary SQL/custom overrides never inherit
those merge semantics merely by using a built-in name.

### Optional ordered-frame reader contract

This reader-only pt-snap extension is new, not an existing original-producer
feature. Current native/compatible writers emit **no** ordered-frame tables.
Declare `extensions.ptSnapOrderedFrames={"version":1}` in the manifest and use
isolated actual tables in each covered source shard:

- `pt_snap_frame_coverage(eventId INTEGER PRIMARY KEY, frameCount INTEGER)`
- `pt_snap_frame(eventId INTEGER, frameIndex INTEGER, frameJson TEXT, PRIMARY KEY(eventId,frameIndex))`

Raw objects must be finite standard JSON, with nesting depth at most 128; deeper
or nonfinite/unparseable input degrades safely, including recursion failures.
Each covered real event needs nonnegative integer `frameCount`, exactly indices
`0..frameCount-1`, and JSON **objects** preserving all raw typed fields. Order and
repeated frames are retained; empty arrays require an explicit count zero row.
Only recognized version/schema and valid per-event coverage produce `frames`
with `frames_status=ordered`. Unknown version, missing schema/rows, invalid JSON
or incomplete coverage degrade to `frames=null`, `frames_status=text_only`;
formatted text is never split/reversed into raw frames. P0/overview's dataset-wide
`structured_frames=false` remains a conservative validation capability, not a
claim about the scoped source payload. Tree rendering and GUI acceptance are not
provided by this extension interface.

## Query Templates

Templates are organized into three categories. Use `pt-snap capabilities --json` for the full catalog (CLI version, every template contract, and bundled skills), or `pt-snap query --list` to see names and descriptions. Filter with `--category`.

### Basic Queries

Raw data lookup.

| Template | Description |
|----------|-------------|
| `block` | Query memory blocks with flexible field filters |
| `event` | Query memory events with flexible field filters |
| `allocation` | Memory allocation timeline (id, allocated, active, reserved) |

`event`, `callstack_analysis`, and `active_memory_callstack_at_event` share one
public contract and select v1 or v2 SQL from the database layout. See
[Callstack layout compatibility](database.md#callstack-layout-compatibility).

### Statistical Queries

Aggregation and analysis.

| Template | Description |
|----------|-------------|
| `callstack_analysis` | Analyze callstack information |
| `memory_peak` | Peak memory metrics |
| `active_blocks_at_event` | List blocks that are still active at a specific event, with optional static and preexisting live inclusion |
| `allocator_gap` | Compare allocated, active, and reserved peak events and same-event gaps |

### Business Queries

Domain-specific analysis.

| Template | Description |
|----------|-------------|
| `leak_detection` | Find captured allocations with no recorded free-completion event (leak candidates) |
| `active_memory_callstack_at_event` | Aggregate blocks active at a specific event by allocation callstack, with static and preexisting memory classified separately |
| `preexisting_live` | Count preexisting-live blocks at an event (`allocEventId=-1` still live, including `freeEventId IS NULL`) |
| `freed_block_lifetime` | Bucket successfully freed blocks by `freeEventId - allocEventId` distance (not elapsed time) |

## Leak Detection

```bash
pt-snap query --template-use leak_detection --params '{"min_size": 1024}'
```

`min_size` is the minimum candidate size in bytes and defaults to `0`. Select
the target device with the command-level `--device` option, not inside `--params`.
`leak_detection` returns candidates that were still live in the captured range,
not confirmed leaks. Read field units and interpretation limits with
`pt-snap query --template-info leak_detection`.

### Retrieving a complete candidate window

`leak_detection` accepts `min_size` and `limit`, but **no `offset`**. Passing
`offset` is rejected (`INVALID_PARAMETER` in CLI JSON, `TemplateRenderError`
in the Python API). `has_more: true` signals incomplete results; it does not
promise offset pagination.

Start with a bounded query. If full coverage is needed, obtain an exact count
while keeping the returned window bounded:

```bash
pt-snap query '<db_path>' --device <device_id> --template-use leak_detection --params '{"min_size":1024}' -n 100 --exact-total --json
```

Exact `total` counts matching **rows**, not bytes or GiB, and ignores `limit`.
If it is zero, report no matching candidates without rerunning with `-n 0`
(which means unlimited). If it is positive and affordable within your
memory/output budget, rerun once with `-n <positive_total>` using the same
database, device, and filters:

```bash
pt-snap query '<db_path>' --device <device_id> --template-use leak_detection --params '{"min_size":1024}' -n <positive_total> --json
```

Remove any explicit `limit` from `--params`, or raise it to the same count;
otherwise a smaller `limit` still caps the enlarged window. Verify `returned`
equals the exact count and both `has_more` and `truncated` are false. **Replace**
the earlier rows with the new result; never append overlapping windows or add
their counts/bytes. The API follows the same workflow with `exact_total=True`
and a positive `max_rows`.

If the full result exceeds the budget, keep a bounded sample and report that
candidate/byte coverage is incomplete. An exact row count does not provide the
total candidate bytes. Increasing `min_size` changes the analysis scope and
requires a new count; it cannot establish completeness for the original scope.

## Parameter Validation

`--params` is validated against the template before any SQL is rendered:

- Every key must be a parameter the template declares. Unknown keys are
  rejected instead of ignored, so a misspelled filter such as `min_sze` fails
  with `Unknown parameter(s) for template 'leak_detection': min_sze (accepted:
  min_size, limit)` rather than silently returning unfiltered results.
- Values are converted to the declared type (`int`, `float`, `str`, `bool`).
- Parameters that are rendered into SQL as identifiers or keywords, such as
  `order_by` and `order_dir`, accept only the values listed under
  `[choices: ...]` in `--template-info`. String choices match
  case-insensitively and render with the declared spelling (`desc` becomes
  `DESC`); anything else is rejected before it reaches the database.

```bash
pt-snap query --template-info allocation
#   order_by: str (optional) [choices: id, allocated, active, reserved] [default: id]
#   order_dir: str (optional) [choices: ASC, DESC] [default: ASC]

pt-snap query --template-use allocation --params '{"order_by": "reserved", "order_dir": "desc"}' -n 5
```

The same rules apply to `SnapshotAnalyzer.execute_query()`, which raises
`TemplateRenderError` with the same message.

## Peak Memory Attribution Workflow

These additions productize the common "find the peak, then explain what was live at that moment" workflow.

### 1. Find the peak event

```bash
pt-snap query --template-use memory_peak
```

This returns peak values and the corresponding event IDs for `allocated`, `active`, and `reserved`.

### 2. Inspect the blocks that were still active at that event

```bash
pt-snap query --template-use active_blocks_at_event --params '{"event_id": 1234, "include_static": true}'
```

`active_blocks_at_event` treats a block as live at `event_id` when:

- Dynamic block: `allocEventId != -1 AND allocEventId <= event_id`, and `freeEventId`
  is `NULL`, negative, or greater than `event_id`
- Block without a captured allocation event (`allocEventId = -1`): `freeEventId`
  is `NULL`, negative, or greater than `event_id`

When `include_static=true`, blocks without an allocation event that are still
live at `event_id` are also included:

- `allocEventId=-1 AND freeEventId=-1` is labeled `static`
- Other allocation-less live blocks (for example, allocated before snapshot
  collection began and freed later) are labeled `preexisting_live_at_event`

### 3. Attribute active memory to callstacks at that event

```bash
pt-snap query --template-use active_memory_callstack_at_event --params '{"event_id": 1234, "include_static": true, "top_n": 20}' -n 22 --json
```

This query:

- starts from the active block set at `event_id`
- joins dynamic blocks back to their allocation events in `trace_entry_<device>`
- groups by allocation callstack
- emits static and preexisting memory as dedicated groups instead of inventing a callstack

`top_n` only bounds dynamic callstack groups; `static` and
`preexisting_live_at_event` groups, when included and present, are exempt from
that inner filter. The outer `-n` cap still applies to all output rows and can
drop special groups or dynamic top groups. For finite positive `top_n=N` with
`include_static=true`, use `-n N+2` (substitute the computed integer: `top_n=1`
needs `-n 3`, and `top_n=20` needs `-n 22`). This preserves the ranked result,
not necessarily the full dynamic set. The representative block query has its
own `limit` / `-n` cap; it does not need two extra rows.

At fixed `top_n`, increasing `-n` preserves common rows and their percentages:
the denominator is the included groups' bytes after inner ranking but before
the outer row cap. A clipped listing need not sum to 100%. Increasing `top_n`
can change the denominator. Check completeness flags before claiming full
coverage; a full ranking window conservatively sets `has_more=true` even when
there are exactly N dynamic groups. Widen the window or use `--exact-total`
to resolve that uncertainty.

### 4. Compare peak event gaps across metrics

```bash
pt-snap query --template-use allocator_gap
```

This reports:

- the peak event for `allocated`, `active`, and `reserved`
- whether those peaks happen at the same event
- same-event gaps such as `reserved - active` and `reserved - allocated`

This is useful because `reserved` may peak at a different event from `active` or `allocated`, so subtracting peak values directly can be misleading.

## Report Command

For a higher-level summary, use the report command:

```bash
pt-snap report peak-memory [db_path] [--device <id>] [--metric active|allocated|reserved] [--include-static|--exclude-static] [--limit <n>] [--start-id <id>] [--end-id <id>] [--timeout <seconds>] [--json]
```

Examples:

```bash
# Text report using the active peak event
pt-snap report peak-memory /path/to/snapshot.db

# Report the reserved peak instead
pt-snap report peak-memory /path/to/snapshot.db --metric reserved

# Emit machine-readable JSON
pt-snap report peak-memory /path/to/snapshot.db --json
```

The report command combines:

- `allocator_gap`, whose result also supplies the six existing `peak_*` fields
- `active_memory_callstack_at_event`

and prints either a human-readable summary or JSON. `--start-id/--end-id` restrict
peak selection; attribution still resolves the complete active set at that selected
event, including earlier allocations. `--timeout` (or `PT_SNAP_QUERY_TIMEOUT`) is
one diminishing **report-wide** deadline, never reset between queries.
JSON adds peak `scope`, separate attribution `source_coverage`, `timeout_s`, and
`budget_scope="report_composition"`.

A dataset report inspects the dataset once and reuses that validated fingerprint
for peak selection and attribution. Changes to the manifest or members detected
between or during these steps reject the whole report; this is a generation check,
not a concurrent-writer lock. Counter peaks are computed once for the selected
range. Attribution still consumes the same cumulative work budget, so a very large
active set can legitimately exceed that budget even when a peak-only query succeeds.

The existing `callstack_groups` and `percent_of_active_blocks` values are preserved.
JSON also exposes attribution `has_more`, `truncated`, `total_is_exact`, and
`effective_params` (`event_id`, `include_static`, `min_size`, `top_n`). A full
dynamic `top_n` window is conservatively **possibly incomplete**, even when it
happens to contain every group. Text output labels this as partial. Increase
`--limit` within a finite budget and replace the previous result; do not add
ranked windows together. Static and preexisting groups are extra rows outside
the dynamic `--limit` cap when included.

`included_bytes` sums all returned groups. `percent_denominator: "included_bytes"`
means row percentages are byte shares of this filtered/capped set, not all active
memory or block counts. `active_bytes_at_event` is the active counter at the
**selected metric's event**, including for allocated/reserved reports.
`coverage_percent` is `100 * included_bytes / active_bytes_at_event`; it is `null`
(text: unknown) when that counter is absent or non-positive, or no event exists.
Coverage is not a completeness flag: `--exclude-static` can lower it without
truncation, and reaching the cap can remain possibly incomplete at 100% coverage.
An empty trace returns no groups, zero included bytes, and unknown coverage.

## JSON Output

`--json` writes one JSON object to stdout. Success payloads include
`schema_version` (currently `1`), `ok: true`, and command fields:

| Branch | Extra fields |
|--------|----------------|
| Execute | `db_path`, `focus_source`, `device_id`, `template`, `effective_params`, `semantics_version`, `total`, `returned`, `has_more`, `truncated`, `total_is_exact`, `timeout_s`, `rows` |
| `--list` | `category`, `templates` (`name`, `description`, `category`) |
| `--template-info` | Template metadata matching `get_template_info()`, plus `template` |
| `capabilities` | `cli_version`, full `templates` contracts, and `skills` |
| `overview` | `db_path`, `focus_source`, `devices` (`device_id`, `first_event_id`, `last_event_id`), `import_metadata` |

`-n` still caps `rows` and `returned`. By default `total` equals `returned`
(this page's row count) and `total_is_exact` is true only when the page is
the complete matching set (`has_more` is false and `offset` is 0).
`--exact-total` counts the matching set (ignoring `limit` / `offset` / `top_n`)
and sets `total_is_exact` to true. Standalone queries use SQL `COUNT`; dataset
built-ins count the fully merged/deduplicated matching set before its global window,
not capped shard-local rows. On the standalone path, when a finite
trailing `LIMIT` is in effect, the executor fetches one extra row to set
`has_more` without that count. A finite inner `top_n` (for example inside
a CTE) is not a trailing `LIMIT`: when that ranked window is full,
`has_more` / `truncated` are set so a default page is not reported as
complete. An exact `COUNT` that equals `returned` can clear that signal.
`truncated` is true when this response is not the complete matching set
(`has_more`, a positive `offset`, or an exact `total` greater than
`returned`). `timeout_s` is the effective execution timeout in seconds, or
`null` when unbounded. `--timeout` / `PT_SNAP_QUERY_TIMEOUT` are one
QueryService-call budget shared by the page query and optional COUNT; they
apply to every template query, including `report peak-memory`, and do not
change the row cap. A non-numeric `PT_SNAP_QUERY_TIMEOUT` is
`INVALID_PARAMETER`, not `QUERY_FAILED`.

`effective_params` is the validated parameter set after defaults and `choices`
normalization. Dataset `limit` reports the final global output-window cap (with the
same min-of-positive-caps rule), not a per-shard SQL LIMIT; global filters and merges
are already complete. On the standalone path, when `-n` is set, `limit` is the trailing SQL LIMIT after the
same merge the executor applies: `min` of a declared template `limit` and
`-n`, or `-n` appended when the rendered SQL has no trailing LIMIT. Inner
caps such as `top_n` stay their own parameters; they do not rewrite
`limit` when they sit inside a CTE. `--template-info --json` includes
`semantics_version`, `interpretation_limits`, and field semantics from
`output_schema`.

`event`, `block`, and `allocation` support `offset` pagination with a stable
`id` tie-break after the primary sort. Continue their truncated `limit` /
`offset` listings with the same sort keys and a higher `offset`.
`leak_detection` also has a stable `id` tie-break, but has no `offset`;
use the [complete candidate window](#retrieving-a-complete-candidate-window)
workflow above. Increasing `-n` replaces the earlier window rather than
fetching a disjoint next page. `has_more` does not imply offset support.
`active_memory_callstack_at_event` has no `offset`; `-n` cannot raise the
CTE `top_n` cap. Widen that template by increasing `top_n`, keeping `-n` at
least `top_n + 2` with static inclusion. Replace the previous ranked result;
do not concatenate or sum overlapping windows.

On `--json` failure, stdout is empty. stderr is:

```json
{
  "schema_version": 1,
  "ok": false,
  "error": {
    "code": "TEMPLATE_NOT_FOUND",
    "message": "Template 'missing' not found",
    "hint": "Use 'pt-snap query --list --json' to list available templates."
  }
}
```

Stable codes include `TEMPLATE_NOT_FOUND`, `INVALID_PARAMETER`,
`DATABASE_NOT_FOUND`, `DEVICE_NOT_FOUND`, and `FOCUS_NOT_CONFIGURED`. The
exit code is nonzero. Usage and parse errors from the `pt-snap` console
entry (for example `query -n abc --json`) also write this envelope with
`INVALID_PARAMETER` and exit code 2. When Click fails before the `--json`
callback runs, that path is a best-effort argv scan: an exact `--json`
token before `--`, and not the value of the previous option.
`--opt=value` and numeric tokens such as `-1` do not consume the next
argument. The `pt-snap` console entry returns the Typer/Click exit code
(nonzero on failure). Ctrl-C / EOF write `Aborted!` to stderr in text
mode (exit 1, or 130 when Typer returns 130). With `--json`, stdout stays
empty and stderr is this envelope (`ERROR`, message `Aborted!`). Text
mode is unchanged: `Error:` lines still go to stdout (including
missing-template `--template-info`, which already exits 1).

Existing `metadata --json` and `report peak-memory --json` field names stay
compatible. Those commands use the same stderr error envelope when `--json`
is set.

## Output Format

All results are displayed by default. Use `-n` to limit the number of rows shown:

```
# Show all results (default)
pt-snap query --template-use leak_detection

# Show only first 5
pt-snap query --template-use leak_detection -n 5

# Show all results (explicit)
pt-snap query --template-use leak_detection -n 0
```

Example output (with `-n 2`, default `total` semantics):

```
Found 2 results, showing 2:
  {'id': 1, 'address': 4096, 'size': 2048, ...}
  {'id': 2, 'address': 8192, 'size': 4096, ...}
  ... more available (use -n, offset, top_n, or --exact-total)
```

With `--exact-total`, "Found N" is the matching-row count and the footer can
show how many rows remain. `SnapshotAnalyzer.execute_query()` defaults to
`max_rows=None` (no cap) and `exact_total=False`, matching the CLI unless
`-n` / `max_rows` or `--exact-total` / `exact_total` is set. `timeout_s` is
independent of the row cap.

CLI and Python API query results contain raw SQLite values. A template's
`output_schema` is metadata and is not applied automatically during query
execution. Use `ResultMapper` explicitly when converted values such as
hexadecimal address strings are required. Result rows do not repeat field
explanations; look up `semantics_version` and interpretation limits with
`--template-info` (or `get_template_info`) for the template that produced the
rows. `SnapshotAnalyzer.execute_query()` results also include `template`
and `semantics_version` so that lookup stays tied to the rows.

## Template Architecture

Query templates are defined in YAML format with:
- `version`: YAML file format version, not the field-semantics contract and not the SnapshotDB schema version
- `queries`: Query definitions with description, supported devices, parameters, SQL (Jinja2 templated), and output schema
- Each parameter declares `type`, `default`, `required`, `description`, and optionally `choices`, a closed list of accepted values that is mandatory for parameters rendered as SQL identifiers or keywords
- Optional `semantics_version` (positive integer) and `interpretation_limits` on the query, plus optional field keys on each `output_schema` entry: `units`, `metric_semantics`, `scope`, `denominator`, `sentinel`, and `interpretation_limits`
- `semantics_version` is the interpretation contract agents should cite. v1/v2 SQL variants of the same template share that contract. Templates that omit both remain valid; unannotated `output_schema` entries carry `column` and `type` only

Closed vocabularies:

- `units`: `bytes`, `gib`, `percent`, `event_id`, `count`, `address`, `flag`, `text`
- `metric_semantics`: `instantaneous_occupancy`, `same_event_gap`, `share_of_included_rows`, `identifier`, `classification`, `ordering_marker`
- `scope`: `dynamic`, `static`, `preexisting`, `mixed`, `captured_range`, `same_event`. Use `mixed` when a column contains more than one of those per row (see `category` on `active_memory_callstack_at_event`)

When passed explicitly to `ResultMapper`, recognized mapping types are `int`,
`float`, `str`, `bool`, `hex`, and `datetime`; `datetime` is currently a
pass-through declaration rather than a parser.

## Optional Result Mapping

For optional row conversion and model mapping, see
[ResultMapper API](result-mapper-api.md).

For the high-level programmatic focus and query facade, see
[SnapshotAnalyzer API](snapshot-analyzer-api.md).
