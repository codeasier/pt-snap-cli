# Packaged Query Contracts

Parent scope: [query engine](../AGENTS.md).

Each YAML `queries` entry is a public named contract: parameters, SQL, output
schema and optional interpretation metadata. Categories default to the directory
name. Package data includes category YAML files; deeper layout changes require
reviewing `pyproject.toml` rather than assuming recursive wheel inclusion.

## Template Families

| Directory | Responsibilities |
| --- | --- |
| `basic/` | Allocation, block and event inspection/pagination |
| `business/` | Leak candidates, preexisting live blocks, freed lifetimes, active-memory callstack attribution |
| `statistical/` | Peak metrics, active-at-event blocks, allocator gaps, callstack aggregates |

## Authoring Rules

- Declare every caller input, accurate defaults/required flags, and each result
  column in `output_schema`. Unannotated fields with only `column`/`type` stay valid.
- SQL identifier/keyword parameters such as `order_by` and `order_dir` require
  `choices`; ordering columns must exist in the output schema. Invalid choices
  definitions/defaults fail construction, and registry loading warns and skips
  the YAML file. Verify the template remains discoverable after editing.
- Use injected device table names. Keep grouped/ranked/paginated results
  deterministic with explicit tie-breakers. Do not invent offset support for
  templates that only expose a ranked window.
- Put inline-callstack v1 and ID-callstack v2 SQL under `query_variants` in one
  entry, sharing name, parameters, description and output schema. Unaffected
  queries retain a single `query`.
- Interpretation changes require reviewing `semantics_version` and field
  metadata, not bumping the database layout or YAML document version instead.

## Attribution Edge Cases

`active_memory_callstack_at_event` normalizes missing dynamic attribution
(empty/NULL text, NULL IDs, absent joined rows) before ranking into
`[missing callstack]`. Keep static and preexisting categories separate. Nonempty
v2 stacks retain ID grouping; whitespace and a captured literal missing-label
string are real data, not the missing group. Display labels are not unique group
identities. Preserve special groups and their totals when applying `top_n`.

## Change Together

Run the config, registry and executor tests for contracts/rendering:

```bash
pytest tests/query/test_registry.py tests/query/test_config.py tests/query/test_executor.py
```

Add the owning real-SQLite suite from [query tests](../../../../tests/query/AGENTS.md). In particular,
attribution requires v1/v2, mixed missing/nonmissing, ranking and denominator
cases. Review service/CLI/API metadata and both querying guides for any public
contract change; skills may depend on parameter names and completeness flags.
