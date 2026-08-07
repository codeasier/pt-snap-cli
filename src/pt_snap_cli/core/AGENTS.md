<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-26 | Updated: 2026-05-26 -->

# core

## Purpose
`core` contains the service layer shared by the CLI and public API. It wraps lower-level config, context, and query modules with stable typed models and domain-specific exceptions for focus management and query execution.

## Key Files
| File | Description |
|------|-------------|
| `__init__.py` | Re-exports service classes, models, and errors for package consumers. |
| `errors.py` | Domain exception types used by CLI/API service boundaries. |
| `focus_service.py` | Focus resolution, validation, project/global focus writes, and device selection. |
| `models.py` | Dataclasses for focus state, resolved focus, template metadata, and query results. |
| `query_service.py` | Template listing/info and query execution orchestration using resolved focus and `QueryExecutor`. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| None | Service-layer modules are flat. |

## For AI Agents

### Working In This Directory
- Translate low-level exceptions into `core.errors` so CLI and API callers receive consistent failures.
- Preserve explicit device precedence over focused device, and validate devices against `Context.device_ids`.
- Keep service models stable when changing CLI/API/MCP output shapes.

### Testing Requirements
- Run `pytest tests/core` for service changes.
- Also run CLI/API tests when service behavior changes user-visible output or errors.

### Common Patterns
- `FocusService` delegates persistence to `Config` and validation to `Context`.
- `QueryService` resolves focus, chooses a target device, executes a named template, and applies row limiting.

## Dependencies

### Internal
- `pt_snap_cli.config` for focus persistence and precedence.
- `pt_snap_cli.context` for database validation and device discovery.
- `pt_snap_cli.query` for template registry and SQL execution.

### External
- `sqlite3` standard library exceptions are normalized at service boundaries.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
