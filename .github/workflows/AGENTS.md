<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-26 | Updated: 2026-05-26 -->

# workflows

## Purpose
`workflows` contains GitHub Actions definitions for continuous integration and release automation.

## Key Files
| File | Description |
|------|-------------|
| `test.yml` | CI workflow for installing dev dependencies and running lint/type/test checks. |
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

### Testing Requirements
- Validate YAML syntax.
- Run equivalent local commands when changing CI command sequences.

### Common Patterns
- Workflows install the package with development extras before verification.

## Dependencies

### Internal
- `pyproject.toml` defines package metadata, dev extras, and tool configuration.
- `tests/` and source files are exercised by CI.

### External
- GitHub Actions hosted runners and packaging/publishing actions.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
