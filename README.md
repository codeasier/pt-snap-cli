# pt-snap-cli

[中文文档](README_zh.md) | English

A command-line tool for analyzing PyTorch memory snapshots. Set a snapshot database, run built-in queries, and inspect memory usage, leaks, and timelines.

## Installation

```bash
pip install -e .
```

## Quick Start

```bash
# Set the snapshot database and device
pt-snap focus examples/snapshot_expandable.pkl.db --device 0

# List available queries
pt-snap query --list

# Run a query (automatically uses the focused device)
pt-snap query --template-use memory_peak

# Detect potential memory leaks
pt-snap query --template-use leak_detection --params '{"min_size": 1024}'
```

See the [full quick start guide](docs/en/quickstart.md) for a walkthrough.

## Commands

| Command | Description |
|---------|-------------|
| `pt-snap focus` | Set and manage analysis focus (database + device) |
| `pt-snap query` | Run memory analysis queries |
| `pt-snap config` | Manage global configuration |
| `pt-snap-mcp` | Start the MCP server for agent integration |

## MCP Server

`pt-snap-cli` provides an MCP (Model Context Protocol) server so AI agents can interact with PyTorch memory snapshots programmatically.

```bash
# Start the MCP server
pt-snap-mcp
```

The server exposes the following tools:

| Tool | Description |
|------|-------------|
| `get_focus` | Get the current analysis focus |
| `set_focus` | Set focus to a database and optional device |
| `list_templates` | List available query templates |
| `get_template_info` | Get template details and parameters |
| `execute_query` | Run a query template against the focused database |

See the [MCP guide](docs/en/mcp.md) for setup and usage details.

## Documentation

| Topic | Guide |
|-------|-------|
| Getting started | [Quick Start](docs/en/quickstart.md) |
| Managing focus | [Focus Management](docs/en/focus-management.md) |
| Running queries | [Querying](docs/en/querying.md) |
| MCP server | [MCP Guide](docs/en/mcp.md) |
| Database format | [SnapshotDB Schema](docs/en/database.md) |
| Python API | [ResultMapper API](docs/en/result-mapper-api.md) |

## Query Templates

6 built-in templates across 3 categories:

- **Basic**: `block`, `event`, `allocation`
- **Statistical**: `callstack_analysis`, `memory_peak`
- **Business**: `leak_detection`

See [Querying](docs/en/querying.md) for details.

## Project Structure

```
pt-snap-cli/
├── src/
│   └── pt_snap_cli/
│       ├── cli.py              # CLI entry point
│       ├── context.py          # Database context manager
│       ├── config.py           # Focus management
│       ├── api.py              # Python API layer
│       ├── query/
│       │   ├── builder.py      # Query builder
│       │   ├── executor.py     # Query executor
│       │   ├── mapper.py       # Result mapper
│       │   ├── registry.py     # Query registry
│       │   ├── condition.py    # Query conditions
│       │   ├── config.py       # Query configuration
│       │   └── templates/      # Query templates
│       ├── models/             # Data models
│       └── mcp/                # MCP server for agent integration
├── tests/                  # Test files
├── examples/               # Example data
└── docs/                   # Documentation
```

## Development

```bash
pytest                           # Run all tests
./tests/run_tests.sh             # Full test run with coverage
black . && ruff check .          # Format and lint
python -m build                  # Build sdist and wheel
```
