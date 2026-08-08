<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-26 | Updated: 2026-08-08 -->

# PULL_REQUEST_TEMPLATE

## Purpose
`PULL_REQUEST_TEMPLATE` contains the default pull request description template used for repository contributions.

## Key Files
| File | Description |
|------|-------------|
| `pull_request_template.md` | PR body template for summaries, testing, and review context. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| None | PR template content is flat. |

## For AI Agents

### Working In This Directory
- Keep checklist items aligned with current verification expectations.
- Avoid adding process requirements that CI or project documentation does not support.
- Preserve the exact snapshot provenance decision/reason labels parsed by `.github/scripts/check_snapshot_provenance.py`.

### Testing Requirements
- Review Markdown rendering after edits.
- Run `pytest tests/test_governance.py` when changing provenance declarations.

### Common Patterns
- The template should prompt contributors for what changed and how it was tested.
- Snapshot runtime changes require exactly one `updated` or `no-update` decision; `no-update` also requires a specific reason.

## Dependencies

### Internal
- `.github/workflows/` defines automated checks referenced by PR guidance.

### External
- GitHub pull request template Markdown support.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
