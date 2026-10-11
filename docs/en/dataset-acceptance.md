# Dataset correctness and default-scale acceptance

Dataset tests distinguish three sources of evidence. Passing a synthetic SQL
fixture is not evidence that a producer, collector, or exporter ran.

## Regular correctness gate

`tests/core/test_dataset_realistic.py` defaults to 20 deterministic seeds in both
compatibility-v1 and native-v2 layouts; the nightly profile extends the same bank
to 200 seeds. The original eight regression seeds and twenty query shapes remain.
Each seed now runs 69–73 query cases per layout (2,896 paired comparisons for the
20-seed bank; 28,864 for 200), covering all eleven dataset-supported templates.
The two standalone-only templates, `event_frames` and
`active_memory_frame_tree_at_event`, have separate explicit rejection tests and
never count as successful differential comparisons.

Both layouts use the same independently generated 80-event history and a
layout-matched standalone SQL oracle. Capacities 2/3/4/5/10/16 produce 5–40
members, including a partial final member. Native fixtures contain real local
stack references, finalized block-reference tables, metadata and member hashes;
they pass the actual native reader validation. Local stack IDs vary by member.
These are synthetic reader/query fixtures, not evidence of native replay/export.
Each shard contains only allocations within its window and carry-in lifetimes;
completed lifetimes do not appear in later windows. Global allocation and
free-completion IDs remain unchanged. Every seed includes address reuse,
preexisting/static blocks, NULL/empty/whitespace stacks, a literal missing-stack
label and separate free-request/completion events. Critical first/last, shard,
request/completion and reuse boundaries are queried under both static policies
and checked independently against generated active IDs, sizes and counters.

Seeded parameters cover legal event ranges, filters, sorting, offset/limit,
`max_rows`, `top_n`, `include_static`, and both `exact_total` settings. Selected
first/last/random member ranges are checked for event/allocation/peak/gap queries.
Empty/full/truncated/beyond-end pages occur in every seed. Many-member cases
assert actual scratch reducer construction, rather than inferring it from shard
count. Input hashes and absence of SQLite write sidecars are checked afterward.

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

The scheduled/manual CI `dataset-acceptance` job runs the 200-seed profile as a
separate required step after its installed-wheel nightly gate. The fail-closed
`.github/scripts/run_differential_acceptance.py` validates exactly 400 distinct
executed test IDs, both formats for all 200 expected seeds, matching JUnit and
per-seed coverage, expected comparison/template counts, zero unexpected errors,
and observed scratch execution. Skips, missing/duplicate cases, stale reports,
or inconsistent evidence fail the job. Its source SHA, summary, log, XML and
compact timeline/coverage/failure JSON are always uploaded as
`differential-acceptance-<commit>`; generated SQLite files are reproducible from the seed
and are not retained in CI artifacts.
This step is source-query acceptance; installed-wheel evidence stays separate.

### Seed profiles and replay

Run these from the intended checkout/interpreter (`PYTHONPATH="$PWD/src"` selects
an isolated worktree without repointing another editable installation):

```bash
# PR/default: 20 seeds, both formats, plus the generator/oracle guard tests
PYTHONPATH="$PWD/src" pytest tests/core/test_dataset_differential_cases.py tests/core/test_dataset_realistic.py

# Nightly: 200 seeds, preserving per-seed evidence and JUnit properties
PYTHONPATH="$PWD/src" PT_SNAP_DIFFERENTIAL_SEEDS=200 pytest \
  tests/core/test_dataset_realistic.py -k seeded \
  --basetemp=test_reports/differential --junitxml=test_reports/differential.xml \
  -o junit_family=xunit1

# Replay one seed and layout (the single-seed override wins over the bank size)
PYTHONPATH="$PWD/src" PT_SNAP_DIFFERENTIAL_SEED=196 pytest \
  tests/core/test_dataset_realistic.py -k 'seeded and v2'
```

`PT_SNAP_DIFFERENTIAL_SEEDS` accepts 1–10,000; `PT_SNAP_DIFFERENTIAL_SEED` accepts
0–2^63−1. Invalid/blank values fail collection, rather than silently skipping work.
The first eight bank entries are the retained regressions, followed by ascending
nonduplicate integers; the 200-seed profile is a strict extension of the default.
The pytest `--basetemp` directory is disposable and is cleared on the next run.

Every successful seed writes `timeline.json` and `coverage.json`, including the
seed, layout, capacity, shard count, comparison count, templates, observed scratch
builds and zero unexpected errors. JUnit carries the same coverage properties.
Failures print the seed/format/parameters and a replay command, and retain
`differential-failure.json` with both full result envelopes or exception details.
One-sided errors and both-sided errors always fail. Expected unsupported-template
rejections are tested separately. Preserve the XML and temporary directory as
CI artifacts when diagnosing a failure.

Terminal-leak parity here applies only to these proved, window-faithful histories,
where every live allocation appears in the terminal shard. It does not erase the
intentional standalone/dataset distinctions for inactive, earlier-only or
unproved histories. `test_dataset_lifecycle_contract.py` retains those contracts
across attached SQL, scratch and bounded fallback. `top_n=0` completeness has
separate empty/static/dynamic/mixed regressions across both layouts and reducers.

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

## Concurrent readers and process interruption

`tests/core/test_dataset_concurrency.py` runs two and four independent readers
in both threads and spawned processes, against the same synthetic dataset and
through both ATTACH and scratch routes. Barriers follow an actual SQLite read
or scratch insert; all readers hold their own query resources concurrently.
Their complete results must agree, scratch directories must be distinct and
removed on normal completion, and source hashes must stay unchanged. This does
not promise that one analyzer or its SQLite connections can be shared by threads.

`tests/test_dataset_signal_boundaries.py` sends actual POSIX signals to the CLI
after a completed scratch insert. Normal completion and SIGINT unwind product
resources and remove scratch. **Current SIGTERM and SIGKILL terminate the process
without that cleanup: the private `pt-snap-lifecycle-*` directory and `derived.db`
remain.** The tests record this limitation, rather than treating test teardown as
product cleanup or claiming issue #252's no-residue kill goal is satisfied. Source
hashes remain unchanged and no partial query output is published. No signal
handler, startup reclamation, or automatic deletion policy is introduced.

These small deterministic tests run in the regular suite (signal cases are POSIX
only). Timeout/error cleanup is separate from abrupt termination: Python-level
unwinding is not evidence that SIGTERM or SIGKILL runs a `finally` block.

`tests/test_dataset_mutation_acceptance.py` pauses a spawned CLI/API query after
its first shard has actually supplied rows or a count, then changes test-owned
members in place. Both the default strong and explicit immutable cache modes must
reject the changed generation without publishing partial rows/counts. Unchanged
runs succeed with independently expected results. Hash-work assertions quantify
compatibility-v1 cold/warm queries: default queries scan each manifest/member
three/two times respectively (admission plus the new final check). Explicit POSIX
immutable queries scan members once/zero times and the manifest twice/zero times.
The final check itself adds one full scan in default mode, zero in metadata-only
immutable mode, and shares the query's deadline. Non-POSIX immutable requests do
not reuse admission based on creation times: both cold and warm queries scan each
member twice and the manifest three times, including a full final hash guard.
Default strong warm reuse still works on non-POSIX systems. The tests exercise
this conservative policy through a resolver-local simulated non-POSIX case too;
that simulation is not evidence of actual Windows execution. These are work-count assertions,
not fixed wall-time or RSS promises. The guard detects these controlled mutations;
it does not create an atomic filesystem snapshot or prove all change-and-restore
races impossible.
