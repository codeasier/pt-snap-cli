<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-26 | Updated: 2026-05-26 -->

# .github

## Purpose
`.github` contains GitHub project automation: issue forms, pull request templates, release workflow, and CI test/type-check workflow definitions.

## Key Files
| File | Description |
|------|-------------|
| None | GitHub metadata is organized in subdirectories. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `ISSUE_TEMPLATE/` | Structured issue form YAML files (see `ISSUE_TEMPLATE/AGENTS.md`). |
| `PULL_REQUEST_TEMPLATE/` | Pull request description template (see `PULL_REQUEST_TEMPLATE/AGENTS.md`). |
| `workflows/` | GitHub Actions workflow definitions (see `workflows/AGENTS.md`). |

## For AI Agents

### Working In This Directory
- Treat workflow changes as CI-affecting; keep dependency installation and verification commands aligned with `pyproject.toml`.
- Keep issue and PR templates concise and consistent with repository scope.

### Testing Requirements
- Validate YAML syntax for workflow or issue template edits.
- For workflow changes, mirror commands locally where practical before relying on CI.

### Common Patterns
- CI installs the package with development dependencies and runs lint/type/test checks.

## Dependencies

### Internal
- `pyproject.toml` defines the Python versions, package dependencies, and tools invoked by workflows.
- `tests/` contains the suite run by CI.

### External
- GitHub Actions runners and standard GitHub issue/PR template formats.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
