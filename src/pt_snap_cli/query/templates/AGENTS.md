<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-26 | Updated: 2026-08-09 -->

# templates

## Purpose
`templates` contains the packaged YAML query templates used by the registry and CLI/API query execution. Templates are grouped by category and define metadata, parameters, SQL, and output schemas.

## Key Files
| File | Description |
|------|-------------|
| None | Template YAML files are grouped in category subdirectories. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `basic/` | Core allocation, block, and event inspection templates. |
| `business/` | Higher-level analysis templates such as leak detection. |
| `statistical/` | Point-in-time, aggregation, gap, callstack, and peak templates. |

## For AI Agents

### Working In This Directory
- Keep each YAML template's `queries` entry name aligned with the file/topic and documented template name.
- Include accurate parameter defaults, required flags, descriptions, and output schema entries.
- Any parameter rendered as a SQL identifier or keyword (`order_by`, `order_dir`, or similar) must declare `choices`; `order_by` choices must be columns present in `output_schema`. `tests/query/test_registry.py` enforces this for packaged templates. Empty `choices`, a non-list `choices`, or a default outside the list raise at `QueryParameter` construction; `_load_yaml_templates` warns and skips that YAML file, so the template is absent rather than listed.
- Callers cannot pass undeclared parameters; `QueryTemplate.validate_params()` rejects unknown names, so declare every input the SQL reads.
- Use Jinja variables provided by `QueryExecutor`, especially device-specific table names.
- Make ranked/grouped results deterministic with explicit tie-breakers and keep every selected result column in `output_schema`.

### Testing Requirements
- Run `pytest tests/query/test_registry.py tests/query/test_config.py tests/query/test_executor.py` after metadata/rendering changes; add the owning SQLite integration suite for SQL semantics.
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

- For callstack-dependent templates, put v1 inline SQL and v2 `callstackId` SQL
  under `query_variants` instead of duplicating the template file. Keep the
  public name, parameters, and `output_schema` identical.
