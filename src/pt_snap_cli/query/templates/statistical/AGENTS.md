<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-26 | Updated: 2026-05-26 -->

# statistical templates

## Purpose
`statistical` contains aggregation-oriented query templates for summarizing memory peaks, callstack behavior, and other statistical views of snapshot data.

## Key Files
| File | Description |
|------|-------------|
| `callstack_analysis.yaml` | Template for grouping or analyzing memory behavior by callstack. |
| `memory_peak.yaml` | Template for identifying peak memory usage. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| None | Statistical templates are flat YAML files. |

## For AI Agents

### Working In This Directory
- Keep aggregation result columns documented in each template's output schema.
- Be careful with SQL grouping and ordering so CLI output remains deterministic.

### Testing Requirements
- Run query executor and registry tests after changing templates.
- Add fixture coverage when introducing new aggregation assumptions.

### Common Patterns
- Templates summarize many low-level records into ranked or grouped result rows.

## Dependencies

### Internal
- Consumed by query registry, CLI/API/MCP template metadata, and `QueryExecutor`.

### External
- YAML plus Jinja2 template syntax inside SQL.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
