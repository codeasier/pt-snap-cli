<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-26 | Updated: 2026-08-08 -->

# tests

## Purpose
`tests` contains the pytest suite for CLI/API/MCP contracts, configuration, services, query behavior, packaging/governance, and the first-party snapshot runtime. Most tests use temporary data; snapshot and import suites may use only checksum-verified executable fixtures under `tests/fixtures/snapshots/`.

## Key Files
| File | Description |
|------|-------------|
| `conftest.py` | Verifies executable fixture provenance at session start and registers repository-wide pytest markers. |
| `run_tests.sh` | Developer-specific Conda/coverage wrapper; prefer direct `pytest` unless its local environment exists. |
| `test_api.py` | Tests for the public `SnapshotAnalyzer` API layer. |
| `test_cli.py` | CLI behavior tests, including focus, query listing, template info, and output limits. |
| `test_completion.py` | Shell completion helper tests. |
| `test_config.py` | Configuration and focus precedence tests. |
| `test_contract_cli_mcp.py` | Normalized behavior contract between CLI and MCP adapters. |
| `test_context.py` | SQLite context, schema validation, and device discovery tests. |
| `test_fixture_provenance.py` | Non-deserializing coverage, SHA-256, size, and Git LFS pointer validation for executable fixtures. |
| `test_governance.py` | Snapshot provenance and repository governance contracts. |
| `test_mcp_server.py` | MCP server tool/resource/prompt behavior tests. |
| `test_models.py` | Package-level model behavior tests. |
| `test_package.py` | Package metadata/import/version tests. |
| `test_release_workflow.py` | Release workflow and package publication contract tests. |
| `test_snapshot_analyzer_cache.py`, `test_query_cache_perf.py` | Analyzer cache invalidation and repeated-query connection reuse contracts. |
| `test_snapshot_db.py` | SnapshotDb write pragmas and query-index creation. |
| `test_baseline_import.py` | Import benchmark metric parsing and platform RSS normalization. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `core/` | Service-layer tests for focus, import, split, query, metadata, and reports (see `core/AGENTS.md`). |
| `fixtures/` | Reviewed executable inputs and their trust/checksum records (see `fixtures/AGENTS.md`). |
| `models/` | Domain model and enum unit tests governed by this guide. |
| `query/` | Query builder, config, executor, mapper, registry, and condition tests (see `query/AGENTS.md`). |
| `snapshot/` | Representation, replay, database adaptor, and slicing runtime tests (see `snapshot/AGENTS.md`). |
| `skills/` | Static skill contracts and local-first suite/case evaluation harness (see `skills/AGENTS.md`). |

## For AI Agents

### Working In This Directory
- Add or update focused tests with behavior changes; `tests/test_cli.py` is the first place to check for user-facing command behavior.
- Use temporary directories and SQLite fixtures instead of relying on local `.pt-snap/focus.json` or real snapshot databases.
- Keep tests deterministic across working directories and user machines.
- Isolate CWD, `PT_SNAP_DB_PATH`, and `Path.home()` in tests that resolve or persist focus.
- Keep live agent runs out of normal pytest; skill evaluation definitions and deterministic graders live under `tests/skills/`.

### Testing Requirements
- Run `pytest` for the full suite.
- Use targeted commands such as `pytest tests/query/test_executor.py` for narrow query changes.
- Run `pytest tests/test_fixture_provenance.py` before tests that deserialize committed snapshot fixtures.

### Common Patterns
- CLI tests exercise Typer commands through test runners and assert printed output.
- Query tests build minimal SQLite schemas and YAML-like config objects around the template pipeline.
- Snapshot/import tests may deserialize only objects accepted by `fixtures/snapshots/PROVENANCE.md` and `SHA256SUMS`; never load a new or changed pickle before review.

## Dependencies

### Internal
- Tests import `pt_snap_cli` package modules from `src/` via editable install or test environment path configuration.

### External
- `pytest` is the test runner.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
