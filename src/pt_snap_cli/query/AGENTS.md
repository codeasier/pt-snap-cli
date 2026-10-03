# Query Engine

Parent scope: [package runtime](../AGENTS.md).

## Data Flow and Ownership

`templates/<category>/*.yaml` → `config.py` → `registry.py` →
`core/query_service.py` → `executor.py`/`Context` → mapped rows and adapter output.
The [template guide](templates/AGENTS.md) owns SQL/metadata authoring rules.

| Module | Boundary |
| --- | --- |
| `config.py` | QueryConfig/QueryTemplate/QueryParameter parsing and parameter validation |
| `registry.py` | Singleton catalog, recursive packaged YAML discovery, category/name lookup |
| `executor.py` | Variant selection, StrictUndefined Jinja rendering, row-limit pushdown, SQLite execution/timeout |
| `mapper.py` | Result conversions and optional registered model factories |
| `builder.py`, `condition.py` | Fluent SQL construction with parameterized value conditions |

## Registration and Rendering

- Packaged templates load through the registry at import time. Executors have no
  template directory: `_configs` contains only runtime `load_config()` /
  `register_template()` registrations, which override same-named catalog entries.
- Validate caller parameters before injecting `device_id`, device table names
  and a pushed-down `limit`. Undeclared names and invalid choices must fail;
  internal render variables are not permission to accept arbitrary user params.
- Parameter validation errors become executor `TemplateRenderError`, then core
  domain errors at the service boundary. Preserve actionable layout/timeout
  errors instead of replacing every failure with generic re-import guidance.
- Compiled Jinja caching includes template name and SQL body. v1/v2 variants
  cannot share a compiled body accidentally. `StrictUndefined` remains enabled.

## Layout, Semantics and Completeness

Select `query_variants.v1`/`v2` from `Context.callstack_layout`; non-variant queries
continue to work when layout is unset. The context only detects layout; queries
must not migrate it. v2 aggregates nonempty callstacks by ID, not display text.

Field metadata (`units`, `metric_semantics`, `scope`, `denominator`, `sentinel`,
`interpretation_limits`) and template `semantics_version` use the same
config → registry → core → CLI/API path as parameter `choices`. Do not introduce
a parallel metadata schema. YAML version, semantics version and database layout
are different contracts.

Trailing `LIMIT`, inner ranking `top_n`, output `max_rows`, and execution timeout
are distinct. Tightening a trailing limit must preserve offset and stable order;
`-n` cannot lift a CTE's `top_n`. The service owns extra-row probes, conservative
inner-window completeness and exact-total budgeting. The executor's SQLite
progress handler must be cleared even on failure, especially with cached Contexts.

## Verification

Run `pytest tests/query` from the repository root; use the
[query test map](../../../tests/query/AGENTS.md) for narrower changes. Rendering
tests alone do not verify SQLite semantics. Changes to contracts/listing also
need `tests/core/test_query_service.py`, `tests/test_contract_cli_api.py`, and
the affected CLI/JSON cases.
