# Test Contracts and Resources

Parent scope: [repository](../AGENTS.md).

Run pytest from the repository root. `pyproject.toml` discovers `tests/test_*.py`
and nested `test_*.py` modules. The full suite is deterministic and does not
require a live model provider or NPU; use temporary SQLite data for analysis.

## Suite Routing

| Scope | Guide / tests | Contract |
| --- | --- | --- |
| Service boundaries | [core](core/AGENTS.md) | Focus/cache ownership, query/report, import/split publication, skill destinations |
| Query engine and SQL | [query](query/AGENTS.md) | Validation, rendering, real SQLite semantics, completeness/timeouts |
| Snapshot mechanisms | [snapshot](snapshot/AGENTS.md) | Replay, mutations, records, schema and slices |
| Executable inputs | [fixtures](fixtures/AGENTS.md) | Review, checksum/size manifest, LFS hydration |
| Skills and evaluation | [skills](skills/AGENTS.md) | Static contracts, synthetic fixtures, descriptors and deterministic grading |
| Models | `models/`, `test_models.py` | Domain dataclasses/enums and sentinel behavior |

## Cross-Surface Test Map

| Files | What must stay aligned |
| --- | --- |
| `test_cli.py`, `test_cli_json.py`, `test_completion.py` | Typer commands/help/output/errors, JSON envelopes and completion handle cleanup |
| `test_api.py`, `test_contract_cli_api.py` | Public analyzer behavior and normalized CLI/API parity |
| `test_analyzer_lifecycle.py` | Terminal analyzer closure, borrowed/owned caches, constructor failures |
| `test_snapshot_analyzer_cache.py`, `test_query_cache_perf.py` | Connection/executor reuse, file replacement and explicit invalidation |
| `test_config.py`, `test_context.py` | Focus precedence/atomic writes, read-only validation and device discovery |
| `test_bundled_skills.py`, `test_package.py` | Authored/packaged skill parity, package metadata/import/version |
| `test_governance.py`, `test_release_workflow.py` | Provenance, issue/PR templates, bilingual contracts, release ordering |
| `test_snapshot_db.py`, `test_baseline_import.py` | Writer pragmas/indexes and benchmark measurement parsing |
| `test_leak_query_window.py` | Real CLI/SQLite verification of bounded leak-skill query windows |

## Fixture Gate and Isolation

`conftest.py:pytest_sessionstart` calls `_fixture_provenance.py` before collection.
Unexpected/missing pickle names, hash/size mismatch, or inconsistent review
manifests abort the session; there is no override. Local snapshots belong outside
the committed fixture directory. The gate validates bytes or reviewed LFS pointer
identity without unpickling; runtime tests still require hydrated inputs.

Tests that resolve/write focus must isolate CWD, `PT_SNAP_DB_PATH`, and home.
Skill mutation tests also isolate host environment variables and destination
directories. Do not let tests discover user focus or write installed skills.

## Resource Ownership

- `ResourceWarning` and `PytestUnraisableExceptionWarning` are errors. Autouse
  `collect_test_resources` triggers GC during teardown so leaks are attributed
  to the owning test, rather than hidden by a later collection.
- Explicitly close SQLite handles. For a transaction plus lifetime scope, use
  `with closing(connection) as conn, conn:`; the SQLite context manager alone
  commits/rolls back but does not close.
- `owned_service_instances` is opt-in for tests that directly construct imported
  analyzer/query/overview/report services. It wraps only test-module bindings
  and registers `.close()` finalizers. Do not use it in lifecycle tests where
  it could hide the defect being tested, or patch production constructors.
- Cache fixtures own their teardown. Borrowed-cache tests must verify that one
  service's cleanup leaves another user operational.

CLI help may contain ANSI color sequences; normalize color when asserting
semantic command/option text. Prefer executing help to matching adapter source
layout. Keep error/exit-code tests alongside successful output assertions.
