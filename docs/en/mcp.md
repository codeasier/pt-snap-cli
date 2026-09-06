# MCP Server

[中文](../zh/mcp.md) | English

`pt-snap-cli` provides an MCP (Model Context Protocol) server that allows AI agents to interact with PyTorch memory snapshots programmatically.

## Installation

From a source checkout:

```bash
pip install -e .
```

The MCP server is installed as part of the core package.

## Starting the Server

```bash
pt-snap-mcp
```

This starts a FastMCP server that exposes tools for analyzing PyTorch memory snapshots.

## Available Tools

| Tool | Description |
|------|-------------|
| `get_focus` | Get the current analysis focus (database path, device ID, source) |
| `set_focus` | Set focus to a database and optional device. Use before running queries. |
| `list_templates` | List available query templates, optionally filtered by category |
| `get_template_info` | Get detailed information about a template including parameters |
| `execute_query` | Execute a query template against the focused database. Returns at most `max_rows` rows (default **100**; pass `0` for unlimited). See [Query Results and Row Limits](#query-results-and-row-limits). |
| `get_database_metadata` | Inspect import provenance for the focused or specified database |

## Available Resources

| Resource | Description |
|----------|-------------|
| `focus://current` | Current analysis focus state |

## Available Prompts

| Prompt | Description |
|--------|-------------|
| `analyze_memory_leaks` | Generate a prompt template for analyzing memory leaks |

## Typical Workflow

1. Call `set_focus` with `db_path` to point to a SnapshotDB `.db` file
2. Call `list_templates` to discover available queries
3. Call `get_template_info` with a template name to see its parameters
4. Call `execute_query` with the template name and parameters
5. Call `get_database_metadata` when import provenance or cache compatibility is needed

## Example Usage

```python
# Set focus to a SnapshotDB file
set_focus(db_path="/path/to/snapshot.db", device_id=0)

# List templates
list_templates()
# Returns: [{"name": "leak_detection", "description": "...", ...}, ...]

# Get template details
get_template_info("leak_detection")
# Returns: {"name": "leak_detection", "parameters": {"min_size": {...}}, ...}

# Run a query
execute_query("leak_detection", params={"min_size": 1024})
# Returns: {"total": 5, "returned": 5, "device_id": 0, "rows": [...]}

# Inspect database import metadata
get_database_metadata()
# Returns: {"status": "available", "metadata": {"source_sha256": "...", ...}}
```

## Query Results and Row Limits

`execute_query(template, params=None, device_id=None, max_rows=100)` returns:

| Field | Meaning |
|-------|---------|
| `total` | Number of rows the query matches. This is exact even when the result was capped: when `max_rows` is hit, the server runs a `COUNT(*)` over the same query. |
| `returned` | Number of rows actually included in `rows`. |
| `device_id` | The device the query ran against (explicit `device_id`, else the focused device, else the first device in the database). |
| `rows` | The result rows as dictionaries of raw SQLite values. |

**The MCP default is `max_rows=100`, which differs from the CLI.** `pt-snap query`
shows every row unless `-n` is given; the MCP tool caps output so a large result
cannot flood an agent's context. Treat `returned < total` as "more data exists":
raise `max_rows`, pass `0` for unlimited, or narrow the query parameters. Do not
sum or count over `rows` as if it were the complete result.

```python
result = execute_query("leak_detection", params={"min_size": 1024})
if result["returned"] < result["total"]:
    result = execute_query("leak_detection", params={"min_size": 1024}, max_rows=0)
```

Templates that expose a `limit` parameter (for example `leak_detection`,
`allocation`, `block`, `event`) apply `min(limit, max_rows)` when both are set.

## CLI Commands

The MCP entry point is declared in `pyproject.toml`:

```toml
[project.scripts]
pt-snap-mcp = "pt_snap_cli.mcp.server:main"
```
