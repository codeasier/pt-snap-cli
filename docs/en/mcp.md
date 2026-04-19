# MCP Server

[中文](../zh/mcp.md) | English

`pt-snap-cli` provides an MCP (Model Context Protocol) server that allows AI agents to interact with PyTorch memory snapshots programmatically.

## Installation

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
| `execute_query` | Execute a query template against the focused database |

## Available Resources

| Resource | Description |
|----------|-------------|
| `focus://current` | Current analysis focus state |

## Available Prompts

| Prompt | Description |
|--------|-------------|
| `analyze_memory_leaks` | Generate a prompt template for analyzing memory leaks |

## Typical Workflow

1. Call `set_focus` with `db_path` to point to a snapshot file
2. Call `list_templates` to discover available queries
3. Call `get_template_info` with a template name to see its parameters
4. Call `execute_query` with the template name and parameters

## Example Usage

```python
# Set focus to a snapshot
set_focus(db_path="/path/to/snapshot.db", device_id=0)

# List templates
list_templates()
# Returns: [{"name": "leak_detection", "description": "...", ...}, ...]

# Get template details
get_template_info("leak_detection")
# Returns: {"name": "leak_detection", "parameters": [...], ...}

# Run a query
execute_query("leak_detection", params={"min_size": 1024})
# Returns: {"total": 5, "returned": 5, "rows": [...]}
```

## CLI Commands

The MCP entry point is declared in `pyproject.toml`:

```toml
[project.scripts]
pt-snap-mcp = "pt_snap_cli.mcp.server:main"
```
