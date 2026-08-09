<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-26 | Updated: 2026-08-08 -->

# pt_snap_cli

## Purpose
`pt_snap_cli` is the main Python package. It exposes the Typer CLI, programmatic `SnapshotAnalyzer` API, read-only SQLite context, focus configuration, product service layer, MCP server, domain models, YAML-driven query execution pipeline, and first-party snapshot runtime.

## Key Files
| File | Description |
|------|-------------|
| `__init__.py` | Package exports and version wiring. |
| `api.py` | High-level `SnapshotAnalyzer` API used by MCP and library callers. |
| `cli.py` | Typer CLI entrypoint for focus, import, split, metadata, query, report, and config commands. |
| `completion.py` | Shell completion helpers for templates, categories, and device IDs. |
| `config.py` | Atomic focus persistence and resolution across explicit paths, environment, project focus, and legacy global config. |
| `context.py` | Read-only SQLite context with schema validation and device discovery. |
| `version.py` | Package version constant. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `core/` | Shared focus, import, split, metadata, query, and report services (see `core/AGENTS.md`). |
| `mcp/` | FastMCP server entrypoint and tools (see `mcp/AGENTS.md`). |
| `models/` | Domain models for snapshot blocks, events, and enums (see `models/AGENTS.md`). |
| `query/` | Query builders, config loading, execution, mapping, registry, and templates (see `query/AGENTS.md`). |
| `snapshot/` | Snapshot representation, replay, database adaptors, and slicing for explicitly trusted inputs (see `snapshot/AGENTS.md`). |

## For AI Agents

### Working In This Directory
- Route user-facing command logic through `core` services when practical so CLI, API, and MCP behavior remain aligned.
- Preserve focus precedence: explicit CLI/API path, `PT_SNAP_DB_PATH`, nearest project `.pt-snap/focus.json`, then legacy global config.
- Keep SQLite access read-only for analysis paths.

### Testing Requirements
- CLI changes should update/run `tests/test_cli.py` and any affected config/focus tests.
- API or MCP changes should update/run `tests/test_api.py`, `tests/test_mcp_server.py`, and `tests/test_contract_cli_mcp.py` when shared semantics change.
- Context or config changes should update/run `tests/test_context.py` and `tests/test_config.py`.
- Import, split, and report changes should run their focused `tests/core/` suites; add `tests/snapshot/` when import/split changes cross into the runtime.

### Common Patterns
- Exceptions from lower-level modules are translated into `core.errors` before reaching CLI/service callers; parameter validation errors become `TemplateRenderError`.
- Query template metadata shown to users comes from the registry/config pipeline, not hardcoded CLI text.

## Dependencies

### Internal
- `core/` coordinates focus and query behavior for CLI/API callers.
- `query/` provides template discovery and execution.
- `models/` contains library-facing snapshot structures.
- `snapshot/` provides pickle/JSON loading, replay, database generation, and slicing engines consumed through `core/`; callers own the trust decision.

### External
- `typer` for CLI commands and output.
- `sqlite3` standard library for database access.
- `mcp` for agent server integration.
- `jinja2` and `pyyaml` through the query subsystem.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
