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
- An event range to investigate.
- A suspected callstack, address, allocation family, or workload phase.

Before running commands, replace `<db_path>`, `<device_id>`, `<min_size>`, `<event_id>`, `<address>`, and other placeholders with validated values. Quote the database path in every command.

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

### 3. Verify the database and required templates

Run:

```bash
pt-snap metadata "<db_path>" --json
pt-snap query --template-info memory_peak
pt-snap query --template-info allocator_gap
pt-snap query --template-info event
pt-snap query --template-info block
pt-snap query --template-info leak_detection
pt-snap query --template-info active_memory_callstack_at_event
```

If database validation or a required template fails, stop and report the exact failure. Do not silently substitute raw SQL for a missing core template.

## Diagnostic Workflow

### 1. Establish trace boundaries and memory peaks

Run:

```bash
pt-snap query "<db_path>" --device <device_id> --template-use event --params '{"order_by":"id","order_dir":"DESC","limit":1}'
pt-snap query "<db_path>" --device <device_id> --template-use memory_peak
pt-snap query "<db_path>" --device <device_id> --template-use allocator_gap
```

Record the final event ID and the separate `allocated`, `active`, and `reserved` peak values and event IDs. Do not subtract peaks from different events as if they occurred simultaneously. Use `allocator_gap` for same-event comparisons.

Treat a large `reserved - active` gap without corresponding active growth as an allocator/cache symptom, not direct leak evidence.

### 2. Find end-of-trace dynamic candidates

Run an initial ranked query, keeping the result bounded while retaining the reported total count:

```bash
pt-snap query "<db_path>" --device <device_id> --template-use leak_detection --params '{"min_size":<min_size>}' -n 100
```

`leak_detection` includes only dynamic blocks with a recorded allocation and no recorded free completion. It intentionally excludes static blocks whose allocation predates tracing.

Record candidate count, largest sizes, addresses, and allocation event IDs. Do not infer simultaneous live bytes by summing cumulative allocation activity from `callstack_analysis`.

### 3. Attribute live memory at the end of the trace

Use the final event ID from Step 1:

```bash
pt-snap query "<db_path>" --device <device_id> --template-use active_memory_callstack_at_event --params '{"event_id":<final_event_id>,"include_static":true,"min_size":0,"top_n":20}'
```

Keep static memory separate from dynamic live memory. Rank dynamic groups by `size_bytes`, then compare block count, requested bytes, and percentage of active blocks. A group containing many small blocks can be important even when no individual block appears near the top of `leak_detection`.

### 4. Test whether suspicious groups survive the active peak

Use the `peak_active_event_id` returned by `memory_peak`:

```bash
pt-snap query "<db_path>" --device <device_id> --template-use active_memory_callstack_at_event --params '{"event_id":<peak_active_event_id>,"include_static":true,"min_size":0,"top_n":20}'
```

Compare the same callstack between the active peak and the final event. Report whether its live bytes and block count disappear, remain stable, or grow. Survival across one peak strengthens retention evidence but does not by itself prove a leak.

### 5. Inspect representative block and address lifecycles

For representative large blocks and high-volume callstack groups, inspect the block and all events at the same address:

```bash
pt-snap query "<db_path>" --device <device_id> --template-use block --params '{"id":<alloc_event_id>}'
pt-snap query "<db_path>" --device <device_id> --template-use event --params '{"address":<address>,"order_by":"id","order_dir":"ASC"}' -n 0
```

Interpret event actions as `4=alloc`, `5=free_requested`, and `6=free_completed`. Address reuse can produce multiple lifecycles, so correlate address, size, stream, allocation event ID, and event ordering before pairing events.

When an unambiguous `free_requested` and `free_completed` pair exists, report their event IDs and event-ID distance. Event IDs are ordering markers, not timestamps; never report the distance as elapsed time.

Do not use `block.state` as evidence for dynamic blocks. Its documented lifecycle meaning is reliable only for static blocks whose block ID is negative.

### 6. Optionally establish a freed-block lifetime baseline

The packaged templates do not aggregate `freeEventId - allocEventId` into lifetime buckets. Only when this baseline is needed, and only when the `sqlite3` CLI is available, use a read-only fallback after validating that `<device_id>` is a non-negative decimal integer:

```bash
sqlite3 -readonly "<db_path>" "
SELECT CASE
         WHEN freeEventId - allocEventId < 1000 THEN '<1k'
         WHEN freeEventId - allocEventId < 5000 THEN '1k-5k'
         WHEN freeEventId - allocEventId < 20000 THEN '5k-20k'
         WHEN freeEventId - allocEventId < 100000 THEN '20k-100k'
         ELSE '>=100k'
       END AS lifetime_events,
       COUNT(*) AS block_count,
       SUM(size) AS size_bytes
FROM block_<device_id>
WHERE allocEventId >= 0 AND freeEventId >= allocEventId
GROUP BY lifetime_events
ORDER BY MIN(freeEventId - allocEventId);"
```

This baseline describes successfully freed blocks. It does not classify end-of-trace candidates and must not be generalized to real elapsed time.

If `sqlite3` is unavailable or read-only mode cannot be verified, skip this optional step and list the lifetime distribution as unknown. Do not use a writable connection.

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

1. `Analysis scope`: database path, device ID, event range, final event ID, and candidate threshold.
2. `Memory baseline`: separate allocated, active, and reserved peaks with their event IDs and same-event gaps.
3. `End-of-trace evidence`: dynamic candidate count, dynamic bytes by callstack, static bytes, and representative blocks.
4. `Peak-survival evidence`: callstack bytes and block counts at the active peak versus the final event.
5. `Lifecycle evidence`: representative alloc, free-requested, and free-completed event IDs, with ambiguities called out.
6. `Findings`: category, confidence, evidence, inference, and affected callstack or allocation family.
7. `Unknowns`: missing timing, ownership, capture-boundary, callstack, or repeated-capture evidence.
8. `Suggested validation`: targeted experiments that could confirm or reject each leading hypothesis.

Useful validation experiments include repeated snapshots at equivalent workload milestones, extending tracing beyond expected cleanup, explicitly releasing suspected application references, synchronizing the device before the capture ends, and comparing behavior before and after allocator cache cleanup. Explain that cache cleanup can change reserved memory without proving that application references were released.

## Guardrails

- Keep SnapshotDB access read-only. Never run `create`, `insert`, `update`, `delete`, `drop`, `alter`, `replace`, `attach`, `detach`, `reindex`, or `vacuum` SQL.
- Do not persist focus, configuration, reports, exports, scratch databases, or readiness files.
- Do not import or deserialize pickle snapshots.
- Prefer packaged `pt-snap` templates. Use raw SQLite only for the optional lifetime aggregate that templates do not expose.
- Do not call every allocation without a free event a leak.
- Separate cumulative allocation volume from memory simultaneously live at an event.
- Keep static memory separate from dynamic candidates.
- Do not treat event IDs as timestamps or event-ID distance as elapsed time.
- Do not generalize from one address, callstack, size class, or capture to all allocations.
- Label evidence, inference, and unknowns separately.

## Verification Checklist

- `pt-snap` availability was verified without installing or switching environments.
- Database and device were selected explicitly without changing focus.
- Final event and all three memory peaks were recorded.
- Same-event allocator gaps came from `allocator_gap`.
- End-of-trace dynamic candidates and static memory were reported separately.
- Active-peak and final-event callstack attribution used the same device.
- Representative lifecycle events were checked for address reuse and ambiguous pairing.
- Dynamic block state was not used as leak evidence.
- Event-ID distances were not presented as time durations.
- Every finding has a conservative category and confidence level.
- Unknowns and validation experiments are included.
