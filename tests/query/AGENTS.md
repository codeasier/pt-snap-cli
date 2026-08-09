<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-26 | Updated: 2026-08-08 -->

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
| `test_executor.py` | Tests Jinja rendering, parameter-error normalization, limits, output validation, and mocked executor behavior. |
| `test_memory_peak_cte.py` | Tests generated memory-peak SQL CTE structure and semantics. |
| `test_mapper.py` | Tests result type conversion and model factory mapping. |
| `test_peak_memory_templates.py` | Tests active-at-event, allocator-gap, and callstack attribution template semantics. |
| `test_query_max_rows_pushdown.py` | Executes packaged leak/callstack templates against SQLite and tests SQL limit pushdown and stable ordering. |
| `test_registry.py` | Tests template registration, lookup, category listing, and registry reset behavior. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| None | Query tests are flat. |

## For AI Agents

### Working In This Directory
- Add coverage in the most specific test file for any query subsystem change.
- Use minimal SQLite fixtures in the integration suites rather than external databases; `test_executor.py` is primarily render/unit coverage.

### Testing Requirements
- Run `pytest tests/query` for query subsystem changes.
- Run CLI tests too when changes affect user-visible template listing, metadata, or output.

### Common Patterns
- Registry tests reset singleton state to avoid cross-test contamination.
- Executor tests exercise rendered SQL and device-specific table names; packaged-template SQLite behavior lives in the dedicated integration files.

## Dependencies

### Internal
- `src/pt_snap_cli/query/` and packaged YAML templates are the primary code under test.
- Tests define minimal local SQLite fixtures for the query behavior they exercise.

### External
- `pytest`.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
