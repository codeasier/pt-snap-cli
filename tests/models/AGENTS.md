<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-26 | Updated: 2026-05-26 -->

# model tests

## Purpose
`tests/models` verifies snapshot domain models and enum definitions exposed from `src/pt_snap_cli/models`.

## Key Files
| File | Description |
|------|-------------|
| `__init__.py` | Test package marker. |
| `test_block.py` | Block model tests. |
| `test_enums.py` | Enum value and behavior tests. |
| `test_event.py` | Event model tests. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| None | Model tests are flat. |

## For AI Agents

### Working In This Directory
- Keep tests aligned with public model exports and expected snapshot semantics.
- Add enum coverage when introducing or renaming model enum values.

### Testing Requirements
- Run `pytest tests/models` for model changes.

### Common Patterns
- Tests focus on object construction, field behavior, and enum correctness.

## Dependencies

### Internal
- `src/pt_snap_cli/models/` is the primary code under test.

### External
- `pytest`.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
