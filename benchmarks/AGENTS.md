# Opt-In Performance Measurements

Parent scope: [repository](../AGENTS.md).

These are standalone scripts, not pytest targets. They can consume substantial
CPU/memory/time; the import benchmark deserializes reviewed executable fixtures.

| Script | Inputs and side effects |
| --- | --- |
| `baseline_import.py` | Warmup/formal imports, optional profiling/correctness queries, temporary databases, timing/RSS/database/frame summaries; import uses `set_focus=False` |
| `sqlite_write_throughput.py` | Synthetic rows against default/optimized writers in temporary databases |

## Preparation and Execution

Run from the repository root with `PYTHONPATH=src python benchmarks/<script>.py`.
Before the import benchmark, run `pytest tests/test_fixture_provenance.py` and
follow [fixture acceptance](../tests/fixtures/AGENTS.md). The large `131k`/`628k`
inputs use Git LFS; hydrate selected objects and rerun verification. The checksum
gate accepts a valid pointer, but benchmark loading cannot use that pointer.

The import benchmark defaults to the large samples. For a bounded check, use
`--samples 8k --runs-8k 1 --skip-profile`; it still loads pickle, performs a
warmup and runs correctness queries unless separately disabled. Keep outputs in
temporary/ignored locations. Dependency setup and sample hydration are separate
from running these scripts.

## Comparisons and Tests

Use the same interpreter, platform, fixture hashes, arguments, warmup and run
counts when comparing changes. RSS normalization is platform-dependent; do not
compare raw resource output as though all systems use the same units.

Run `pytest tests/test_baseline_import.py` for parsing/RSS helper changes.
Import/runtime changes also need their core/snapshot correctness suites, and
SQLite writer/index changes need `tests/test_snapshot_db.py`. Faster benchmark
results do not replace replay, schema or publication correctness evidence.
