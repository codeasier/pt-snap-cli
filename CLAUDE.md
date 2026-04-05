# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Start

```bash
# Install in development mode
pip install -e .

# Run all tests
pytest

# Run single test file
pytest tests/test_cli.py -v

# Run tests with coverage
pytest --cov=pt_snap_analyzer --cov-report=term-missing

# Quick test mode (no coverage)
tests/run_tests.sh -q

# Use CLI
pt-snap use examples/snapshot.pkl.db
pt-snap query --template-use leak_detection_v2
```

## Architecture Overview

PyTorch Memory Snapshot Analysis Tool - CLI for analyzing PyTorch memory snapshots stored as SQLite databases.

```
pt_snap_analyzer/
├── cli.py          # Typer CLI entry point (pt-snap command)
├── context.py      # SQLite database context manager (read-only)
├── config.py       # Configuration management
├── models/         # Data models (Block, Event, MemoryEventType)
└── query/          # Query engine
    ├── builder.py      # Fluent SQL builder
    ├── condition.py    # Condition expressions (eq, gt, lt, etc.)
    ├── executor.py     # Template query executor
    ├── mapper.py       # Result mapping to Python objects
    ├── registry.py     # Query template registry
    ├── config.py       # Query template config classes
    └── templates/      # YAML query templates
```

## Core Data Flow

1. **CLI** (`cli.py`) → parses commands
2. **Context** (`context.py`) → read-only SQLite connection
3. **Query Executor** → loads YAML template, renders with Jinja2, executes SQL
4. **Models** → structured results (Block, Event)

## Key Design Decisions

- **Read-only database access**: Uses `file:...?mode=ro` URI to prevent modification
- **Template-driven queries**: Predefined YAML templates in `query/templates/`
- **Device isolation**: Multi-GPU data separated by `device_id`
- **Fluent API**: `QueryBuilder` supports method chaining

## Available Query Templates

Located in `pt_snap_analyzer/query/templates/`:
- `leak_detection_v2` - Detect unfreed memory allocations
- `callstack_analysis_v2` - Analyze allocation call stacks
- `memory_timeline_v2` - Memory allocation timeline
- `active_blocks_v2` - Active memory blocks
- `memory_summary_v2` - Memory summary statistics
- `blocks_by_size_v2` - Block size distribution
- `events_by_action_v2` - Events grouped by action

## Development Notes

- Python 3.10+ required
- Code formatting: `black --line-length 100`
- Linting: `ruff` (configured in pyproject.toml)
- Test scripts use conda environment `openclaw` (see `tests/run_tests.sh`)
