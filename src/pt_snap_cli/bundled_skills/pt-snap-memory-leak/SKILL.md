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

Use the displayed database and focused device only when both are present and the user has not requested another target. If the database or device remains ambiguous, ask the user to select it before analysis.

Do not run `pt-snap focus <database_path>` or otherwise persist focus from this skill. Pass the database and device explicitly to every diagnostic query.

This skill accepts SnapshotDB files only. Do not run `pt-snap import` or deserialize a pickle snapshot. If the user has only a pickle file, stop and explain that importing requires a separate, explicit trusted-input decision because pickle loading is not a sandbox.

### 3. Verify capabilities and the database in two calls

Run:

```bash
pt-snap capabilities --json
pt-snap overview '<db_path>' --json
```

`capabilities --json` is the catalog: CLI version, every template contract (parameters, `output_schema`, field semantics), and the skill list. Do not probe templates one-by-one with `--template-info`.

`overview --json` is the read-only database orientation: device list, per-device first/last event id, and import-metadata status. Do not persist focus.

Prerequisite probe budget: previously 7 calls (`metadata` plus six `--template-info` probes). Now 2 calls (`capabilities` + `overview`). Record that reduction when evaluating this skill.

Confirm these templates exist in the capabilities catalog before diagnosis: `memory_peak`, `allocator_gap`, `event`, `block`, `leak_detection`, `active_memory_callstack_at_event`, `preexisting_live`, `freed_block_lifetime`. If the catalog or overview fails, stop and report the exact failure. Do not silently substitute raw SQL for a missing core template.

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
`total` equals this page's `returned` count; do not treat it as the full
matching set. If `has_more` or `truncated` is true, continue with `offset` or a
larger `-n` instead of concluding from the first page. Add `--exact-total` only
when a matching-row count is required. `--timeout` is independent of `-n`.

```bash
pt-snap query '<db_path>' --device <device_id> --template-use leak_detection --params '{"min_size":<min_size>}' -n 100 --json
```

`leak_detection` includes only dynamic blocks with a recorded allocation and no recorded free completion. It intentionally excludes static blocks whose allocation predates tracing. Interpret its columns from the `leak_detection` entry in `pt-snap capabilities --json`; do not treat candidates as confirmed leaks.

Record candidate count, largest sizes, addresses, and allocation event IDs. Do not infer simultaneous live bytes by summing cumulative allocation activity from `callstack_analysis`.

### 3. Attribute live memory at the end of the trace

Use the final event ID from Step 1:

```bash
pt-snap query '<db_path>' --device <device_id> --template-use active_memory_callstack_at_event --params '{"event_id":<final_event_id>,"include_static":true,"min_size":0,"top_n":20}'
```

This template has no `offset`, and `-n` cannot raise the CTE `top_n` cap. If
`has_more` or `truncated` is true, increase `top_n` instead of concluding from
the first ranked page.

Keep static memory separate from dynamic live memory. Rank dynamic groups by `size_bytes`, then compare block count, requested bytes, and each group's share of included active bytes. Read `percent_of_active_blocks` units, denominator, and interpretation limits from the `active_memory_callstack_at_event` entry in `pt-snap capabilities --json` rather than inferring them from the column name. A group containing many small blocks can be important even when no individual block appears near the top of `leak_detection`.

### 4. Compare occupancy at the active peak

Use the `peak_active_event_id` returned by `memory_peak`:

```bash
pt-snap query '<db_path>' --device <device_id> --template-use active_memory_callstack_at_event --params '{"event_id":<peak_active_event_id>,"include_static":true,"min_size":0,"top_n":20}'
```

Treat this as an occupancy comparison between two independent aggregates, not a block-identity survival test. Each query groups whatever was live at its own event, and `top_n` truncation applies to dynamic callstack groups only; the static and preexisting groups are always returned in full. A peak block may have been freed while an equal-sized later block from the same callstack was live at the final event, which keeps the callstack row stable without any block surviving.

Before claiming that the same blocks persisted across the peak:
- Match representative blocks by identity: the same `id`/address plus allocation event ID must appear live at both events.
- Confirm continuity through lifecycle checks in Step 5; occupancy stability alone is not survival evidence.

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
6. `Findings`: category, confidence, evidence, inference, and affected callstack or allocation family.
7. `Unknowns`: missing timing, ownership, capture-boundary, callstack, or repeated-capture evidence.
8. `Suggested validation`: targeted experiments that could confirm or reject each leading hypothesis.

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
- Every finding has a conservative category and confidence level.
- Unknowns and validation experiments are included.
