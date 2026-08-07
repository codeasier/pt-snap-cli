<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-26 | Updated: 2026-05-26 -->

# core tests

## Purpose
`tests/core` verifies the service layer that sits between CLI/API/MCP callers and lower-level config, context, and query modules.

## Key Files
| File | Description |
|------|-------------|
| `test_focus_service.py` | Tests focus service resolution, validation, project/global writes, and device handling. |
| `test_query_service.py` | Tests query service template listing/info, focus resolution, execution, row limiting, and error translation. |

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

### Common Patterns
- Tests isolate focus/query services from persistent user config and use temporary fixtures.

## Dependencies

### Internal
- `src/pt_snap_cli/core/` is the primary code under test.
- Shared fixtures may come from `tests/conftest.py`.

### External
- `pytest`.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
