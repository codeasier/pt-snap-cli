<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-26 | Updated: 2026-05-26 -->

# models

## Purpose
`models` contains library-facing domain objects for PyTorch memory snapshot data, including allocation blocks, events, and enum values that describe allocator state and event types.

## Key Files
| File | Description |
|------|-------------|
| `__init__.py` | Public model exports. |
| `_enums.py` | Enum definitions for snapshot concepts. |
| `block.py` | Block-related data model. |
| `event.py` | Event-related data model. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| None | Domain models are flat. |

## For AI Agents

### Working In This Directory
- Keep model fields aligned with the snapshot schema and query output mapping expectations.
- Update exports in `__init__.py` when adding public models.

### Testing Requirements
- Run `pytest tests/models` and any package-level model tests after changing models or enums.

### Common Patterns
- Models are used by library-facing code more than the CLI, which usually prints plain dictionaries from query execution.

## Dependencies

### Internal
- Query result mapping may depend on model-compatible types and enum values.

### External
- Standard Python dataclass/enum-style modeling; no heavy external model framework is used here.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
