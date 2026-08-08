<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-26 | Updated: 2026-08-08 -->

# .github

## Purpose
`.github` contains GitHub project automation: issue forms, pull request templates, snapshot provenance enforcement, release workflow, and CI verification definitions.

## Key Files
| File | Description |
|------|-------------|
| None | GitHub metadata is organized in subdirectories. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `ISSUE_TEMPLATE/` | Structured issue form YAML files (see `ISSUE_TEMPLATE/AGENTS.md`). |
| `PULL_REQUEST_TEMPLATE/` | Pull request description template (see `PULL_REQUEST_TEMPLATE/AGENTS.md`). |
| `scripts/` | Repository governance scripts, including snapshot provenance validation. |
| `workflows/` | GitHub Actions workflow definitions (see `workflows/AGENTS.md`). |

## For AI Agents

### Working In This Directory
- Treat workflow changes as CI-affecting; keep dependency installation and verification commands aligned with `pyproject.toml`.
- Keep issue and PR templates concise and consistent with repository scope.

### Testing Requirements
- Validate YAML syntax for workflow or issue template edits.
- For workflow changes, mirror commands locally where practical before relying on CI.
- Run `pytest tests/test_governance.py` when provenance scripts, workflow wiring, or PR declarations change.

### Common Patterns
- CI installs the package with development dependencies and runs lint/type/test checks.
- Snapshot runtime changes require one validated provenance decision from the PR body.

## Dependencies

### Internal
- `pyproject.toml` defines the Python versions, package dependencies, and tools invoked by workflows.
- `tests/` contains the suite run by CI.

### External
- GitHub Actions runners and standard GitHub issue/PR template formats.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
