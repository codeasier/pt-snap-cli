# Package Runtime and Adapters

Parent scope: [source/distribution](../AGENTS.md).

## Ownership Map

| Entry | Responsibility | Focused tests from repository root |
| --- | --- | --- |
| `cli.py` | Root Typer app, root commands, group registration, `_safe_call` parse/error boundary | `tests/test_cli.py`, `tests/test_cli_json.py` |
| `cli_reports.py`, `cli_skills.py` | `report_app` / `skill_app` registered by `cli.py` | Report/skill cases in `tests/test_cli.py` |
| `cli_output.py` | JSON-mode callback/state, errors, terminal renderers shared across command modules | `tests/test_cli_json.py` |
| `api.py` | `SnapshotAnalyzer`, session focus, typed query payloads, capabilities/overview/metadata | `tests/test_api.py`, `tests/test_contract_cli_api.py`, `tests/test_analyzer_lifecycle.py` |
| `config.py` | Focus precedence and atomic project/global JSON persistence | `tests/test_config.py` |
| `context.py` | Connection ownership, dictionary validation, device and callstack-layout discovery | `tests/test_context.py`, `tests/query/test_callstack_schema_compat.py` |
| `completion.py` | Read-only template/category/skill/device completion with connection cleanup | `tests/test_completion.py` |
| `version.py`, `__init__.py` | Distribution version lookup and public exports | `tests/test_package.py` |

## Subsystems

- [Core](core/AGENTS.md): service contracts, cache ownership, import/split
  transactions, reports, skill catalog/destinations.
- [Query](query/AGENTS.md): registry/config/executor/mapper and YAML contracts.
- [Snapshot](snapshot/AGENTS.md): first-party representation/replay/storage/slices.
- [Models](models/AGENTS.md): library dataclasses/enums, distinct from runtime
  entities and core result payloads.
- `bundled_skills/`: wheel resources governed by the authoring
  [skills guide](../../skills/AGENTS.md), not a separate skill implementation.

## Adapter Contracts

- Keep root and group commands on the same `cli_output.py` JSON/error path.
  Preserve `_safe_call` handling for argument parsing as well as domain errors;
  successful service calls are not enough to validate JSON mode.
- Adapters may format or translate public errors, but service behavior belongs
  in core. Use existing serializers in `core/json_codec.py` and
  `core/query_service.py` instead of constructing a second template schema.
- `SnapshotAnalyzer.set_focus()` changes validated session state; CLI focus
  persistence goes through `FocusService`/`Config`. Preserve their normalized
  shared behavior without making the API write project focus implicitly.
- Analyzer `close()` is idempotent and terminal for operations; subsequent
  operations raise `RuntimeError("SnapshotAnalyzer is closed.")`. Cache access
  and explicit invalidation remain available for cleanup. An injected cache
  stays caller-owned. Pair lifecycle changes with the cache suites in
  [core tests](../../tests/core/AGENTS.md).
- Preserve `TemplateSummaryPayload` and `QueryResultPayload` boundaries and the
  file-level type gates; dynamic query cell values are `object`, not `Any`.

## Context and Layout

`Context` normally closes on exit from its outermost `connect()` scope;
`persistent=True` keeps the connection for an explicit owner. Constructor
validation failures must close even persistent connections.

Layout detection inspects trace columns and the shared callstack table, with
`pt_snap_metadata` as an auxiliary consistency check. `v1` uses inline text;
`v2` uses `callstackId`. Conflicts leave `callstack_layout=None` and expose
`callstack_layout_error`; they do not reject an otherwise valid dictionary-based
Context. The executor rejects only queries requiring an unavailable variant.
Layout must not be persisted to focus or repaired by analysis-time writes.
