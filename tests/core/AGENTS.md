# Service Boundary Tests

Parent scope: [test contracts](../AGENTS.md).
Implementation: [core services](../../src/pt_snap_cli/core/AGENTS.md).

## Focused Test Map

| Files | Behavior under test |
| --- | --- |
| `test_focus_service.py` | Resolution, database/device validation, project/global persistence |
| `test_context_cache.py` | LRU eviction, replacement signatures, invalidation and close |
| `test_query_service.py` | Catalog/result contracts, focus/device selection, executor reuse and error normalization |
| `test_capability_service.py`, `test_overview_service.py` | Catalog and read-only device/event-bound/metadata probes |
| `test_report_service.py` | Named-query composition and report fields |
| `test_import_models.py`, `test_import_errors.py`, `test_import_metadata.py` | Import inputs, error context, metadata/cache/source identity |
| `test_import_service.py` | Staging, import reuse, source changes, publication/focus transaction |
| `test_import_backend_failures.py` | Backup short/zero writes, publication/focus/rollback faults, fd closure and recovery evidence |
| `test_split_service.py` | Strategy/device validation, formats, replay, cleanup, races and no-replace publication |
| `test_skill_service.py` | Catalog precedence, host/scope/custom destinations, status and mutation preflight |
| `test_json_codec.py` | Path/dataclass conversion and JSON envelopes |

## What to Assert

- Assert normalized service errors and stable result fields, not incidental
  lower-layer messages. Add CLI/API contract cases when a shared result changes.
- Publication fault injection must check the previous destination, focus file,
  temporary files and owned descriptors. A raised exception alone does not prove
  rollback. Rollback failure is a distinct path with recovery evidence.
- Split failure/race cases must prove no partially published directory and no
  replacement of an independently created destination.
- Skill mutation preflight must cover non-skill paths and all selected locations
  before deleting any copy; list status and host loading are separate concepts.
- Cache work also exercises `tests/test_analyzer_lifecycle.py`,
  `tests/test_snapshot_analyzer_cache.py`, and `tests/test_query_cache_perf.py`.
  Service reuse after close and analyzer terminal closure need separate cases.

Run `pytest tests/core` or the owning file from the repository root. Follow the
parent's fixture gate before import/split cases and resource ownership rules for
all cached services. Cross-runtime changes additionally use `tests/snapshot/`.
