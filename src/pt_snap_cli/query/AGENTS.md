<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-26 | Updated: 2026-08-09 -->

# query

## Purpose
`query` implements the template-driven query subsystem. It loads YAML query definitions, validates template parameters, renders device-specific SQL with Jinja2, executes queries through the read-only database context, maps result types, and provides fluent builder utilities for constructing SQL programmatically.

## Key Files
| File | Description |
|------|-------------|
| `__init__.py` | Query package marker/exports. |
| `builder.py` | Fluent `QueryBuilder` for SELECT statements with conditions, grouping, ordering, limits, and offsets. |
| `condition.py` | Composable SQL condition objects that emit parameterized SQL fragments. |
| `config.py` | YAML query config loader and `QueryTemplate`/`QueryParameter` validation. |
| `executor.py` | Jinja2 SQL rendering and query execution through `Context`. |
| `mapper.py` | Result type conversion and optional model-factory mapping. |
| `registry.py` | Singleton registry that loads packaged YAML templates and exposes listing/lookup helpers. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `templates/` | Built-in YAML query templates grouped by category (see `templates/AGENTS.md`). |

## For AI Agents

### Working In This Directory
- When changing template behavior, check YAML templates, `config.py`, `registry.py`, `executor.py`, and CLI template metadata output together.
- Keep SQL value filters parameterized where using builder/condition APIs.
- Device-specific template SQL should use injected table names such as `device_trace_table` and `device_block_table`.
- Keep direct `QueryParameter` validation errors local; `QueryExecutor` must normalize them to its `TemplateRenderError` before the core boundary.
- `QueryTemplate.validate_params()` rejects undeclared parameter names and enforces `QueryParameter.choices`; extra render-context variables (`device_id`, table names, the pushed-down `limit`) are injected by `QueryExecutor.render()` after validation, not passed through `params`.

### Testing Requirements
- Run `pytest tests/query` for query subsystem changes; real SQLite template semantics live in `test_peak_memory_templates.py` and `test_query_max_rows_pushdown.py`.
- Run `pytest tests/test_cli.py` when template listing/info/output behavior changes.

### Common Patterns
- Registry lookup is global and package templates load at import time.
- `StrictUndefined` is used during template rendering so missing template variables fail loudly.
- Template categories are inferred from directory structure when not explicitly declared in YAML.
- `QueryService` translates executor errors to `core.errors` and owns cached Context/QueryExecutor reuse.

## Dependencies

### Internal
- `pt_snap_cli.context.Context` provides database connections and device discovery.
- `src/pt_snap_cli/query/templates/` provides built-in templates.
- `core.query_service` consumes registry and executor APIs.

### External
- `pyyaml` for YAML parsing.
- `jinja2` for SQL template rendering.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
