# Source and Distribution Boundary

Parent scope: [repository](../AGENTS.md).

`pyproject.toml` discovers `pt_snap_cli*` packages under `src`. The runtime
ownership map is in [pt_snap_cli](pt_snap_cli/AGENTS.md). Adding a sibling
package or moving resources requires reviewing the setuptools configuration.

## What Ships

| Input | Distribution contract |
| --- | --- |
| `pt_snap_cli/` | Python package, with `pt-snap` registered to `cli:_safe_call` |
| `pt_snap_cli/query/templates/` | Root/category YAML globs in package data; recursively loaded by the query registry |
| `pt_snap_cli/bundled_skills/` | Authored skill copies included by `bundled_skills/**/*`; fallback catalog for wheel installs |
| `pt_snap_cli/snapshot/LICENSE`, `PROVENANCE.md` | Explicitly included snapshot license/evidence assets |

Versioning uses setuptools-scm (`no-guess-dev`, `no-local-version`), not a
hand-maintained constant. `pt_snap_cli/version.py` reads installed distribution
metadata and falls back to `0.0.0-dev` only if the distribution is absent.
Source-path selection alone does not change installed version metadata.

## Change Together

- Asset moves: package-data declarations, the registry or `SkillService`
  resource lookup, and `tests/test_bundled_skills.py` / `tests/test_package.py`.
- Skill edits: use the authoring rules in [skills](../skills/AGENTS.md); building
  a wheel does not synchronize authored and bundled files for you.
- Version/release changes: follow [release workflow](../.github/workflows/AGENTS.md).
  Build outputs are sdist and wheel in `dist/`; setuptools also creates build
  intermediates. Build isolation may fetch dependencies.
- Installed behavior: `.github/scripts/clean_wheel_agent_acceptance.py` verifies
  package resolution inside a temporary venv, bundled skill discovery and
  installation, then trusted import/reuse, overview and query. Its venv shares
  system dependencies but installs the supplied wheel with `--no-deps --no-index`;
  this is not a fresh dependency-resolution test. See [automation](../.github/AGENTS.md).

Use `pytest tests/test_package.py tests/test_bundled_skills.py` for package
contracts. A source checkout alone cannot prove that a newly added asset ships.
