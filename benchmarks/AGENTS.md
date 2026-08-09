<!-- Parent: ../AGENTS.md -->

# benchmarks

## Purpose
`benchmarks` contains opt-in performance measurements. These scripts are not
pytest entry points: they can consume substantial CPU, memory, and time, and the
import benchmark deserializes reviewed executable fixtures.

## Entry Points
| File | Behavior |
| --- | --- |
| `baseline_import.py` | Runs warmup/formal imports in temporary directories, profiles one import, and prints timing, RSS, database, and correctness summaries. |
| `sqlite_write_throughput.py` | Compares default and optimized SQLite writers using temporary databases. |

## Safety And Execution
- Run from the repository root with `PYTHONPATH=src python benchmarks/<script>.py`.
- Run `pytest tests/test_fixture_provenance.py` before `baseline_import.py`; it loads pickle fixtures listed in `tests/fixtures/snapshots/SHA256SUMS`.
- Before selecting the 131k or 628k samples, hydrate their Git LFS objects (for example, `git lfs pull --include="tests/fixtures/snapshots/*.pickle"`) and verify their on-disk sizes match `tests/fixtures/snapshots/PROVENANCE.md`; the checksum gate also accepts an unhydrated pointer, but the benchmark cannot deserialize one.
- `baseline_import.py` defaults to the large 131k and 628k samples. Use `--samples 8k` and reduced run counts for a short check.
- Both scripts keep generated databases in temporary directories; do not redirect benchmark output into tracked source paths.
- Compare performance with the same interpreter, platform, fixture hashes, arguments, and warmup/run counts.

## Focused Tests
- Run `pytest tests/test_baseline_import.py` for metric parsing and platform RSS normalization.
- Runtime/import changes also require the owning core or snapshot tests; benchmark output alone is not correctness evidence.
