# pt-snap-cli

[中文文档](README_zh.md) | English

A command-line tool for analyzing PyTorch memory snapshots. Set a snapshot database, run built-in queries, and inspect memory usage, leaks, and timelines.

## Installation

```bash
pip install -e .
```

## Quick Start

To start from a raw PyTorch memory snapshot, import the pickle into a SnapshotDB with pt-snap's built-in snapshot support, then list the available query templates:

> **Security warning:** Import only pickle snapshots from a trusted source. Pickle
> deserialization can execute arbitrary code. `pt-snap import` is not a sandbox.

```bash
pt-snap import snapshot.pkl
pt-snap metadata snapshot.pkl.db
pt-snap query --list
```

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

To divide a large snapshot into independently replayable files before import,
use exactly one split strategy and an output directory that does not exist:

```bash
pt-snap split snapshot.pkl --slices 4 --output snapshot-slices
```

See [Splitting Snapshots](docs/en/splitting.md) for device selection, JSON output,
deterministic names, replay validation, and failure-safe publication.

See the [full quick start guide](docs/en/quickstart.md) for a walkthrough.

## Commands

| Command | Description |
|---------|-------------|
| `pt-snap focus` | Set and manage analysis focus (database + device) |
| `pt-snap import <snapshot.pkl>` | Import a PyTorch memory snapshot pickle into a SnapshotDB |
| `pt-snap split <snapshot.pkl>` | Create replayable per-device snapshot slices |
| `pt-snap metadata [database.db]` | Inspect SnapshotDB import provenance and compatibility metadata |
| `pt-snap query` | Run memory analysis queries |
| `pt-snap report` | Generate higher-level memory analysis reports |
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
| `get_database_metadata` | Inspect import metadata for the focused or specified database |

See the [MCP guide](docs/en/mcp.md) for setup and usage details.

## Documentation

| Topic | Guide |
|-------|-------|
| Getting started | [Quick Start](docs/en/quickstart.md) |
| Managing focus | [Focus Management](docs/en/focus-management.md) |
| Running queries | [Querying](docs/en/querying.md) |
| Splitting snapshots | [Splitting Snapshots](docs/en/splitting.md) |
| MCP server | [MCP Guide](docs/en/mcp.md) |
| Database format | [SnapshotDB Schema](docs/en/database.md) |
| Python API | [ResultMapper API](docs/en/result-mapper-api.md) |

## Query Templates

9 built-in templates across 3 categories:

- **Basic**: `block`, `event`, `allocation`
- **Statistical**: `active_blocks_at_event`, `allocator_gap`, `callstack_analysis`, `memory_peak`
- **Business**: `active_memory_callstack_at_event`, `leak_detection`

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

### CLI/MCP semantic contract

The CLI and MCP server must keep using the shared API/core services as the single
semantic source of truth. The CLI may render results as terminal text and the MCP
server may return JSON-like tool payloads, but normalized meanings must stay in
sync for focus handling, query template listing, template metadata, query
execution, and shared error cases.

`tests/test_contract_cli_mcp.py` compares normalized CLI output with MCP tool
results on the same inputs and fixtures. When adding a new shared CLI/MCP capability,
update or add a contract case in that file so CI fails if either adapter drifts
from the shared behavior.
