<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-26 | Updated: 2026-08-24 -->

# core

Parent scope: [pt_snap_cli package](../AGENTS.md)

## Purpose
`core` contains the product service layer shared by CLI, Python API, and MCP adapters. It owns focus, import publication and metadata, snapshot splitting, query orchestration, reports, stable result models, and domain-specific errors over lower-level config, context, query, and snapshot modules.

## Key Files
| File | Description |
|------|-------------|
| `__init__.py` | Re-exports service classes, models, and errors for package consumers. |
| `context_cache.py` | Bounded Context reuse with path identity, file-signature invalidation, and explicit close/invalidate behavior. |
| `errors.py` | Domain exception types used by CLI/API service boundaries. |
| `focus_service.py` | Focus resolution, validation, project/global focus writes, and device selection. |
| `import_service.py` | Failure-safe snapshot import, cache reuse, metadata writes, and optional focus update. |
| `import_metadata.py` | Import metadata schema, inspection, hashing, validation, and cache decisions. |
| `models.py` | Dataclasses for focus, import, split, template, query, and report service boundaries. |
| `query_service.py` | Template listing/info and query execution orchestration using resolved focus and `QueryExecutor`. |
| `report_service.py` | Higher-level reports composed from shared query services. |
| `snapshot_import_backend.py` | Adapter from trusted snapshot runtime replay to staged SnapshotDB output. |
| `split_service.py` | Argument/device validation, replay-safe slicing, staging cleanup, and exclusive publication. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| None | Service-layer modules are flat. |

## For AI Agents

### Working In This Directory
- Translate low-level exceptions into `core.errors` so CLI and API callers receive consistent failures.
- Preserve explicit device precedence over focused device, and validate devices against `Context.device_ids`.
- Keep service models stable when changing CLI/API/MCP output shapes.
- Preserve existing import destinations when publication or the requested focus update fails, and never replace an existing split destination.

### Testing Requirements
- Run `pytest tests/core` for service changes; import tests isolate CWD, environment focus, and home before any default focus write.
- Also run CLI/API tests when service behavior changes user-visible output or errors.
- Run `pytest tests/snapshot` when import or split changes cross into the snapshot runtime.

### Common Patterns
- `FocusService` delegates persistence to `Config` and validation to `Context`.
- `QueryService` resolves focus, chooses a target device, reuses a cached context/executor, executes a named template, and applies row limiting.
- `ImportService` validates a temporary database, publishes it with a retained rollback link, and commits requested focus before releasing that link. `SplitService` validates staged slices before a no-replace directory publish.
- `ReportService` composes named query results instead of reimplementing SQL.

### Change Together
- Context cache changes require `tests/core/test_context_cache.py`, `tests/test_snapshot_analyzer_cache.py`, and `tests/test_query_cache_perf.py`.
- Import publication or focus transaction changes require `tests/core/test_import_service.py` and `tests/test_config.py`.

## Dependencies

### Internal
- `pt_snap_cli.config` for focus persistence and precedence.
- `pt_snap_cli.context` for database validation and device discovery.
- `pt_snap_cli.query` for template registry and SQL execution.
- `pt_snap_cli.snapshot` for trusted representation loading, replay, database adaptation, and slicing.

### External
- `sqlite3` standard library exceptions are normalized at service boundaries.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
