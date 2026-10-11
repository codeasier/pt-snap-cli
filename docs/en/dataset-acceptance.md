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
- A trusted, test-owned snapshot with 1,000,000 alloc/free-request/free-completion
  events goes through the clean-venv installed `pt-snap import --format msinsight`
  with **no capacity override**, producing two full 500,000-event members. All
  installed catalog templates are classified: 11 dataset-supported templates
  have CLI/API parity and independent result checks; `event_frames` and
  `active_memory_frame_tree_at_event` retain explicit dataset rejection. The
  `peak-memory` report succeeds; `memory-tree` retains its dataset rejection.
- A second required installed-wheel case preserves the original 500,002-event
  workload and its 500,000 + 2 member layout. It verifies the crossing completed
  lifetime, final survivor, pages and point-event results. Both installed cases
  require unchanged input, manifest and member hashes after queries.

Build the wheel from the intended clean checkout using the
[distribution instructions](../../README.md#building-distributions), then run:

```bash
pytest tests/test_fixture_provenance.py
PT_SNAP_ACCEPTANCE_WHEEL="$(realpath dist/<built-wheel>.whl)" \
  pytest tests/core/test_dataset_scale_acceptance.py --junitxml=dataset-acceptance.xml
```

Replace `<built-wheel>` with the actual wheel name. Each installed case creates
its own fresh venv without system packages, installs the exact wheel and runtime
dependencies, clears source `PYTHONPATH`, and checks that the package and
runtime dependencies resolve inside that venv. Dependency installation may use
the package index. Set `PT_SNAP_ACCEPTANCE_WHEELHOUSE` to a directory containing
compatible dependency wheels for an offline `--no-index --find-links` install.
Without `PT_SNAP_ACCEPTANCE_WHEEL`, both installed cases are explicitly skipped;
those skips are not E2E acceptance. The full PR tier uses `pytest -m 'not nightly'`;
the compatibility tier uses `pytest -m 'not slow and not nightly'`.

The million-event installed case writes `acceptance.json` and a
`dataset_acceptance` JUnit property with wheel/source hashes, runtime identity,
event counts and command/query evidence. The short-final-shard case stores its
own evidence separately. `PT_SNAP_ACCEPTANCE_EVIDENCE_DIR` selects a persistent
evidence directory; otherwise pytest temporary directories are used. The
required nightly runner rejects a missing or nonpassing case. Durations are
observational; these installed-wheel cases have no fixed timing or RSS promise.

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
