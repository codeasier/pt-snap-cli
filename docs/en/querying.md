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
| `active_blocks` | Currently active (unfreed) memory blocks |
| `blocks_by_size` | Memory blocks sorted by size |
| `events_by_action` | Events grouped by action type |
| `memory_timeline` | Memory allocation timeline |

### Statistical Queries

Aggregation and analysis.

| Template | Description |
|----------|-------------|
| `callstack_analysis` | Analyze callstack information |
| `memory_summary` | Memory usage statistics |

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

Results display as a list:
- Shows first 10 results
- If more than 10, shows remaining count

```
Found 150 results:
  {'id': 1, 'address': '0x1000', 'size': 2048, ...}
  ...
  ... and 140 more
```

## Template Architecture

Query templates are defined in YAML format with:
- `version`: Template version
- `queries`: Query definitions with description, supported devices, parameters, SQL (Jinja2 templated), and output schema

**Supported type converters:** `int`, `float`, `str`, `bool`, `hex`, `datetime`

## Python API

For programmatic usage, see [ResultMapper API](result-mapper-api.md).
