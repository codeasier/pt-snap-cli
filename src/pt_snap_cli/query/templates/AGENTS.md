<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-26 | Updated: 2026-05-26 -->

# templates

## Purpose
`templates` contains the packaged YAML query templates used by the registry and CLI/API/MCP query execution. Templates are grouped by category and define metadata, parameters, SQL, and output schemas.

## Key Files
| File | Description |
|------|-------------|
| None | Template YAML files are grouped in category subdirectories. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `basic/` | Core allocation/block/event inspection templates (see `basic/AGENTS.md`). |
| `business/` | Higher-level analysis templates such as leak detection (see `business/AGENTS.md`). |
| `statistical/` | Aggregation and statistical analysis templates (see `statistical/AGENTS.md`). |

## For AI Agents

### Working In This Directory
- Keep each YAML template's `queries` entry name aligned with the file/topic and documented template name.
- Include accurate parameter defaults, required flags, descriptions, and output schema entries.
- Use Jinja variables provided by `QueryExecutor`, especially device-specific table names.

### Testing Requirements
- Run `pytest tests/query/test_registry.py tests/query/test_config.py tests/query/test_executor.py` after template changes.
- Run `pytest tests/test_cli.py` if list or template-info output changes.

### Common Patterns
- Category is inferred from the subdirectory unless explicitly set in the YAML.
- SQL is rendered through Jinja2 before execution against SQLite.

## Dependencies

### Internal
- `pt_snap_cli.query.config.QueryConfig` parses template YAML.
- `pt_snap_cli.query.registry` discovers and registers packaged templates.
- `pt_snap_cli.query.executor.QueryExecutor` renders and executes template SQL.

### External
- YAML syntax via `pyyaml` and Jinja2 expressions inside SQL strings.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
