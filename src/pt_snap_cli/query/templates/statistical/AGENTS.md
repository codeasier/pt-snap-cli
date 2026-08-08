<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-26 | Updated: 2026-08-08 -->

# statistical templates

## Purpose
`statistical` contains point-in-time and aggregation templates for active blocks, allocator gaps, callstack behavior, and memory peaks.

## Key Files
| File | Description |
|------|-------------|
| `active_blocks_at_event.yaml` | Return blocks active at a selected event, optionally including static allocations. |
| `allocator_gap.yaml` | Compare allocated, active, and reserved peak events and same-event gaps. |
| `callstack_analysis.yaml` | Template for grouping or analyzing memory behavior by callstack. |
| `memory_peak.yaml` | Template for identifying peak memory usage. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| None | Statistical templates are flat YAML files. |

## For AI Agents

### Working In This Directory
- Keep each template's result columns documented in its output schema.
- Preserve deterministic ordering for both point-in-time rows and grouped/ranked output.

### Testing Requirements
- Run query executor and registry tests after changing templates.
- Add fixture coverage when introducing new aggregation assumptions.

### Common Patterns
- Templates either select block state at one event or summarize low-level records into ranked/grouped results.

## Dependencies

### Internal
- Consumed by query registry, CLI/API/MCP template metadata, and `QueryExecutor`.

### External
- YAML plus Jinja2 template syntax inside SQL.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
