# AGENTS.md

This is the repository-wide entry point for coding agents. Keep durable project
facts here; user-facing behavior belongs in `README.md` and `docs/`.

## Project Scope

`pt-snap-cli` is a Python 3.10+ package for importing, splitting, inspecting,
and querying PyTorch memory snapshots. It exposes a Typer CLI, a Python API,
and an MCP server over shared service-layer behavior.

## Development Commands

Run these commands from the repository root.

- Install for local development: `pip install -e .`
- Install development dependencies: `pip install -e ".[dev]"`
- Run all tests: `pytest`
- Run one file: `pytest tests/test_cli.py`
- Run one test: `pytest tests/test_cli.py -k test_version_flag`
- Lint: `ruff check .`
- Check formatting: `black --check .`
- Apply formatting: `black .`

`tests/run_tests.sh` is tied to a developer-specific Conda path and writes
coverage reports under `test_reports/`; use direct `pytest` commands unless
that local environment is intentionally available.

## Scoped Guidance

| Scope | Guide | Responsibility |
| --- | --- | --- |
| GitHub automation | [.github/AGENTS.md](.github/AGENTS.md) | Issue/PR templates, provenance guard, CI, and release workflows |
| User documentation | [docs/AGENTS.md](docs/AGENTS.md) | English/Chinese guides, API docs, navigation, and legal evidence |
| Package source | [src/AGENTS.md](src/AGENTS.md) | Installable package boundaries and source-layout rules |
| Tests | [tests/AGENTS.md](tests/AGENTS.md) | Cross-surface contracts, service/query/runtime suites, and reviewed executable fixtures |
| Benchmarks | [benchmarks/AGENTS.md](benchmarks/AGENTS.md) | Import and SQLite performance measurement with temporary outputs |
| Agent skills | [skills/AGENTS.md](skills/AGENTS.md) | Installation approval and read-only memory-diagnostic boundaries |

## Runtime Topology

| Surface | Entry point | Responsibility |
| --- | --- | --- |
| CLI | `src/pt_snap_cli/cli.py` via `pt_snap_cli.cli:_safe_call` | Typer commands for focus, import, split, metadata, query, reports, and config |
| Python API | `src/pt_snap_cli/api.py` (`SnapshotAnalyzer`) | Programmatic focus, query, and metadata facade |
| MCP | `src/pt_snap_cli/mcp/server.py` via `pt_snap_cli.mcp.server:main` | Agent tools/resources backed by `SnapshotAnalyzer` |
| Product services | `src/pt_snap_cli/core/` | Shared focus, import, split, query, report, metadata, and error semantics |
| Database access | `src/pt_snap_cli/context.py` | Read-only SQLite validation, connection management, and device discovery |
| Query engine | `src/pt_snap_cli/query/` | YAML loading, registry, parameter validation, SQL rendering/execution, and result mapping |
| Snapshot runtime | `src/pt_snap_cli/snapshot/` | First-party pickle/JSON representation, replay, database import, and slicing |
| Library models | `src/pt_snap_cli/models/` | Dataclass models and allocator event/block enums |

Installed scripts and package data are declared in `pyproject.toml`. Query
templates under category subdirectories are included by
`query/templates/*/*.yaml`.

## Repository Invariants

### CLI, API, and MCP

- Keep normalized CLI and MCP behavior in shared API/core services; adapters may
  format output differently but must not redefine focus, query, metadata, or
  error semantics.
- Update `tests/test_contract_cli_mcp.py` when a shared CLI/MCP capability or
  normalized result changes.

### Focus and database selection

- `Config.resolve_focus()` resolves the database in this order: explicit path,
  `PT_SNAP_DB_PATH`, nearest ancestor `.pt-snap/focus.json`, then legacy global
  config at `~/.config/pt-snap-cli/config.json`.
- Query device selection is explicit device, focused device, then the first
  device discovered from `trace_entry_<device_id>` tables.
- `Context` opens SQLite with `mode=ro` and validates the `dictionary` table.
  Do not introduce writes into the analysis path.

### Query templates

- Packaged templates live under `src/pt_snap_cli/query/templates/<category>/*.yaml`.
- `query/config.py` owns YAML parsing and parameter validation;
  `query/registry.py` recursively loads templates into the singleton registry;
  `query/executor.py` renders with Jinja2 `StrictUndefined` and injects device
  table names before executing through `Context`.
- When template metadata or behavior changes, review the YAML, config, registry,
  executor, `core/query_service.py`, CLI/MCP presentation, and focused tests
  together.

### Snapshot import and split

- Pickle input is trusted-code execution, not a sandbox. Never load an
  untrusted fixture or snapshot merely to inspect it.
- Import writes and validates metadata on a temporary database before
  publication. When focus update is requested, publication retains a rollback
  link until the atomic focus write succeeds; reported failure preserves the
  previous destination.
- Split requires exactly one positive strategy (`--slices` or
  `--max-entries`), an absent destination, replay-validates generated slices,
  and publishes the staged directory without replacement.
- `src/pt_snap_cli/snapshot/PROVENANCE.md` is append-only. The guard compares
  base/head Git blobs on PRs, main pushes, and releases; snapshot-runtime PRs
  additionally require the exact provenance decision in the default PR template.

## Change Routing

| Change | Start here | Focused tests |
| --- | --- | --- |
| CLI options or terminal rendering | `src/pt_snap_cli/cli.py` and the owning core service | `tests/test_cli.py`, `tests/test_completion.py` |
| Focus precedence or persistence | `src/pt_snap_cli/config.py`, `src/pt_snap_cli/core/focus_service.py`, `src/pt_snap_cli/context.py` | `tests/test_config.py`, `tests/test_context.py`, `tests/core/test_focus_service.py` |
| Context/executor caching | `src/pt_snap_cli/core/context_cache.py`, `src/pt_snap_cli/api.py`, `src/pt_snap_cli/core/query_service.py` | `tests/core/test_context_cache.py`, `tests/test_snapshot_analyzer_cache.py`, `tests/test_query_cache_perf.py` |
| Query schema, SQL, or categories | `src/pt_snap_cli/query/`, `src/pt_snap_cli/core/query_service.py` | `tests/query/`, `tests/core/test_query_service.py` |
| MCP or Python API behavior | `src/pt_snap_cli/api.py`, `src/pt_snap_cli/mcp/server.py` | `tests/test_api.py`, `tests/test_mcp_server.py`, `tests/test_contract_cli_mcp.py` |
| Snapshot import or metadata | `src/pt_snap_cli/core/import_service.py`, `src/pt_snap_cli/core/import_metadata.py`, `src/pt_snap_cli/core/snapshot_import_backend.py` | `tests/core/test_import_*.py`, `tests/test_snapshot_db.py` |
| Snapshot splitting or replay | `src/pt_snap_cli/core/split_service.py`, `src/pt_snap_cli/snapshot/` | `tests/core/test_split_service.py`, `tests/snapshot/` |
| Reports | `src/pt_snap_cli/core/report_service.py`, report commands in `src/pt_snap_cli/cli.py` | `tests/core/test_report_service.py`, report cases in `tests/test_cli.py` |
| Agent setup or peak-memory diagnostic skills | `skills/` and the referenced CLI/query surfaces | `tests/test_setup_skill.py`, `tests/test_memory_peak_breakdown_skill.py` |
| Packaging or release | `pyproject.toml`, `.github/workflows/` | `tests/test_package.py`, `tests/test_release_workflow.py` |
| Executable fixtures | `tests/fixtures/snapshots/` | `tests/test_fixture_provenance.py` before any deserializing suite |

## Documentation Boundaries

- `README.md` and `README_zh.md` are user-facing entry points.
- `docs/en/` and `docs/zh/` must remain behaviorally aligned for user guides.
- Keep agent instructions in this file unless a subtree gains an independent
  lifecycle or maintenance contract that warrants a local `AGENTS.md`.
