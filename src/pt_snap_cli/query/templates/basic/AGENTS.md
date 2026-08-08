<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-26 | Updated: 2026-05-26 -->

# basic templates

## Purpose
`basic` contains core query templates for inspecting low-level allocation, block, and event records in a focused snapshot database.

## Key Files
| File | Description |
|------|-------------|
| `allocation.yaml` | Allocation-oriented query template. |
| `block.yaml` | Block inspection query template. |
| `event.yaml` | Event timeline/query template. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| None | Basic templates are flat YAML files. |

## For AI Agents

### Working In This Directory
- Keep templates narrowly focused on direct snapshot inspection.
- Ensure parameter descriptions and output schemas match the SQL result columns.

### Testing Requirements
- Run query config/registry/executor tests after changing YAML.
- Run CLI template-info tests if metadata changes.

### Common Patterns
- Templates query device-specific trace or block tables using injected table names.

## Dependencies

### Internal
- Loaded by `pt_snap_cli.query.registry` and executed by `QueryExecutor`.

### External
- YAML plus Jinja2 template syntax inside SQL.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
