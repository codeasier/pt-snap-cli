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

### Business Queries

Domain-specific analysis.

| Template | Description |
|----------|-------------|
| `leak_detection` | Find allocations without matching free events |

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
