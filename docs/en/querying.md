# Querying

[English](querying.md) | [中文](../zh/querying.md)

Run memory analysis queries against your snapshot database.

## The Query Command

```bash
pt-snap query [--template-use <template_name>] [--params <json>] [--device <id>] [--list] [--template-info <template>]
```

**Parameters:**

| Flag | Description |
|------|-------------|
| `db_path` | SQLite database file path (optional if context is configured) |
| `--template-use` | Query template name (required unless using `--list` or `--template-info`) |
| `--params` | Query parameters in JSON format |
| `--device` | Device ID |
| `--list` | List available query templates |
| `--category` | Filter templates by category: `basic`, `statistical`, `business` |
| `--template-info` | Show template details (parameters and output schema) |

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
| `active_blocks_at_event` | List blocks that are still active at a specific event, with optional static block inclusion |
| `allocator_gap` | Compare allocated, active, and reserved peak events and same-event gaps |

### Business Queries

Domain-specific analysis.

| Template | Description |
|----------|-------------|
| `leak_detection` | Find allocations without matching free events |
| `active_memory_callstack_at_event` | Aggregate blocks active at a specific event by allocation callstack, with static memory classified separately |

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

- `allocEventId <= event_id`
- and `freeEventId = -1` or `freeEventId > event_id`

When `include_static=true`, blocks with `allocEventId=-1 AND freeEventId=-1` are also included and labeled as `static`.

### 3. Attribute active memory to callstacks at that event

```bash
pt-snap query --template-use active_memory_callstack_at_event --params '{"event_id": 1234, "include_static": true, "top_n": 20}'
```

This query:

- starts from the active block set at `event_id`
- joins dynamic blocks back to their allocation events in `trace_entry_<device>`
- groups by allocation callstack
- emits static memory as a dedicated group instead of inventing a callstack

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

**Example:**
```bash
pt-snap query --template-use leak_detection --params '{"min_size": 1024}'
```

Parameters:
- `min_size`: Minimum leak size in bytes (default: 0)
- `device_id`: Device ID

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
  {'id': 1, 'address': '0x1000', 'size': 2048, ...}
  {'id': 2, 'address': '0x2000', 'size': 4096, ...}
  ... and 148 more (use -n to show more)
```

## Template Architecture

Query templates are defined in YAML format with:
- `version`: Template version
- `queries`: Query definitions with description, supported devices, parameters, SQL (Jinja2 templated), and output schema

**Supported type converters:** `int`, `float`, `str`, `bool`, `hex`, `datetime`

## Python API

For programmatic usage, see [ResultMapper API](result-mapper-api.md).
