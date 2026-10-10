# Dataset correctness and default-scale acceptance

Dataset tests distinguish three sources of evidence. Passing a synthetic SQL
fixture is not evidence that a producer, collector, or exporter ran.

## Regular correctness gate

`tests/core/test_dataset_realistic.py` runs eight fixed seeds and twenty query
shapes per seed against a standalone reference. Each shard contains only blocks
allocated within its window and blocks still alive on entry. Completed lifetimes
do not appear in later windows; global allocation/free-completion IDs remain
unchanged. Cases include address reuse, a pending free crossing a window,
preexisting/static blocks, NULL/empty/whitespace stacks, a literal missing-stack
label, sorting, pagination, filters and dynamic `top_n` truncation.

Comparisons are exact, including four-decimal percentages. The minimal 1-byte /
127-byte case requires `0.7813`; an 8-MiB scale variant also checks six-decimal
GiB rounding. The contract is exact parity with the active SQLite runtime's
arithmetic and `ROUND`, not a mathematical half-up approximation. Near-half
3/2,000,000 and 7/2,000,000 proportions, nearby values and large GiB conversions
are compared with standalone SQL on that same runtime, since SQLite versions
can differ in how they format binary doubles. Scalar rounding uses short-lived,
explicitly closed in-memory connections without source reads or merge tables;
timeouts during either rounding pass also verify connection/cursor cleanup. Dataset-only provenance is excluded
from common-schema comparisons. Point-event stored `state` is an observation,
not state at that event; global block comparisons use the latest containing
observation for both sides.

A separate two-device native-v2 case executes actual replay/import, then attaches
an explicitly constructed ordered-frame extension. Equal local stack IDs in
different members must not merge different ordered arrays. Order, repeats and
extra raw-frame fields are checked against input arrays. Common event/block
fields are compared with standalone SQL; the optional extension does not claim
that the native writer emits ordered frames.

```bash
pytest tests/test_fixture_provenance.py
pytest tests/core/test_dataset_realistic.py tests/core/test_dataset_attribution.py tests/core/test_dataset_global.py
```

## Slow scale and installed export gates

`tests/core/test_dataset_scale_acceptance.py` is marked `slow` and contains:

- Synthetic compatibility-v1 SQLite: 1,000,000 real events in two default-sized
  500,000-event members, with window-correct lifecycle membership. Global peak,
  gap, event/allocation pages, block pages, terminal leak candidates and stack
  aggregation must succeed
  using the real default work budgets. Unbounded materialization must still fail
  at the genuine row ceiling. Budgets are not monkeypatched down or disabled.
  Ordered-frame aggregation may still need the bounded raw-frame fallback; this
  gate does not claim all large ordered-frame or unlimited-output queries succeed.
- A separate 10,000-event / 8-KiB-inline-stack dataset checks aggregate/small-page
  success and genuine 64-MiB full-output rejection without creating an 8-GB file.
- A trusted, test-owned snapshot with 500,002 alloc/free-request/free-completion
  events goes through a non-editable installed `pt-snap import --format msinsight`
  with **no capacity override**. The resulting 500,000 + 2 member layout and
  cross-boundary lifecycle membership are checked before installed CLI/API peak,
  page, terminal-candidate, point-event and report queries. Artifact hashes must
  remain unchanged during queries.

Build the wheel from the intended clean checkout using the
[distribution instructions](../../README.md#building-distributions), then run:

```bash
pytest tests/test_fixture_provenance.py
PT_SNAP_ACCEPTANCE_WHEEL="$(realpath dist/<built-wheel>.whl)" \
  pytest tests/core/test_dataset_scale_acceptance.py --junitxml=dataset-acceptance.xml
```

Replace `<built-wheel>` with the actual wheel name. The test installs that exact
wheel into its temporary directory using `--no-deps --no-index`; subprocesses
clear source `PYTHONPATH` and verify that `pt_snap_cli` resolves inside the
installation. Runtime dependencies are reused from the test interpreter: this
is not a fresh dependency-resolution test. Without `PT_SNAP_ACCEPTANCE_WHEEL`,
only the installed test is explicitly skipped; that skip is not E2E acceptance.
Use `pytest -m 'not slow'` for the regular suite.

The installed test writes `acceptance.json` under its pytest temporary directory
and a `dataset_acceptance` JUnit property containing the wheel/source SHA-256,
package path, event counts, import duration and query assertions. Duration is
observational; there is no fixed timing assertion or RSS promise.

## Evidence limits

The [historical performance baseline](../dataset-performance-baseline.json)
uses a 581,140-byte reviewed snapshot and capacity 2,000. Its sharded run has
8,092 real events across five members. It remains useful historical evidence,
but cannot demonstrate default-capacity scalability.

The new exporter gate exercises the real first-party replay/export/query chain
on inspectable test-owned input. It does not execute live PyTorch/NPU collection,
the upstream msinsight producer, or its GUI. Those acceptance steps remain
separate. No new committed pickle is introduced. The provenance gate runs before
collection; the test-owned temporary input is written during the test.
