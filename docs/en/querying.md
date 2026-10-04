# Querying

[中文](../zh/querying.md) | English

Run memory analysis queries against your snapshot database.

## The Query Command

```bash
pt-snap query [DB_PATH] [--template-use <template_name>] [--params <json>] \
  [--device <id>] [--list] [--category <category>] \
  [--template-info <template>] [-n <rows>] [--exact-total] [--timeout <seconds>] [--json]
```

**Parameters:**

| Flag | Description |
|------|-------------|
| `db_path` | SQLite database file path (optional if focus is configured) |
| `--template-use` | Query template name (required unless using `--list` or `--template-info`) |
| `--params` | Query parameters in JSON format |
| `--device` | Device ID |
| `--list` | List available query templates |
| `--category` | Filter templates by category: `basic`, `statistical`, `business` |
| `--template-info` | Show template details (parameters, output schema, and field semantics) |
| `-n` | Maximum displayed rows; zero or a negative value means unlimited. Separate from `--timeout`. |
| `--exact-total` | Run a `COUNT` of the matching set. Default `total` is the returned-row count. |
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
pt-snap report peak-memory [db_path] [--device <id>] [--metric active|allocated|reserved] [--include-static|--exclude-static] [--limit <n>] [--json]
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

- `memory_peak`
- `allocator_gap`
- `active_memory_callstack_at_event`

and prints either a human-readable summary or JSON.

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
`--exact-total` runs a `COUNT` of the matching set (ignoring `limit` /
`offset` / `top_n`) and sets `total_is_exact` to true. When a finite
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
normalization. When `-n` is set, `limit` is the trailing SQL LIMIT after the
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

## Frame Memory Breakdown

After importing with this version, inspect the original ordered frame array or
decompose live memory after an event:

```bash
pt-snap query --template-use event_frames --params '{"event_id":100}' --json
pt-snap query --template-use active_memory_frame_tree_at_event --params '{"event_id":100}' --json
pt-snap report memory-tree --event-id 100
pt-snap report memory-tree --event-id 100 --json
pt-snap report memory-tree --event-id 100 --format html > memory-tree.html
```

The HTML file is self-contained: open it locally, click a frame to zoom, reset
to show the whole tree, or search filenames/functions. Width measures live
block bytes, not CPU time or allocation traffic. No static server is needed.
`--device` selects the device; `--exclude-static` omits static/preexisting
memory; `--min-size` filters individual blocks. `--event-id` is required.
The report requests a complete tree without a ranked or row cap.

| Field | Meaning |
| --- | --- |
| `node_id`, `parent_id` | Caller-path identity and direct parent; `root` is the total |
| `depth`, `frame_id` | Caller-first level and structured frame identity |
| `size_bytes`, `requested_bytes`, `block_count` | Inclusive occupancy/count for this node and descendants |
| `self_bytes`, `self_requested_bytes`, `self_block_count` | Allocations whose recorded stack ends at this node |
| `percent_of_total` | 0–100 byte share of root occupancy after block/category filters, before output row caps |

For each node, inclusive occupancy equals self occupancy plus the inclusive
occupancy of its direct children. Sum `self_bytes` across all nodes, or sum
inclusive bytes at one complete cut through the tree; summing inclusive bytes
across levels counts allocations repeatedly. An internal node can have self
bytes when a recorded stack ends there. Recursion and identical frames under
different callers remain separate paths.

Only blocks with `allocEventId <= event_id` and a later or absent
`freeEventId` are attributed dynamically. `freeEventId` is `free_completed`,
so pending-free memory is still included. Static, preexisting, and missing or
damaged stack links remain explicit synthetic leaves. This is active-block
occupancy and does not decompose reserved bytes. Event IDs mark ordering, not
elapsed time. `min_size` and `include_static` change the root denominator.
If a direct query uses `-n`/`max_rows`, inspect its completeness flags: a
truncated set of node rows is not a complete tree. Old text-only databases
must be re-imported; the analyzer does not reconstruct frames from text.

The Python API uses the same template and contracts:

```python
from pathlib import Path
from pt_snap_cli import SnapshotAnalyzer

with SnapshotAnalyzer(db_path=Path("snapshot.pkl.db"), device_id=0) as analyzer:
    frames = analyzer.execute_query("event_frames", params={"event_id": 100})
    tree = analyzer.execute_query("active_memory_frame_tree_at_event", params={"event_id": 100})
```

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
