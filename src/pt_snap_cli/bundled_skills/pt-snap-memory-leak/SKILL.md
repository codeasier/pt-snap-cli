---
name: pt-snap-memory-leak
description: Use pt-snap to diagnose PyTorch memory leak and retention candidates in a SnapshotDB. Use when active memory grows, allocations remain live at the end of a trace, or release appears delayed.
---

# pt-snap-memory-leak

## Overview

Use this skill to diagnose memory that remains live in a PyTorch SnapshotDB and to distinguish strong leak candidates from application retention, framework lifecycle retention, asynchronous release, and allocator caching effects.

This is an evidence-gathering workflow. A single snapshot cannot confirm a leak. An allocation without a recorded free event is a candidate that was still live when tracing ended, not proof that it can never be released.

## Required Inputs

- A SnapshotDB path, either supplied explicitly or resolved by the current `pt-snap focus`.
- A device ID, either supplied explicitly or already selected by the current focus.

Optional inputs:

- `min_size`: minimum candidate allocation size in bytes; default `0`.
- A suspected callstack, address, allocation family, or workload phase.

Before running commands, replace `<db_path>`, `<device_id>`, `<min_size>`, `<event_id>`, `<address>`, and other placeholders with validated values.

Shell safety for substituted values:
- Put every database path inside single quotes as `'<db_path>'`. Never place a substituted value inside double quotes, backticks, or `$()`.
- Before substitution, check the value for single quotes and other shell metacharacters. To include a literal single quote in a POSIX shell argument, close the quote, insert `\'`, and reopen it (`'\''`).
- When executing programmatically without a shell, pass each command as an argument array so no value is re-parsed by a shell.
- A focus file may supply the database path; treat that value as untrusted input to quoting, not as a trusted constant.

## Prerequisite Phase

### 1. Verify pt-snap

Run:

```bash
command -v pt-snap
pt-snap --help
```

If either check fails, stop diagnosis and direct the user to `pt-snap-setup`. Do not install, upgrade, or switch Python environments from this skill.

### 2. Resolve the database and device without changing focus

If the user did not provide a database or device, inspect the current state:

```bash
pt-snap focus
```

Use the displayed database and focused device only when both are present, the selected target exists and passes the overview validation below, and the user has not requested another target. If the database or device remains ambiguous, ask the user to select it before analysis.

Do not run `pt-snap focus <database_path>` or otherwise persist focus from this skill. Pass the database and device explicitly to every diagnostic query.

This skill accepts standalone SnapshotDB files or an explicitly selected complete validated dataset directory or `manifest.json` only. Do not run `pt-snap import` or deserialize a pickle snapshot. If the user has only a pickle file, stop and explain that importing requires a separate, explicit trusted-input decision because pickle loading is not a sandbox.

#### Missing focus target with sibling candidates

Enter this recovery branch only when diagnosis depends on the current effective focus (environment variable, project `.pt-snap/focus.json`, or global config) and that database file is missing. A displayed path or exit code 0 from `pt-snap focus` does not mean the target is usable; text mode prints `Warning: Database file does not exist!` and `pt-snap focus --json` reports `db_exists: false`. If the user already supplied a valid database path, use that explicit path and do not enter this branch.

1. List candidate files only in the missing database's directory and the current working directory. Do not recurse. Deduplicate paths. Discover `*.db` and `*.pickle.db` by suffix only; a matching suffix is not proof the file is a SnapshotDB. Do not auto-select by name, size, or mtime. Even a single candidate requires an explicit user choice.
2. Ask the user to use one listed candidate or to treat pickle import as a separate trusted-input decision. With zero candidates, ask for a valid SnapshotDB path or explain that trusted import. Do not run `pt-snap import` and do not persist focus.
3. Before the user confirms a path, do not run diagnostic queries, reports, or metadata against any candidate, and do not inspect candidates with Python, the `sqlite3` CLI, or hand-assembled SQL.
4. After the user confirms a path, the next inspect step is `pt-snap metadata '<db_path>' --json`. Do not start with `pt-snap query`. Re-resolve the device from the confirmed database; do not inherit the focused device from the missing target. Then continue the checks below. A schema-valid legacy database may report metadata status `unavailable` with reason `metadata_missing`; record unknown import provenance and do not force a re-import. Stop on schema errors or invalid metadata.

### 3. Verify capabilities and the database in two calls

Apply the shared diagnostic preflight contract in `pt-snap-helper`, even on
direct invocation. Run only the probes whose complete results are not reusable:

```bash
pt-snap capabilities --json
pt-snap overview '<db_path>' --json
```

Reuse complete successful results from this conversation only for the same
CLI/Python environment and unchanged database target. Check CLI version and the
overview's resolved absolute database path. Summaries, truncated output, changed
environment/version or database, and unknown result identity require refreshing
the affected probe. Revalidate the contents even when reusing results.

`capabilities --json` is the catalog: CLI version, every template contract (parameters, `output_schema`, field semantics), and the skill list. Do not probe templates one-by-one with `--template-info`. Do not re-emit a reused catalog.

Read `overview.import_metadata.status` (the `import_metadata` field in the
overview JSON), not just exit code 0 or outer `ok: true`. Stop on `invalid`
metadata or schema errors. Continue with `available`, or with legacy
`unavailable` and reason `metadata_missing` after recording unknown import
provenance. Stop on any other status/reason or incomplete result. Validate the
selected device against overview's devices and record its trace bounds.

Prerequisite probe budget: 2 calls from cold, 1 with one reusable result, 0 with
both. Record tool-call count and output bytes separately; fewer calls need not
mean fewer bytes. Availability/focus checks are outside this discovery budget.
Missing-focus recovery is the metadata-first exception: after user confirmation,
run metadata and apply its stop/legacy rules above, then obtain/reuse capabilities
and overview. Metadata alone does not replace overview; never reuse the missing
target's overview or device.

Confirm these templates exist in the capabilities catalog before diagnosis: `memory_peak`, `allocator_gap`, `event`, `block`, `leak_detection`, `active_memory_callstack_at_event`, `active_blocks_at_event`, `preexisting_live`, `freed_block_lifetime`. If the catalog or overview fails, stop and report the exact failure. Do not silently substitute raw SQL for a missing core template.

## Validated complete dataset scope

Accept only the user's explicit standalone file or complete validated
compatibility-v1 / pt-snap-native-v2 dataset directory or `manifest.json`.
Existence alone is not validation. Never infer arbitrary or sibling directories,
auto-select a device, import pickle, or persist focus. Keep the same explicit
target/device pair in every command and record full-device versus selected range.
For a dataset, validate `overview.dataset.status`, `format`, `manifest_path`,
`fingerprint`, real bounds and selected device. Reuse requires the same fingerprint.
Read `overview.import_metadata`: a valid external original artifact may report
`unavailable` / `metadata_missing`; record unknown provenance. This is not permission
to allow invalid metadata, incomplete validation, or any other unknown reason.

Check every chosen catalog entry's `dataset_support.supported`. All eleven built-ins
have declared dataset semantics; arbitrary SQL and custom built-in-name overrides
are unsupported. Never concatenate shard-local top-N or sum different device peaks.
Use `lifecycle_id` within the same fingerprint/device plus original `allocEventId`,
`allocation_source` and `free_source`; completed frees have action 6, not pending
free_requested. Address and shard-local stack IDs are not lifecycle identity.
Stored `state_scope` is an observation, not reconstructed state at arbitrary E.
Dataset `stack_id` / `source_stack_id` uses full canonical text or covered ordered
raw frames; `local_stack_id`, source event/slice and `text_kind` are provenance.
Never merge shortened labels. Keep captured literal missing-label text separate
from missing references. `callstack_analysis` semantics_version=2 counts ALL real
stack-bearing actions in legacy `alloc_count`, not allocation-only; `total_size`
is activity, not live bytes, and non-NULL empty text activity remains its own group.

Check `scope.range_complete` for ranges and
`scope.source_coverage.range_complete` for point queries; source/frame coverage is
separate from `has_more`, `truncated`, and exact totals. Retain
`allocation_source_complete` and `ordered_frames_complete`. Only recognized
ptSnapOrderedFrames version 1 with actual schema and per-event coverage supplies
ordered frames (including duplicates); missing/unknown/uncovered means text-only.
Never reconstruct frames or claim hierarchical evidence from text alone.
One query/report shares diminishing time and cumulative 100000 fetched/output rows
and 64 MiB serialized-value budgets, NOT an RSS ceiling. Budget failure returns no
partial global proof; narrow scope or ask for an explicit member, never raw SQL.
Percentages use included group bytes (standalone SQL or dataset post-merge) after filtering/top-N and before the caller's
row cap, not the whole active counter; report coverage uses active at the SAME
selected metric event. Leak candidates require terminal full-device dataset scope,
not an arbitrary `--slice`; end-live survival is not a confirmed leak.

## Optional compact stack evidence

For long stack text, check the capabilities catalog for `stack_bytes` on `event`
or `active_memory_callstack_at_event` before adding `stack_bytes: 256` to their
params. This is not a `leak_detection` parameter. Retain `stack_id`, `stack_kind`,
`stack_event_id`, effective `stack_bytes`, `stack_original_bytes`,
`stack_truncated`, category, numbers and completeness. UTF-8 text bytes are not
model tokens or a hard JSON response cap. Text shortening does not change
`has_more`, `truncated` or `total_is_exact` and does not complete a ranked window.
Never merge groups by shortened text: equal v2 text may have distinct IDs and
captured text may match synthetic labels. Retrieve full captured text with the
catalog's `event` query using `id=stack_event_id`, omit `stack_bytes`, and keep
the same unchanged database/device. Missing/static/preexisting groups have no
captured allocation stack. Keep per-block `(id, allocEventId)` matching for
survival evidence; a stack identity is not a block identity.

## Diagnostic Workflow

### 1. Establish trace boundaries and memory peaks

Run:

```bash
pt-snap query '<db_path>' --device <device_id> --template-use event --params '{"order_by":"id","order_dir":"DESC","limit":1}'
pt-snap query '<db_path>' --device <device_id> --template-use memory_peak
pt-snap query '<db_path>' --device <device_id> --template-use allocator_gap
```

Record the final event ID and the separate `allocated`, `active`, and `reserved` peak values and event IDs. Do not subtract peaks from different events as if they occurred simultaneously. Use `allocator_gap` for same-event comparisons.

Treat a large `reserved - active` gap without corresponding active growth as an allocator/cache symptom, not direct leak evidence.

### 2. Find end-of-trace dynamic candidates

Run an initial ranked query, keeping the result bounded. Prefer `--json`. Default
`total` equals this window's `returned` count; do not treat it as the full
matching set. `leak_detection` accepts only `min_size` and `limit`: it has no
`offset`, and both CLI and API reject that unknown parameter. `has_more` or
`truncated` means the result is incomplete, not that offset paging is supported.
`--timeout` is independent of `-n`.

```bash
pt-snap query '<db_path>' --device <device_id> --template-use leak_detection --params '{"min_size":<min_size>}' -n 100 --json
```

If the result is incomplete and a full candidate set is needed:

1. Repeat with the same database, device, and `min_size`, adding `--exact-total`:

   ```bash
   pt-snap query '<db_path>' --device <device_id> --template-use leak_detection --params '{"min_size":<min_size>}' -n 100 --exact-total --json
   ```

   The exact `total` is a matching **row count**, not bytes or GiB. The count
   ignores `limit`; it does not make the returned rows complete.
2. If `total` is zero, report no matching candidates and stop this candidate
   listing. Do not pass zero to `-n`: `-n 0` means unlimited, not an empty window.
3. Only when the positive exact total is affordable within the memory/output
   budget, request that many rows in one bounded window. Replace `<positive_total>`
   below with that count. Remove any explicit `limit` from `--params` (as below),
   or raise it to the same count; a smaller explicit `limit` still caps `-n`.

   ```bash
   pt-snap query '<db_path>' --device <device_id> --template-use leak_detection --params '{"min_size":<min_size>}' -n <positive_total> --json
   ```

4. Verify `returned` equals the exact count and both `has_more` and `truncated`
   are false before claiming completeness. The enlarged result **replaces** the
   earlier rows; never append windows or add their counts/bytes together, because
   every rerun starts at the same ranked beginning.

If the full count exceeds the budget, retain a bounded sample and explicitly
report incomplete candidate/byte coverage. An exact row count alone does not
give total candidate bytes. A higher `min_size` can narrow a follow-up query,
but changes the scope and requires a new count; do not call that the original
complete set. Never use an unlimited window to bypass the budget.

`leak_detection` includes only dynamic blocks with a recorded allocation and no recorded free completion. It intentionally excludes static blocks whose allocation predates tracing. Interpret its columns from the `leak_detection` entry in `pt-snap capabilities --json`; do not treat candidates as confirmed leaks.

Record candidate count, largest sizes, addresses, and allocation event IDs. Do not infer simultaneous live bytes by summing cumulative allocation activity from `callstack_analysis`.

### 3. Attribute live memory at the end of the trace

Use the final event ID from Step 1:

```bash
pt-snap query '<db_path>' --device <device_id> --template-use active_memory_callstack_at_event --params '{"event_id":<final_event_id>,"include_static":true,"min_size":0,"top_n":20}'
```

This template has no `offset`, and `-n` cannot raise the template `top_n` cap. If
`has_more` or `truncated` is true, increase `top_n` instead of concluding from
the first ranked page.

Keep static memory separate from dynamic live memory. Rank dynamic groups by `size_bytes`, then compare block count, requested bytes, and each group's share of included active bytes. Read `percent_of_active_blocks` units, denominator, and interpretation limits from the `active_memory_callstack_at_event` entry in `pt-snap capabilities --json` rather than inferring them from the column name. A group containing many small blocks can be important even when no individual block appears near the top of `leak_detection`.

### 4. Compare occupancy at the active peak

Use the `peak_active_event_id` returned by `memory_peak`:

```bash
pt-snap query '<db_path>' --device <device_id> --template-use active_memory_callstack_at_event --params '{"event_id":<peak_active_event_id>,"include_static":true,"min_size":0,"top_n":20}'
```

Treat this as an occupancy comparison between two independent aggregates, not a block-identity survival test. Each query groups whatever was live at its own event, and `top_n` truncation applies to dynamic callstack groups only; the static and preexisting groups are always returned in full. A peak block may have been freed while an equal-sized later block from the same callstack was live at the final event, which keeps the callstack row stable without any block surviving.

Before claiming that the same blocks persisted across the peak, query individual live blocks at both events in the same database and the same device:

```bash
pt-snap query '<db_path>' --device <device_id> --template-use active_blocks_at_event --params '{"event_id":<peak_active_event_id>,"include_static":true,"min_size":0,"order_by":"id","order_dir":"ASC","offset":0}' -n 500 --json
pt-snap query '<db_path>' --device <device_id> --template-use active_blocks_at_event --params '{"event_id":<final_event_id>,"include_static":true,"min_size":0,"order_by":"id","order_dir":"ASC","offset":0}' -n 500 --json
```

- Use a positive page window (`-n 500`), never an unlimited query. These commands return only the first page. For each event independently, advance the `offset` parameter by that page's `returned` count, keeping the event, filters, ordering, database, and device fixed. Continue until `has_more=false` in the JSON response, retaining every preceding page. An offset page still has `truncated=true` because it omits earlier rows; completeness comes from collecting all pages from offset 0 through the terminal page, not from that last page alone. Default `total` is a page count, not the full set; an exact count alone does not retrieve the missing identities.
- Match representative blocks by identity using the exact pair `(id, allocEventId)`, not address, size, or callstack alone. Address reuse does not mean the same allocation survived. Keep `dynamic_live_at_event`, `static`, and `preexisting_live_at_event` categories separate; pre-tracing allocations have unknown allocation history and are not dynamic leak candidates.
- If either event is incompletely paged (or a query fails), label matches as sample-only evidence. Unmatched sample rows are not proven new or released. Do not report a full-set survival rate or claim zero new blocks from samples.
- Only after both complete sets are collected, intersect their `(id, allocEventId)` keys: `matched = peak ∩ final`, `new_at_end = final - peak`, and `released_from_peak = peak - final`. Compute these separately per category. A count-based peak survival rate is `len(matched) / len(peak)`; the share of final blocks already live at peak is `len(matched) / len(final)`. State the denominator and scope, report an empty denominator as unavailable, and do not mix block counts with bytes. Claim zero new blocks only when the complete `new_at_end` set is empty.
- Confirm continuity through lifecycle checks in Step 5; occupancy stability alone is not survival evidence. Check real `freeEventId` values between the two events before describing peak-only blocks as released, and inspect address-event lifecycles for reuse or ambiguous pairing. Even complete identity survival is retention evidence, not proof of a leak.

The template separates blocks without a captured allocation event into their own groups instead of attributing them to callstacks: `[static] allocEventId=-1, freeEventId=-1`, and `[preexisting live] allocEventId=-1` for blocks allocated before tracing that were still live at the analyzed event because their recorded free event came later or does not exist. Pre-tracing blocks whose free event precedes the analyzed event are correctly absent because they were no longer live. Report each group separately instead of absorbing it into a callstack group.

For an exact cross-check of the `[preexisting live]` bucket — for example against a database imported before this grouping existed — do not scan with the packaged `block` filters: they compare `freeEventId` numerically and cannot express the `freeEventId IS NULL` case that `active_memory_callstack_at_event` counts as preexisting-live, so any filtered scan risks an incomplete bucket. Use the packaged `preexisting_live` template instead:

```bash
pt-snap query '<db_path>' --device <device_id> --template-use preexisting_live --params '{"event_id":<peak_active_event_id>}'
```

The template uses the same predicate as the `[preexisting live]` group: pre-tracing allocations whose free event is missing (`NULL`), comes later than the analyzed event, or is negative other than the static sentinel `-1`. The aggregate returns a single row, so no row limit applies and nothing is silently undercounted; report the count and bytes next to the static group.

Occupancy that stays high across both events strengthens retention evidence but does not by itself prove a leak.

### 5. Inspect representative block and address lifecycles

For representative large blocks and high-volume callstack groups, inspect the block and all events at the same address:

```bash
pt-snap query '<db_path>' --device <device_id> --template-use block --params '{"id":<alloc_event_id>}'
pt-snap query '<db_path>' --device <device_id> --template-use event --params '{"address":<address>,"order_by":"id","order_dir":"ASC"}' -n 100
```

Keep address-event listings bounded. `-n 0` and other unlimited settings materialize every matching row in memory, which can exhaust resources on a heavily reused address; start with `-n 100` and continue with the `offset` parameter while `has_more` is true, or narrow the window with `min_id`/`max_id` around the allocation event ID instead of requesting all rows at once. `event` / `block` pages stay stable because `id` is the sort tie-break.

Interpret event actions as `4=alloc`, `5=free_requested`, and `6=free_completed`. Address reuse can produce multiple lifecycles, so correlate address, size, stream, allocation event ID, and event ordering before pairing events.

When an unambiguous `free_requested` and `free_completed` pair exists, report their event IDs and event-ID distance. Event IDs are ordering markers, not timestamps; never report the distance as elapsed time.

Do not use `block.state` as evidence for dynamic blocks. Its documented lifecycle meaning is reliable only for static blocks whose block ID is negative.

### 6. Optionally establish a freed-block lifetime baseline

When a lifetime baseline is needed, use the packaged `freed_block_lifetime` template:

```bash
pt-snap query '<db_path>' --device <device_id> --template-use freed_block_lifetime
```

This baseline describes successfully freed blocks, bucketed by `freeEventId - allocEventId` distance (`<1k`, `1k-5k`, `5k-20k`, `20k-100k`, `>=100k`). It does not classify end-of-trace candidates and must not be generalized to real elapsed time. Read those limits from the `freed_block_lifetime` entry in `pt-snap capabilities --json`.

### 7. Classify findings conservatively

Before any positive or negative per-step / per-iteration conclusion (including
"not a per-step leak"), establish and report iteration evidence:

- State the trusted iteration count, boundaries mapped to event IDs, source,
  and coverage range. Use workload code, logs, or an explicit verified marker
  convention to establish the mapping; allocator event counts, waveform minima,
  and cleanup counts are not iteration counts.
- `segment_unmap` is only a conditional supporting clue. One `empty_cache`
  call can emit multiple unmap events; one iteration can perform multiple
  cleanups, or none. Group events and cleanup calls only according to the
  verified workload mapping, never by assuming one event or cleanup equals
  one step. Do not directly count `segment_unmap` events as steps.
- Check capture start/end and missing markers against that source. Separate
  fully covered iterations from partial iterations and uncaptured work; do not
  extrapolate a captured count to the whole run. If count, boundaries, source,
  or coverage cannot be established, report the unsupported fields and the
  per-step conclusion as `unknown`. A verified complete subrange may support
  a conclusion scoped only to that subrange, with the rest explicitly unknown.
- Within verified comparable boundaries, correlate allocation identities and
  release events with live bytes after expected cleanup. Three surviving blocks
  over three verified iterations can support accumulation; three blocks alone
  cannot establish a fixed per-step population or rule out accumulation. Keep
  observed per-iteration accumulation a candidate, not a confirmed leak; check
  application ownership and expected lifetime before assigning a category.
- Jaccard similarity of `(action, callstackId)` sets is only supporting evidence
  of similar event kinds. Sets discard multiplicity, ordering, allocation
  identity, and byte sizes; even high similarity cannot prove that unreturned
  bytes are the only per-iteration difference.

Use these result categories:

- `strong leak candidate`: dynamic live bytes grow across comparable captures or phases, persist after expected cleanup, and have ownership evidence. Do not use this category from end-of-trace survival alone.
- `application retention`: a user-code allocation family stays referenced longer than expected, but eventual release has not been disproved.
- `framework lifecycle retention`: allocations appear tied to framework initialization, caches, workspaces, or finalization boundaries.
- `asynchronous free pending`: an unambiguous free request is present but completion is absent or occurs substantially later in event order.
- `allocator/cache effect`: reserved memory remains high while active memory does not show corresponding live allocation growth.
- `normal long-lived allocation`: lifetime matches the expected model, optimizer, graph, communication, or workspace lifecycle.
- `inconclusive`: capture duration, missing callstacks, static allocations, address reuse, or incomplete lifecycle evidence prevents classification.

## Output Template

Report results in this order:

1. `Analysis scope`: database path, device ID, final event ID, and candidate threshold.
2. `Memory baseline`: separate allocated, active, and reserved peaks with their event IDs and same-event gaps.
3. `End-of-trace evidence`: dynamic candidate count, dynamic bytes by callstack, static bytes, and representative blocks.
4. `Peak-occupancy evidence`: callstack bytes and block counts at the active peak versus the final event, identity-matched blocks if any, and static plus `[preexisting live]` memory that carries no per-callstack attribution.
5. `Lifecycle evidence`: representative alloc, free-requested, and free-completed event IDs, with ambiguities called out.
6. `Iteration evidence`: trusted iteration count, event-ID boundaries, workload code/log/verified marker source, and coverage range; distinguish complete and partial iterations. Report unsupported fields and per-step conclusions as `unknown` before any positive or negative per-step finding. Include scoped per-iteration live-byte/lifecycle evidence when available.
7. `Findings`: category, confidence, evidence, inference, and affected callstack or allocation family; per-iteration accumulation remains a candidate, not a confirmed leak.
8. `Unknowns`: missing timing, ownership, capture-boundary, callstack, repeated-capture, or iteration-mapping evidence, including uncaptured work.
9. `Suggested validation`: targeted experiments that could confirm or reject each leading hypothesis, including workload logs or explicit marker conventions when iteration mapping is unknown.

Useful validation experiments include repeated snapshots at equivalent workload milestones, extending tracing beyond expected cleanup, explicitly releasing suspected application references, synchronizing the device before the capture ends, and comparing behavior before and after allocator cache cleanup. Explain that cache cleanup can change reserved memory without proving that application references were released.

## Guardrails

- Keep SnapshotDB access read-only. Never run `create`, `insert`, `update`, `delete`, `drop`, `alter`, `replace`, `attach`, `detach`, `reindex`, or `vacuum` SQL.
- Do not persist focus, configuration, reports, exports, scratch databases, or readiness files.
- Do not import or deserialize pickle snapshots.
- Prefer packaged `pt-snap` templates. Do not use the `sqlite3` CLI or hand-assembled SQL. The exact `[preexisting live]` total is `preexisting_live` (Step 4) and the freed-block lifetime baseline is `freed_block_lifetime` (Step 6).
- Do not call every allocation without a free event a leak.
- Separate cumulative allocation volume from memory simultaneously live at an event.
- Keep static memory separate from dynamic candidates.
- Do not treat event IDs as timestamps or event-ID distance as elapsed time.
- Do not generalize from one address, callstack, size class, or capture to all allocations.
- Keep result listings bounded; never request unlimited rows from a query. Prefer `--json` and do not treat a page as complete when `has_more` or `truncated` is true.
- Treat peak-versus-final callstack aggregates as occupancy evidence only; claim persistence solely from identity-matched blocks.
- Label evidence, inference, and unknowns separately.

## Verification Checklist

- `pt-snap` availability was verified without installing or switching environments.
- Database and device were selected explicitly without changing focus.
- Final event and all three memory peaks were recorded.
- Same-event allocator gaps came from `allocator_gap`.
- End-of-trace dynamic candidates and static memory were reported separately.
- Active-peak and final-event callstack attribution used the same device.
- Peak-versus-final comparisons were reported as occupancy, and persistence claims relied on identity-matched blocks.
- Preexisting-live memory was reported separately from static and dynamic groups, with exact totals taken from `preexisting_live`.
- Address-event listings stayed bounded with paging or event-ID windows, and `has_more` was honored.
- Database paths were single-quoted or passed through argument arrays without shell re-parsing.
- Representative lifecycle events were checked for address reuse and ambiguous pairing.
- Dynamic block state was not used as leak evidence.
- Event-ID distances were not presented as time durations.
- Every positive or negative per-step conclusion was preceded by a trusted iteration count, event-ID boundaries, source, and coverage range; otherwise the unsupported fields and conclusion were `unknown`.
- Complete iterations were separated from partial or uncaptured work; multiple allocator events or cleanup calls per iteration were reconciled with workload code, logs, or a verified marker convention instead of counted as steps.
- Per-iteration accumulation remained a candidate, not a confirmed leak, and Jaccard set similarity was not used to claim a unique byte difference.
- Every finding has a conservative category and confidence level.
- Unknowns and validation experiments are included.
