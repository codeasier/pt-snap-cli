# Query Engine and SQL Tests

Parent scope: [test contracts](../AGENTS.md).
Implementation: [query engine](../../src/pt_snap_cli/query/AGENTS.md).

## Choose the Evidence Layer

| Tests | Scope |
| --- | --- |
| `test_builder.py`, `test_condition.py`, `test_mapper.py` | SQL/parameter generation, composable conditions, result conversion/model factories |
| `test_config.py`, `test_registry.py` | YAML contracts, parameter choices, catalog discovery/reset and categories |
| `test_executor.py` | Rendering, injected tables, error normalization and executor unit behavior |
| `test_memory_peak_cte.py`, `test_peak_memory_templates.py` | Peak/active-at-event/gap/attribution semantics |
| `test_callstack_schema_compat.py` | v1/v2 detection, conflicts, missing attribution and matching SQL results |
| `test_query_max_rows_pushdown.py` | Packaged templates against SQLite, outer cap pushdown and ordering |
| `test_query_completeness.py` | Extra-row probes, inner ranked windows, exact totals, stable pagination and timeout |
| `test_template_semantics.py` | Field interpretation metadata, serialization and unannotated compatibility |
| `test_leak_fallback_templates.py` | Preexisting/freed-lifetime queries replacing raw-SQL skill fallbacks |

Use small explicit SQLite schemas for semantic tests. Mocked rendering proves
syntax selection but not actual joins, grouping, limits, sentinels or percentages.
For attribution changes, cover both layouts and missing-data groups before ranking;
do not assert identity by display text alone.

Registry tests must restore singleton state. Close SQLite and cached service
resources using the parent test rules. Pagination assertions need ordering ties,
empty/full pages, inner `top_n` caps and completeness flags, rather than only row
counts. Timeout tests should demonstrate subsequent connection reuse too.

Run `pytest tests/query` from the repository root. Public metadata or query-result
changes additionally affect `tests/core/test_query_service.py`,
`tests/test_contract_cli_api.py`, and CLI/JSON cases. Skill instructions relying
on the changed query need the corresponding `tests/skills/` contracts.
