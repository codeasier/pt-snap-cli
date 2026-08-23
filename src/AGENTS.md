<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-26 | Updated: 2026-08-24 -->

# src

Parent scope: [repository root](../AGENTS.md)

## Purpose
`src` contains the installable Python package for `pt-snap-cli`. Its only package subtree, `pt_snap_cli`, holds the CLI, MCP server, product services, query system, first-party snapshot runtime, and domain models shipped in the distribution.

## Key Files
| File | Description |
|------|-------------|
| None | Source files live under the `pt_snap_cli/` package. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `pt_snap_cli/` | Main package implementation (see `pt_snap_cli/AGENTS.md`). |

## For AI Agents

### Working In This Directory
- Keep import paths package-relative to `pt_snap_cli` and avoid adding sibling packages unless packaging metadata is updated.
- When adding package data, update `pyproject.toml` so files are included in builds.

### Testing Requirements
- Run package-level tests from the repository root with `pytest` or focused tests in `tests/`.

### Common Patterns
- The repository uses a `src/` layout, so tests and local commands should import the installed/editable package rather than relying on the repository root being importable.

## Dependencies

### Internal
- `pt_snap_cli/` is installed via the `pyproject.toml` setuptools configuration.

### External
- setuptools package discovery uses `where = ["src"]`.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
