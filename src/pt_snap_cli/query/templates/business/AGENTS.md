<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-26 | Updated: 2026-05-26 -->

# business templates

## Purpose
`business` contains higher-level analysis templates that package common memory investigation workflows into named queries.

## Key Files
| File | Description |
|------|-------------|
| `leak_detection.yaml` | Template for identifying potential memory leaks using allocation-size thresholds. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| None | Business templates are flat YAML files. |

## For AI Agents

### Working In This Directory
- Keep query names and descriptions understandable to CLI users rather than implementation-oriented.
- Validate that defaults are safe for broad snapshot exploration.

### Testing Requirements
- Run query registry/config/executor tests after changing templates.
- Run docs/CLI checks if user-facing metadata changes.

### Common Patterns
- Templates may expose business-level parameters such as minimum allocation size.

## Dependencies

### Internal
- Consumed by query registry, CLI template listing, API/MCP template tools, and `QueryExecutor`.

### External
- YAML plus Jinja2 template syntax inside SQL.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
