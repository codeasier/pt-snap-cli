# pt-snap-cli

[中文文档](README_zh.md) | English

PyTorch Memory Snapshot Analysis CLI - A command-line tool for analyzing PyTorch memory snapshots.

## Installation

```bash
pip install -e .
```

## Usage

### pt-snap CLI Usage

#### 1. Check Version

```bash
pt-snap --version
```

#### 2. Set Database

Use a snapshot database file:

```bash
pt-snap use <path/to/snapshot.pkl.db>
```

Example:
```bash
pt-snap use examples/snapshot_large.pickle.db
```

This command validates the database and displays the list of available devices.

### Context Management

`pt-snap` supports project-scoped context so different terminals, agents, or working directories can analyze different databases without overwriting each other.

#### Set Project Database

```bash
# Set and validate the database for the current project directory
pt-snap use /path/to/your/snapshot.db
```

After successful setup, the database path is saved to `.pt-snap/context.json` in the current directory.

#### Session-Scoped Override

Use `PT_SNAP_DB_PATH` when one shell or agent needs an isolated database without changing project context:

```bash
export PT_SNAP_DB_PATH=/path/to/agent-specific/snapshot.db
pt-snap query --template-use memory_summary_v2
```

You can also print the export command after validation:

```bash
pt-snap use /path/to/agent-specific/snapshot.db --session
```

#### View Effective Context

```bash
# View the effective database and its source
pt-snap use
```

#### Query with Context (No dbpath Needed)

```bash
# List all query templates
pt-snap query --list

# Execute query (automatically uses the resolved database context)
pt-snap query --template-use memory_summary_v2

# Query with parameters
pt-snap query --template-use leak_detection_v2 --params '{"min_size": 1024}'

# Specify device
pt-snap query --template-use active_blocks_v2 --device 0
```

#### Resolution Priority

Database context is resolved in this order:

1. Explicit `pt-snap query <db_path>`
2. `PT_SNAP_DB_PATH`
3. Nearest `.pt-snap/context.json`, searching from the current directory upward
4. Legacy global config at `~/.config/pt-snap-cli/config.json`

Even with context configured, you can still specify a different database on the command line:

```bash
# Use temporarily specified database (does not affect context)
pt-snap query /path/to/other.db --template-use memory_summary_v2
```

#### Legacy Global Configuration

Global configuration is kept for compatibility and personal defaults, but project or session context is recommended for concurrent agent workflows.

```bash
# Store in ~/.config/pt-snap-cli/config.json
pt-snap use /path/to/your/snapshot.db --global
```

#### Manage Legacy Global Configuration

```bash
# View global configuration
pt-snap config

# View global configuration file path
pt-snap config --path

# Clear global configuration
pt-snap config --clear
```

#### Context File Locations

Project context is saved at: `.pt-snap/context.json`

Legacy global configuration is saved at: `~/.config/pt-snap-cli/config.json`

Context content example:
```json
{
  "current_db_path": "/path/to/your/snapshot.db"
}
```

#### Error Handling

**Query without configured database:**

```bash
pt-snap query --template-use memory_summary_v2
# Error: No database path specified and no database configured.
# Use 'pt-snap use <database_path>' to set a project database, or provide db_path argument.
```

**Configured database file does not exist:**

If the resolved database file is deleted or moved, `pt-snap` reports the context source and leaves the context file unchanged:

```bash
pt-snap query --template-use memory_summary_v2
# Error: Database from project context not found: /path/to/missing.db
# Use 'pt-snap use <new_database_path>' to set a new project database, or provide db_path argument.
```

#### Complete Workflow Example

```bash
# 1. First use, set the project database
pt-snap use examples/snapshot_expandable.pkl.db

# 2. Then query directly without repeating path
pt-snap query --template-use memory_summary_v2
pt-snap query --template-use active_blocks_v2 --device 0
pt-snap query --template-use leak_detection_v2

# 3. View the effective context and source
pt-snap use

# 4. If this shell or agent needs a different database
export PT_SNAP_DB_PATH=/path/to/agent_snapshot.db

# 5. If the project should switch to another database
pt-snap use /path/to/new_snapshot.db

# 6. Clear legacy global configuration only
pt-snap config --clear
```

#### Advantages

1. **Improve Efficiency**: No need to enter full database path every query
2. **Reduce Errors**: Avoid query failures due to path input errors
3. **Concurrent Agent Safety**: Project context and `PT_SNAP_DB_PATH` avoid cross-process global state conflicts
4. **Flexible Override**: Explicit db paths and session env still override project defaults
5. **Transparent Context**: `pt-snap use` shows the effective database and where it came from

### Execute Queries

Use the `query` command to perform memory analysis queries:

```bash
pt-snap query [--template-use <template_name>] [--params <json>] [--device <id>] [--list] [--template-info <template>]
```

**Parameters:**
- `db_path`: SQLite database file path (optional if configured)
- `--template-use`: Query template name (required unless using --list or --template-info)
- `--params`: Query parameters in JSON format (optional)
- `--device`: Device ID (optional)
- `--list`: List available query templates
- `--template-info <template>`: Show detailed information about a specific template (parameters and output schema)

**Examples:**

List all available query templates:
```bash
pt-snap query --list
```

Query using template (leak detection):
```bash
pt-snap query --template-use leak_detection_v2 --params '{"min_size": 1024}'
```

Query specific device:
```bash
pt-snap query --template-use active_blocks_v2 --device 0
```

View template details:
```bash
pt-snap query --template-info leak_detection_v2
```

### Query Module Usage

The Query module provides powerful memory snapshot query functionality with template-based queries and parameterized configuration.

#### Available Query Templates

1. **leak_detection_v2** - Memory Leak Detection
   
   Detects memory allocations without free events.
   
   ```bash
   pt-snap query --template-use leak_detection_v2 --params '{"min_size": 1024}'
   ```
   
   Parameters:
   - `min_size`: Minimum leak size (bytes), default 1024
   - `device_id`: Device ID

2. **callstack_analysis_v2** - Callstack Analysis
   
   Analyzes callstack information for memory allocations.
   
   ```bash
   pt-snap query --template-use callstack_analysis_v2
   ```

3. **memory_timeline_v2** - Memory Timeline
   
   Shows timeline information for memory allocations.
   
   ```bash
   pt-snap query --template-use memory_timeline_v2
   ```

4. **active_blocks_v2** - Active Memory Blocks
   
   View currently active memory blocks.
   
   ```bash
   pt-snap query --template-use active_blocks_v2
   ```

5. **memory_summary_v2** - Memory Summary
   
   Display memory usage statistics summary.
   
   ```bash
   pt-snap query --template-use memory_summary_v2
   ```

6. **blocks_by_size_v2** - Blocks by Size
   
   Display memory blocks sorted by allocation size.
   
   ```bash
   pt-snap query --template-use blocks_by_size_v2
   ```

7. **events_by_action_v2** - Events by Action
   
   Display events grouped by action type.
   
   ```bash
   pt-snap query --template-use events_by_action_v2
   ```

#### Query Output

Query results are displayed in list format:
- Shows first 10 results
- If more than 10 results, shows remaining count

Example output:
```
Found 150 results:
  {'id': 1, 'address': '0x1000', 'size': 2048, ...}
  {'id': 2, 'address': '0x2000', 'size': 4096, ...}
  ...
  ... and 140 more
```

#### Advanced Usage

**Using ResultMapper for Custom Result Mapping:**

```python
from pt_snap_cli.query.mapper import ResultMapper, map_result, map_results

# Create mapper
mapper = ResultMapper()

# Register custom type converter
mapper.register_type_converter("custom", lambda x: f"custom_{x}")

# Register model factory
mapper.register_model_factory("MyModel", lambda d: MyModel(d))

# Map single row result
row = {"id": "1", "size": "1024"}
schema = [
    {"column": "id", "type": "int"},
    {"column": "size", "type": "int"},
]
result = mapper.map(row, schema)

# Map all results
results = mapper.map_all(rows, schema)

# Map to model object
model = mapper.map_to_model(row, "MyModel")
models = mapper.map_all_to_model(rows, "MyModel")
```

**Using Convenience Functions:**

```python
from pt_snap_cli.query.mapper import map_result, map_results

# Map single result
mapped = map_result(row, schema)

# Map multiple results
mapped_all = map_results(rows, schema)
```

#### Query Architecture

Query templates are defined in YAML format, including:
- `version`: Template version
- `queries`: Query definitions
  - `description`: Query description
  - `devices`: List of supported devices
  - `parameters`: Parameter definitions (type, default value, required)
  - `query`: SQL query statement (supports Jinja2 template syntax)
  - `output_schema`: Output schema definition (column names and types)

Supported type converters:
- `int`: Integer
- `float`: Float
- `str`: String
- `bool`: Boolean
- `hex`: Hexadecimal (integer to hex string)
- `datetime`: Datetime

## Project Structure

```
pt-snap-cli/
├── pt_snap_cli/
│   ├── cli.py              # CLI entry point
│   ├── context.py          # Context management
│   ├── query/
│   │   ├── builder.py      # Query builder
│   │   ├── executor.py     # Query executor
│   │   ├── mapper.py       # Result mapper
│   │   ├── registry.py     # Query registry
│   │   ├── condition.py    # Query conditions
│   │   ├── config.py       # Query configuration
│   │   └── templates/      # Query templates
│   └── models/             # Data models
├── tests/                  # Test files
├── examples/               # Example data
└── docs/                   # Documentation
```

## Development

Run tests:
```bash
pytest
```

## Version

Current version: See [pyproject.toml](pyproject.toml)
