# pt-snap-cli

[中文文档](README_zh.md) | English

A command-line tool for analyzing PyTorch memory snapshots. Set a snapshot database, run built-in queries, and inspect memory usage, leaks, and timelines.

## Installation

From a source checkout:

```bash
pip install -e .
```

## Quick Start

To start from a raw PyTorch memory snapshot, import the pickle into a SnapshotDB with pt-snap's built-in snapshot support, then list the available query templates:

> **Security warning:** Import only pickle snapshots from a trusted source. Pickle
> deserialization can execute arbitrary code. The loader rejects non-`builtins`
> global objects, but `pt-snap import` is not a sandbox.

```bash
pt-snap import snapshot.pkl
pt-snap metadata snapshot.pkl.db
pt-snap query --list
```

```bash
# Set the snapshot database and device
pt-snap focus snapshot.pkl.db --device 0

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

See the [MCP guide](docs/en/mcp.md) for setup and usage details.

## Documentation

See the [documentation index](docs/README.md) for all English and Chinese guides.

| Topic | Guide |
|-------|-------|
| Getting started | [Quick Start](docs/en/quickstart.md) |
| Managing focus | [Focus Management](docs/en/focus-management.md) |
| Running queries | [Querying](docs/en/querying.md) |
| Splitting snapshots | [Splitting Snapshots](docs/en/splitting.md) |
| MCP server | [MCP Guide](docs/en/mcp.md) |
| Database format | [SnapshotDB Schema](docs/en/database.md) |
| Python API | [SnapshotAnalyzer API](docs/en/snapshot-analyzer-api.md) |
| Result mapping utility | [ResultMapper API](docs/en/result-mapper-api.md) |

## Development

```bash
pip install -e ".[dev]"         # Install development dependencies
pytest                           # Run all tests
black --check . && ruff check .  # Check formatting and lint
python -m build                  # Build sdist and wheel
```
