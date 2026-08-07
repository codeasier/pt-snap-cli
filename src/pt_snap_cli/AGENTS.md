<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-26 | Updated: 2026-05-26 -->

# pt_snap_cli

## Purpose
`pt_snap_cli` is the main Python package. It exposes the Typer CLI, programmatic `SnapshotAnalyzer` API, read-only SQLite context, focus configuration, completion helpers, service layer, MCP server, domain models, and YAML-driven query execution pipeline.

## Key Files
| File | Description |
|------|-------------|
| `__init__.py` | Package exports and version wiring. |
| `api.py` | High-level `SnapshotAnalyzer` API used by MCP and library callers. |
| `cli.py` | Typer CLI entrypoint for `pt-snap focus`, `pt-snap query`, and `pt-snap config`. |
| `completion.py` | Shell completion helpers for templates, categories, and device IDs. |
| `config.py` | Focus persistence and resolution across explicit paths, environment, project focus, and legacy global config. |
| `context.py` | Read-only SQLite context with schema validation and device discovery. |
| `version.py` | Package version constant. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `core/` | Service-layer models and typed domain errors (see `core/AGENTS.md`). |
| `mcp/` | FastMCP server entrypoint and tools (see `mcp/AGENTS.md`). |
| `models/` | Domain models for snapshot blocks, events, and enums (see `models/AGENTS.md`). |
| `query/` | Query builders, config loading, execution, mapping, registry, and templates (see `query/AGENTS.md`). |

## For AI Agents

### Working In This Directory
- Route user-facing command logic through `core` services when practical so CLI, API, and MCP behavior remain aligned.
- Preserve focus precedence: explicit CLI/API path, `PT_SNAP_DB_PATH`, nearest project `.pt-snap/focus.json`, then legacy global config.
- Keep SQLite access read-only for analysis paths.

### Testing Requirements
- CLI changes should update/run `tests/test_cli.py` and any affected config/focus tests.
- API or MCP changes should update/run `tests/test_api.py` and `tests/test_mcp_server.py`.
- Context or config changes should update/run `tests/test_context.py` and `tests/test_config.py`.

### Common Patterns
- Exceptions from lower-level modules are translated into `core.errors` before reaching CLI/service callers.
- Query template metadata shown to users comes from the registry/config pipeline, not hardcoded CLI text.

## Dependencies

### Internal
- `core/` coordinates focus and query behavior for CLI/API callers.
- `query/` provides template discovery and execution.
- `models/` contains library-facing snapshot structures.

### External
- `typer` for CLI commands and output.
- `sqlite3` standard library for database access.
- `mcp` for agent server integration.
- `jinja2` and `pyyaml` through the query subsystem.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
