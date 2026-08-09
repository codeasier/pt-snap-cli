<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-26 | Updated: 2026-08-08 -->

# .github

## Purpose
`.github` contains GitHub project automation: issue forms, pull request templates, snapshot provenance enforcement, release workflow, and CI verification definitions.

## Key Files
| File | Description |
|------|-------------|
| `pull_request_template.md` | Default PR body, including exact snapshot provenance labels parsed by the guard. |
| `scripts/check_snapshot_provenance.py` | Base/head blob comparison plus PR decision validation. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `ISSUE_TEMPLATE/` | Numbered `.yml` issue forms and chooser config (see `ISSUE_TEMPLATE/AGENTS.md`). |
| `scripts/` | Repository governance scripts, including snapshot provenance validation. |
| `workflows/` | GitHub Actions workflow definitions (see `workflows/AGENTS.md`). |

## For AI Agents

### Working In This Directory
- Treat workflow changes as CI-affecting; keep dependency installation and verification commands aligned with `pyproject.toml`.
- Keep issue and PR templates concise and consistent with repository scope.

### Testing Requirements
- Validate YAML syntax for workflow or issue template edits.
- For workflow changes, mirror commands locally where practical before relying on CI.
- Run `pytest tests/test_governance.py tests/test_release_workflow.py` when provenance scripts, workflow wiring, or PR declarations change.

### Common Patterns
- `test.yml` is both normal CI and the local reusable workflow called by a tag release.
- Snapshot runtime PRs require one validated provenance decision; non-PR runs still enforce append-only provenance content.

## Dependencies

### Internal
- `pyproject.toml` defines the Python versions, package dependencies, and tools invoked by workflows.
- `tests/` contains the suite run by CI.

### External
- GitHub Actions runners and standard GitHub issue/PR template formats.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
