<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-26 | Updated: 2026-08-08 -->

# core tests

## Purpose
`tests/core` verifies focus, import, split, metadata, query, and report services between CLI/API/MCP callers and lower-level config, context, query, and snapshot modules.

## Key Files
| File | Description |
|------|-------------|
| `test_focus_service.py` | Tests focus service resolution, validation, project/global writes, and device handling. |
| `test_context_cache.py` | Tests bounded Context reuse, invalidation, close behavior, and file replacement detection. |
| `test_import_*.py` | Tests import models/errors, metadata/cache decisions, safe publication, reuse, and failure handling. |
| `test_query_service.py` | Tests query service template listing/info, focus resolution, execution, row limiting, and error translation. |
| `test_report_service.py` | Tests higher-level report composition and normalized results. |
| `test_split_service.py` | Tests split contracts, devices, formats, replay validation, cleanup, races, and publication. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| None | Service tests are flat. |

## For AI Agents

### Working In This Directory
- Update these tests when `src/pt_snap_cli/core/` behavior changes.
- Assert service-level errors rather than low-level implementation exceptions.

### Testing Requirements
- Run `pytest tests/core` for service-layer changes.
- Run `pytest tests/test_fixture_provenance.py` first when selected import/split tests deserialize committed fixtures.

### Common Patterns
- Focus-writing tests isolate CWD, `PT_SNAP_DB_PATH`, and home from persistent user config.
- Import and split tests assert that failures do not replace existing destinations or publish partial output.
- Import publication tests cover focus-write rollback as part of the reported import transaction.

## Dependencies

### Internal
- `src/pt_snap_cli/core/` is the primary code under test.

### External
- `pytest`.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
