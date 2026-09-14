---
name: pt-snap-memory-fragmentation
description: Diagnose suspected PyTorch allocator fragmentation, cache pressure, or segment churn from an existing SnapshotDB when reserved memory stays above active or allocated memory, peaks diverge, or OOM-like pressure needs conservative allocator evidence.
---

# pt-snap-memory-fragmentation

## Overview

Use this skill to gather read-only SnapshotDB evidence about allocator gaps,
segment retention, and segment churn. The workflow can identify pressure that is
consistent with fragmentation, but it cannot prove fragmentation from a
SnapshotDB alone.

SnapshotDB does not contain free-region topology, size-bin history, or the
largest contiguous free region. Therefore, `reserved - active` is not pure
fragmentation, and no definitive fragmentation ratio or OOM root cause can be
derived from this workflow.

## Required Inputs

- A SnapshotDB path, supplied explicitly or resolved from the current
  `pt-snap focus`.
- A device ID, supplied explicitly or already selected by the current focus.

Optional inputs:

- An event range to investigate, expressed as the `<range_start>` and
  `<range_end>` event IDs. Use `0` as `<range_start>` unless a validated
  explicit lower bound applies. Omit every upper-bound parameter while the
  scope has no validated upper bound.
- A positive page size for timeline and event pagination; default `1000`.
- Selected peak or pressure event IDs for active-block attribution.

Replace `<db_path>`, `<device_id>`, `<page_size>`, `<offset>`, `<range_start>`,
and `<range_end>` placeholders with validated values before running commands.
Quote the database path in every command.

## Prerequisite Phase

### 1. Verify pt-snap

Run:

```bash
command -v pt-snap
pt-snap --help
```

If either command fails, stop and direct the user to `pt-snap-setup`. Never
install, upgrade, repair, or switch Python environments from this skill.

### 2. Resolve scope without persisting focus

If either input was not supplied, inspect the current state:

```bash
pt-snap focus
```

Use the displayed database and focused device only when both are present. If
either remains absent or ambiguous, ask the user to select it and stop until it
is explicit. Do not run `pt-snap focus <database_path>`, use `--session`, or
otherwise persist or modify focus. After resolving the scope, pass both the
database and device explicitly to every diagnostic query and report command.

This skill accepts SnapshotDB files only. Do not run `pt-snap import`, open a
pickle, or deserialize a pickle. If only a pickle is available, stop and explain
that conversion requires a separate trusted-input decision because pickle
loading is not a sandbox.

### 3. Verify metadata and required templates before diagnosis

Run these checks before any diagnostic query:

```bash
pt-snap metadata "<db_path>" --json
pt-snap query --template-info memory_peak
pt-snap query --template-info allocator_gap
pt-snap query --template-info allocation
pt-snap query --template-info event
```

Stop on invalid database metadata/schema or a missing required template, and
report the exact failure. A compatible legacy database may report metadata as
unavailable; record that provenance limitation rather than treating it as
import metadata. Do not replace a missing required template with raw SQL.

Before using the optional attribution phase, also verify its surfaces:

```bash
pt-snap query --template-info active_memory_callstack_at_event
pt-snap report peak-memory --help
```

## Diagnostic Workflow

### 1. Establish separate peaks and same-event gaps

Run:

```bash
pt-snap query "<db_path>" --device <device_id> --template-use memory_peak --params '{"start_id":<range_start>}'
pt-snap query "<db_path>" --device <device_id> --template-use allocator_gap --params '{"start_id":<range_start>}'
```

The `start_id` filter keeps peak events inside the validated runtime range;
with the default `0` it excludes negative synthetic reconstruction rows, which
could otherwise win a peak and whose IDs cannot drive dynamic attribution
later. When the scope has a validated upper bound, add `"end_id":<range_end>`
to both parameter objects.

Use `memory_peak` for the separate allocated, active, and reserved peak values
and their event IDs. These peaks may occur at different events, so never
subtract one peak value from another. Use `allocator_gap` for
`reserved - active` and `reserved - allocated` comparisons at the same selected
peak event.

Treat the gaps as allocator/cache pressure indicators. They include effects
such as reusable cache, inactive blocks, allocator bookkeeping, and possibly
unusable free regions; they are not a direct measurement of fragmentation.

### 2. Read the event-ordered memory curve in bounded pages

Run `allocation` with a positive page size, `min_id=<range_start>`, and
increasing offsets:

```bash
pt-snap query "<db_path>" --device <device_id> --template-use allocation --params '{"min_id":<range_start>,"order_by":"id","order_dir":"ASC","limit":<page_size>,"offset":<offset>}'
```

Start with offset `0`, increase it by `<page_size>`, and stop when a page has no
rows. Preserve event order while examining the allocated, active, and reserved
curve. Add `"max_id":<range_end>` consistently on every page when the scope has
an upper event bound.

Look for sustained rather than isolated gaps, reserved plateaus after active
memory falls, repeated reserve growth, and whether later allocation activity
reuses an existing reserved plateau. Event IDs establish ordering, not time;
event-ID differences are not durations or rates.

### 3. Inspect both runtime segment operation pairs

Query all four segment actions with `min_id=<range_start>`, bounded pages, and
event order:

```bash
pt-snap query "<db_path>" --device <device_id> --template-use event --params '{"min_id":<range_start>,"action":0,"order_by":"id","order_dir":"ASC","limit":<page_size>,"offset":<offset>}'
pt-snap query "<db_path>" --device <device_id> --template-use event --params '{"min_id":<range_start>,"action":1,"order_by":"id","order_dir":"ASC","limit":<page_size>,"offset":<offset>}'
pt-snap query "<db_path>" --device <device_id> --template-use event --params '{"min_id":<range_start>,"action":2,"order_by":"id","order_dir":"ASC","limit":<page_size>,"offset":<offset>}'
pt-snap query "<db_path>" --device <device_id> --template-use event --params '{"min_id":<range_start>,"action":3,"order_by":"id","order_dir":"ASC","limit":<page_size>,"offset":<offset>}'
```

When the scope has a validated upper bound, add `"max_id":<range_end>` to every
page of all four actions.

Interpret the operation pairs separately:

- `0=segment_map` and `1=segment_unmap` describe runtime expandable-segment
  mapping operations.
- `2=segment_alloc` and `3=segment_free` describe runtime segment acquisition
  and release operations.

Repeat pagination for each action until no rows remain. The non-negative
`min_id` filter is mandatory here because negative IDs are synthetic
reconstruction events for segments that existed before collection; they are not
runtime segment operations.

Compare the operation ordering with the memory curve. Repeated map/unmap or
alloc/free activity can support a segment-churn inference, while reserve growth
without corresponding release can support segment-retention or cache-pressure
inferences. Event size sums are operation volume, not retained bytes or
reserved deltas. Do not subtract summed map/unmap or alloc/free sizes and call
the result retained memory.

### 4. Optionally aggregate operations or locate maximum observed gaps

Packaged templates expose ordered event rows and same-event gaps at peak events,
but they do not aggregate segment operation counts/sizes or locate maximum gaps
over the full runtime range. Only when one of those aggregates is needed, and
only when the `sqlite3` CLI is available, use this read-only fallback. Scope
these aggregates to the same validated range: substitute `<range_start>` for
the literal `0` in the predicates below, and append `AND id <= <range_end>` to
every statement when the scope has a validated upper bound.

First validate `<device_id>` as a non-negative decimal integer matching
`^[0-9]+$`; reject signs, whitespace, separators, and every other character
before interpolating it into a table name. Then run only `SELECT`/`WITH SELECT`
statements through `sqlite3 -readonly`:

```bash
device_id='<device_id>'
case "$device_id" in
  ''|*[!0-9]*) printf '%s\n' 'device ID must be a non-negative decimal integer' >&2; exit 1 ;;
esac
sqlite3 -readonly "<db_path>" "
SELECT action,
       COUNT(*) AS operation_count,
       COALESCE(SUM(size), 0) AS operation_volume_bytes,
       MAX(size) AS largest_operation_bytes
FROM trace_entry_${device_id}
WHERE id >= <range_start> AND action IN (0, 1, 2, 3)
GROUP BY action
ORDER BY action;

SELECT id, allocated, active, reserved,
       reserved - active AS reserved_active_gap
FROM trace_entry_${device_id}
WHERE id >= <range_start>
ORDER BY reserved_active_gap DESC, id ASC
LIMIT 1;

SELECT id, allocated, active, reserved,
       reserved - allocated AS reserved_allocated_gap
FROM trace_entry_${device_id}
WHERE id >= <range_start>
ORDER BY reserved_allocated_gap DESC, id ASC
LIMIT 1;"
```

The SQL remains subject to the same limitations: operation sums measure churn
volume, maximum counter gaps do not reveal free-region topology, and neither is
a fragmentation ratio. If read-only mode is unavailable or device validation
fails, skip this phase and list the aggregate as unknown. No writable SQL is
permitted.

### 5. Optionally describe active blocks at selected events

After verifying the optional surfaces, use either or both of these commands:

```bash
pt-snap report peak-memory "<db_path>" --device <device_id> --metric active --limit 20 --json
pt-snap query "<db_path>" --device <device_id> --template-use active_memory_callstack_at_event --params '{"event_id":<event_id>,"include_static":true,"min_size":0,"top_n":20}'
```

Use these results only to describe active blocks at a selected event. They do
not attribute reserved bytes, cached bytes, or the `reserved - active` gap to
those callstacks. Keep static and dynamic active-block groups distinct.

Do not use `callstack_analysis` as segment-source attribution. Its query has no
action filter, so it mixes event types and cannot identify which callstack
caused segment mapping, acquisition, retention, cache bytes, or fragmentation.

### 6. Classify evidence conservatively

Choose one or more classifications and assign `low`, `medium`, or `high`
confidence based on the stated evidence and unknowns:

- `allocator/cache pressure`: reserved memory stays materially above active or
  allocated memory, without enough topology evidence to isolate fragmentation.
- `segment retention/churn`: runtime segment operations and the ordered curve
  show repeated mapping/acquisition activity or limited release; this describes
  allocator behavior, not exact retained bytes.
- `fragmentation-consistent pressure`: sustained same-event gaps and allocation
  pressure coexist with segment behavior that is compatible with unusable free
  regions. This is a hypothesis, never proof of fragmentation.
- `normal allocator behavior`: reserve reuse and segment caching are stable and
  consistent with expected allocator caching, with no corroborating pressure.
- `inconclusive`: missing topology, incomplete capture scope, absent operation
  pairs, coarse event ordering, or external device-memory evidence prevents a
  stronger classification.

Do not claim a definitive fragmentation ratio or OOM root cause. Even high
confidence applies only to the selected classification and observed scope, not
to facts the SnapshotDB cannot represent.

## Output Template

Report each section separately and in this order:

1. `Scope`: database path, device ID, event range, page size, metadata status,
   and templates verified.
2. `Evidence`: separate peaks/event IDs, same-event gaps, ordered curve
   behavior, and both segment operation pairs. Label SQL sums as operation
   volume.
3. `Inference`: patterns supported by the evidence without restating them as
   measured facts.
4. `Unknowns`: free-region topology, size-bin history, largest contiguous free
   region, wall-clock timing, device-global consumers, and missing capture
   context.
5. `Classifications and confidence`: category, confidence, supporting evidence,
   contradictory evidence, and scope limitations.
6. `Validation experiments`: a targeted experiment for each leading inference
   and what outcome would support or reject it.

Useful validation experiments include repeating captures at equivalent workload
milestones, extending capture through expected cleanup, synchronizing before a
comparison point, comparing controlled allocator configurations, and measuring
whether subsequent allocations reuse reserved memory. Allocator cache cleanup
may lower reserved memory, but that does not prove fragmentation or release of
application references. Use external allocator/runtime telemetry when an
experiment needs size-bin or contiguous-free-region evidence.

## Guardrails

- Keep every SnapshotDB access read-only.
- Never install packages or switch Python environments; delegate setup to
  `pt-snap-setup` and stop.
- Never import or deserialize pickle input.
- Never persist focus or configuration.
- Never write reports, exports, scratch databases, focus files, or readiness
  files; keep results on standard output and do not redirect them to files.
- Prefer packaged templates. Raw SQLite is optional only for segment operation
  counts/sizes or maximum observed gaps that packaged templates cannot provide.
- Validate the device ID as a non-negative decimal integer before table-name
  interpolation, use `sqlite3 -readonly`, and run no writable SQL.
- Keep separate-event peaks distinct and use `allocator_gap` for same-event
  comparisons.
- Exclude negative synthetic reconstruction events from runtime segment
  analysis with the validated non-negative `min_id`/`start_id` (default `0`)
  or `id >= <range_start>`.
- Apply one validated event range across every phase so peaks, the curve,
  segment operations, optional aggregates, and attribution inputs share a
  single scope; reject negative peak event IDs before attribution instead of
  attributing them.
- Treat operation counts and size sums as operation volume, not retained bytes.
- Event IDs are ordering markers, not timestamps.
- Separate evidence, inference, unknowns, classifications/confidence, and
  validation experiments.

## Verification Checklist

- `pt-snap` availability was verified without installation or environment
  changes.
- An explicit database and device were resolved without changing focus.
- Metadata and required templates were verified before diagnosis.
- Separate peaks came from `memory_peak`; same-event gaps came from
  `allocator_gap`.
- The same validated event range was applied consistently to peaks, the
  ordered curve, segment operation pairs, optional aggregates, and
  attribution inputs.
- The allocated/active/reserved curve used paginated, event-ordered `allocation`
  queries.
- Runtime `segment_map`/`segment_unmap` and `segment_alloc`/`segment_free` were
  both inspected with synthetic events excluded.
- Optional raw SQL, if used, stayed read-only and within the aggregate boundary.
- Active-block callstacks were not presented as reserved/cache attribution.
- Conclusions used conservative classifications, explicit confidence, unknowns,
  and validation experiments.
