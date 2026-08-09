<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-26 | Updated: 2026-08-09 -->

# ISSUE_TEMPLATE

## Purpose
`ISSUE_TEMPLATE` contains structured GitHub issue forms for bugs, documentation requests, feature requests, questions, and template chooser configuration.

## Key Files
| File | Description |
|------|-------------|
| `01-bug-report.yml` | Form for reproducible defects and environment details. |
| `02-feature-request.yml` | Form for proposed enhancements. |
| `03-documentation.yml` | Form for documentation improvements or corrections. |
| `04-question.yml` | Form for usage questions. |
| `config.yml` | GitHub issue chooser configuration and valid contact links. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| None | Issue templates are flat YAML files. |

## For AI Agents

### Working In This Directory
- Keep issue forms scoped to this Python CLI/MCP project.
- Preserve valid GitHub issue form YAML structure.
- Ordering is controlled by numbered filenames; `config.yml` has no `issue_templates` key.

### Testing Requirements
- Validate YAML syntax and run `pytest tests/test_governance.py` after path/schema edits.

### Common Patterns
- Forms collect structured fields rather than relying on free-form Markdown only.

## Dependencies

### Internal
- Repository README/docs provide canonical terminology for issue prompts.

### External
- GitHub issue form YAML schema.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
