<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-26 | Updated: 2026-05-26 -->

# query tests

## Purpose
`tests/query` verifies the query subsystem: fluent SQL building, condition composition, YAML config loading, Jinja2 rendering, SQLite execution, result mapping, and registry behavior.

## Key Files
| File | Description |
|------|-------------|
| `__init__.py` | Test package marker. |
| `test_builder.py` | Tests `QueryBuilder` SQL and parameter generation. |
| `test_condition.py` | Tests condition objects and composite boolean conditions. |
| `test_config.py` | Tests YAML loading and query parameter validation. |
| `test_executor.py` | Tests template rendering and execution against SQLite fixtures. |
| `test_mapper.py` | Tests result type conversion and model factory mapping. |
| `test_registry.py` | Tests template registration, lookup, category listing, and registry reset behavior. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| None | Query tests are flat. |

## For AI Agents

### Working In This Directory
- Add coverage in the most specific test file for any query subsystem change.
- Use minimal SQLite fixtures for executor tests rather than external databases.

### Testing Requirements
- Run `pytest tests/query` for query subsystem changes.
- Run CLI tests too when changes affect user-visible template listing, metadata, or output.

### Common Patterns
- Registry tests reset singleton state to avoid cross-test contamination.
- Executor tests exercise rendered SQL and device-specific table names.

## Dependencies

### Internal
- `src/pt_snap_cli/query/` and packaged YAML templates are the primary code under test.
- Shared database fixtures may come from `tests/conftest.py`.

### External
- `pytest`.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
