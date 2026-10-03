# AGENTS.md

Repository-wide guidance for `pt-snap-cli`, a Python 3.10+ package for importing,
splitting, and analyzing PyTorch memory snapshots. User-facing behavior belongs
in `README.md`, `README_zh.md`, and `docs/`; `CLAUDE.md` delegates here.

## Start Here

Read the nearest scoped guide before editing. Each guide links its children;
follow the hierarchy rather than copying local rules into this file.

| Scope | Guide | Ownership |
| --- | --- | --- |
| Package/build boundary | [src](src/AGENTS.md) | Setuptools discovery, installed assets, versioning |
| Runtime and adapters | [pt_snap_cli](src/pt_snap_cli/AGENTS.md) | CLI/API, focus, Context, and subsystem routing |
| Tests | [tests](tests/AGENTS.md) | Contracts, resource ownership, fixture gate, focused suites |
| Agent workflows | [skills](skills/AGENTS.md) | Routing, setup, collection, diagnostics, packaged copies |
| User documentation | [docs](docs/AGENTS.md) | Bilingual guides, API references, legal evidence |
| Automation | [.github](.github/AGENTS.md) | Provenance guard, issue forms, CI and release |
| Performance | [benchmarks](benchmarks/AGENTS.md) | Opt-in import and SQLite measurements |

## Runtime Topology

| Surface | Entry/registration | Implementation |
| --- | --- | --- |
| Console script | `pyproject.toml` → `pt_snap_cli.cli:_safe_call` | `cli.py` root commands; `cli_reports.py` and `cli_skills.py` groups; `cli_output.py` shared output/errors |
| Python API | `api.py:SnapshotAnalyzer` | Session focus, template queries, capabilities, overview, metadata |
| Product behavior | `core/` services | Shared resolution, validation, results and errors; import/split publication; CLI-only skill management |
| Analysis | `Context` → `query/` | Read-only SQLite, layout detection, YAML contracts, Jinja rendering, result mapping |
| Snapshot runtime | `snapshot/` via core import/split | Trusted representation loading, allocator replay, database adaptation, slicing |
| Agent integration | Authored `skills/` → packaged `bundled_skills/` | Host-loaded workflows calling the CLI; no MCP server or console entry point |

## Development and Checks

Run from the repository root using the intended Python environment. Installing
changes that environment and may download dependencies:

```bash
python -m pip install -e ".[dev]"
```

For an isolated worktree using dependencies already installed elsewhere, set
`PYTHONPATH="$PWD/src"` on Python/test commands so imports come from that worktree.
Do not silently repoint a shared editable installation.

```bash
pytest tests/test_fixture_provenance.py   # Before any committed-pickle loading
pytest                                  # Or the owning focused suite
ruff check .
black --check .
python -m basedpyright --pythonpath "$(python -c 'import sys; print(sys.executable)')"
git diff --check
```

- Type checking covers all `src/pt_snap_cli`, including `snapshot/`. Zero errors
  is the gate; warnings are informational. Preserve the file-level Any/Unknown
  error gates in `api.py`, `core/models.py`, and `snapshot/representation.py`;
  do not downgrade snapshot through an `executionEnvironments` exception.
- Pytest treats `ResourceWarning` and `PytestUnraisableExceptionWarning` as
  errors. Ownership/teardown guidance lives in [tests](tests/AGENTS.md).
- Coverage is measured with branches enabled. The overall floor and independent
  critical-file floors are documented with [CI](.github/workflows/AGENTS.md).
- `tests/run_tests.sh` assumes a developer-specific Conda path and writes
  `test_reports/`; prefer direct pytest. `.pt-snap/`, `.tmp/`, `.worktrees/`,
  and `tmp/` are ignored and excluded from root Ruff/Black checks.
- `python -m build` writes `dist/` and build intermediates and may download build
  requirements. See [packaging](src/AGENTS.md) before using it as verification.

## Cross-Repository Contracts

1. **One behavior layer.** CLI and `SnapshotAnalyzer` adapters share core
   semantics; update `tests/test_contract_cli_api.py` when normalized shared
   results change. Skill management is CLI-only; the analyzer is not an
   import/split or skill-install facade.
2. **Resolution and read-only analysis.** `Config.resolve_focus()` selects
   explicit path → `PT_SNAP_DB_PATH` → nearest ancestor `.pt-snap/focus.json` →
   legacy `~/.config/pt-snap-cli/config.json`. Queries select explicit device →
   focused device → first discovered device. `Context` requires `dictionary`
   and opens SQLite with `mode=ro`; analysis must not migrate a database or
   persist detected layout into focus.
3. **Explicit resource ownership.** Analyzer `close()`/`with` ends its lifetime;
   an injected cache stays caller-owned. Cache/service reuse and terminal
   analyzer closure are different contracts; see [core](src/pt_snap_cli/core/AGENTS.md).
4. **Single query contract.** YAML metadata, validation, registry, executor,
   services and adapters form one path. Layout-specific SQL shares a public
   schema and semantic contract. Query caps, completeness and timeouts must
   remain visible to callers; see [query](src/pt_snap_cli/query/AGENTS.md).
5. **Trusted input and transactional publication.** Pickle loading is code
   execution, not a sandbox. Import stages and validates before publication and
   includes a requested focus update in rollback handling. Split replay-validates
   staged output and publishes without replacing an existing destination.
6. **Skill/source parity.** Author `skills/<name>/SKILL.md` and keep its packaged
   `src/pt_snap_cli/bundled_skills/<name>/SKILL.md` identical. Diagnostic workflows
   use read-only SnapshotDB operations; setup and collection have separate
   mutation/consent boundaries.
7. **Evidence and localization.** Snapshot `PROVENANCE.md` is append-only;
   changes anywhere under `snapshot/` require the PR provenance decision,
   including documentation-only changes. Executable fixture review is a
   separate [acceptance process](tests/fixtures/AGENTS.md). Keep English/Chinese
   user guides behaviorally aligned when public behavior changes.

## Change Routing

| Change | Start with | Verification owner |
| --- | --- | --- |
| CLI/API, completion, focus, Context | [Package adapters](src/pt_snap_cli/AGENTS.md) | [Cross-surface tests](tests/AGENTS.md) |
| Cache, import/split, reports, skill destinations | [Core services](src/pt_snap_cli/core/AGENTS.md) | [Service tests](tests/core/AGENTS.md) |
| SQL, parameters, completeness, result semantics | [Query engine](src/pt_snap_cli/query/AGENTS.md), [YAML templates](src/pt_snap_cli/query/templates/AGENTS.md) | [Query tests](tests/query/AGENTS.md) |
| Representation, replay, schema, slicing | [Snapshot runtime](src/pt_snap_cli/snapshot/AGENTS.md) | [Runtime tests](tests/snapshot/AGENTS.md) |
| Diagnostic instructions and evaluation | [Skills](skills/AGENTS.md) | [Skill contracts/harness](tests/skills/AGENTS.md) |
| Packaging or release | [Source layout](src/AGENTS.md), [workflows](.github/workflows/AGENTS.md) | `tests/test_package.py`, `tests/test_release_workflow.py` |
