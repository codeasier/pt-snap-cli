# Querying

[中文](../zh/querying.md) | English

Run memory analysis queries against your snapshot database.

## The Query Command

```bash
pt-snap query [DB_PATH] [--template-use <template_name>] [--params <json>] \
  [--device <id>] [--list] [--category <category>] \
  [--template-info <template>] [-n <rows>]
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
| `--template-info` | Show template details (parameters and output schema) |
| `-n` | Maximum displayed rows; zero or a negative value means unlimited |

## Query Templates

Templates are organized into three categories. Use `pt-snap query --list` to see them all, or filter with `--category`.

### Basic Queries

Raw data lookup.

| Template | Description |
|----------|-------------|
| `block` | Query memory blocks with flexible field filters |
| `event` | Query memory events with flexible field filters |
| `allocation` | Memory allocation timeline (id, allocated, active, reserved) |

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
| `leak_detection` | Find allocations without matching free events |
| `active_memory_callstack_at_event` | Aggregate blocks active at a specific event by allocation callstack, with static and preexisting memory classified separately |

## Leak Detection

```bash
pt-snap query --template-use leak_detection --params '{"min_size": 1024}'
```

`min_size` is the minimum candidate size in bytes and defaults to `0`. Select
the target device with the command-level `--device` option, not inside `--params`.

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

The same rules apply to `SnapshotAnalyzer.execute_query()` and the MCP
`execute_query` tool, which raise `TemplateRenderError` with the same message.

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
pt-snap query --template-use active_memory_callstack_at_event --params '{"event_id": 1234, "include_static": true, "top_n": 20}'
```

This query:

- starts from the active block set at `event_id`
- joins dynamic blocks back to their allocation events in `trace_entry_<device>`
- groups by allocation callstack
- emits static and preexisting memory as dedicated groups instead of inventing a callstack

`top_n` only bounds dynamic callstack groups; `static` and
`preexisting_live_at_event` groups are always returned and are never pushed out
by larger dynamic groups.

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

Example output (with `-n 2`):

```
Found 150 results, showing 2:
  {'id': 1, 'address': 4096, 'size': 2048, ...}
  {'id': 2, 'address': 8192, 'size': 4096, ...}
  ... and 148 more (use -n to show more)
```

CLI, Python API, and MCP query results contain raw SQLite values. A template's
`output_schema` is metadata and is not applied automatically during query
execution. Use `ResultMapper` explicitly when converted values such as
hexadecimal address strings are required.

## Template Architecture

Query templates are defined in YAML format with:
- `version`: Template version
- `queries`: Query definitions with description, supported devices, parameters, SQL (Jinja2 templated), and output schema
- Each parameter declares `type`, `default`, `required`, `description`, and optionally `choices`, a closed list of accepted values that is mandatory for parameters rendered as SQL identifiers or keywords

When passed explicitly to `ResultMapper`, recognized mapping types are `int`,
`float`, `str`, `bool`, `hex`, and `datetime`; `datetime` is currently a
pass-through declaration rather than a parser.

## Optional Result Mapping

For optional row conversion and model mapping, see
[ResultMapper API](result-mapper-api.md).

For the high-level programmatic focus and query facade, see
[SnapshotAnalyzer API](snapshot-analyzer-api.md).
