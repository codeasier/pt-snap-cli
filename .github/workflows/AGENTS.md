<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-26 | Updated: 2026-08-08 -->

# workflows

## Purpose
`workflows` contains GitHub Actions definitions for continuous integration and release automation.

## Key Files
| File | Description |
|------|-------------|
| `test.yml` | PR provenance gate plus lint, type, test-matrix, coverage, build, and wheel smoke checks. |
| `release.yml` | Release workflow for building and publishing package artifacts. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| None | Workflow YAML files are flat. |

## For AI Agents

### Working In This Directory
- Keep workflow Python versions and commands aligned with `pyproject.toml`.
- Treat release workflow edits as high-impact and verify syntax carefully.
- Do not bypass tests, lint, type checks, or publishing safeguards without explicit instruction.
- Keep snapshot provenance inputs and declaration parsing aligned with `.github/scripts/check_snapshot_provenance.py` and the PR template.

### Testing Requirements
- Validate YAML syntax.
- Run equivalent local commands when changing CI command sequences.
- Run `pytest tests/test_governance.py tests/test_release_workflow.py` for provenance or release workflow changes.

### Common Patterns
- Workflows install the package with development extras before verification.
- The test workflow defines independent provenance, lint, and Python-version test jobs that may run concurrently.

## Dependencies

### Internal
- `pyproject.toml` defines package metadata, dev extras, and tool configuration.
- `tests/` and source files are exercised by CI.

### External
- GitHub Actions hosted runners and packaging/publishing actions.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
