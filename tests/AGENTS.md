<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-26 | Updated: 2026-05-26 -->

# tests

## Purpose
`tests` contains the pytest suite for CLI commands, configuration and focus resolution, SQLite context validation, MCP server tools, public API behavior, domain models, and query subsystem components. Tests use temporary SQLite fixtures to avoid dependence on local snapshot files.

## Key Files
| File | Description |
|------|-------------|
| `conftest.py` | Shared pytest fixtures, including temporary snapshot database setup. |
| `run_tests.sh` | Convenience script for running the test suite with coverage. |
| `test_api.py` | Tests for the public `SnapshotAnalyzer` API layer. |
| `test_cli.py` | CLI behavior tests, including focus, query listing, template info, and output limits. |
| `test_completion.py` | Shell completion helper tests. |
| `test_config.py` | Configuration and focus precedence tests. |
| `test_context.py` | SQLite context, schema validation, and device discovery tests. |
| `test_mcp_server.py` | MCP server tool/resource/prompt behavior tests. |
| `test_models.py` | Package-level model behavior tests. |
| `test_package.py` | Package metadata/import/version tests. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `core/` | Service-layer tests for focus and query orchestration (see `core/AGENTS.md`). |
| `models/` | Domain model and enum tests (see `models/AGENTS.md`). |
| `query/` | Query builder, config, executor, mapper, registry, and condition tests (see `query/AGENTS.md`). |

## For AI Agents

### Working In This Directory
- Add or update focused tests with behavior changes; `tests/test_cli.py` is the first place to check for user-facing command behavior.
- Use temporary directories and SQLite fixtures instead of relying on local `.pt-snap/focus.json` or real snapshot databases.
- Keep tests deterministic across working directories and user machines.

### Testing Requirements
- Run `conda run -n cc pytest` for the full suite when available.
- Use targeted commands such as `pytest tests/query/test_executor.py` for narrow query changes.

### Common Patterns
- CLI tests exercise Typer commands through test runners and assert printed output.
- Query tests build minimal SQLite schemas and YAML-like config objects around the template pipeline.

## Dependencies

### Internal
- Tests import `pt_snap_cli` package modules from `src/` via editable install or test environment path configuration.

### External
- `pytest` is the test runner.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
