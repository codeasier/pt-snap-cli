# CI and Release Lifecycles

Parent scope: [automation](../AGENTS.md).

## Test Workflow

`test.yml` runs for main pushes, main-targeted PR opened/synchronize/reopened/edited
events, `workflow_call`, nightly at 03:17 UTC, and `workflow_dispatch`. Provenance,
lint, browser and Python test-matrix jobs are independent. Checkouts use the PR
head SHA or the triggering SHA; manual dispatch checks the selected ref's SHA.
Concurrency is keyed by GitHub ref and superseded runs are cancelled.

| Job/step | Gate |
| --- | --- |
| Snapshot provenance | Full Git history; base/head comparison; PR decision required only in PR mode |
| Lint & Format | Python 3.13, editable dev install, Ruff, Black, basedpyright with the selected interpreter |
| Compatibility matrix | Python 3.10–3.12; fixture provenance first, then `pytest -m "not slow and not nightly"` |
| Full PR test tier | Python 3.13; `pytest -m "not nightly"` with branch coverage, preserving the existing slow tests |
| Overall coverage | `pyproject.toml` fail-under 90 with branches enabled |
| Critical runtime coverage | Import backend 90; simulated allocator 88; snapshot mutator 84, checked independently |
| Python 3.13 packaging | Upload coverage, build wheel, run offline clean-wheel skill/CLI acceptance including both sharded formats |
| Nightly/manual dataset acceptance | Python 3.13; provenance, wheel build and audit, then `nightly` tests including the required installed-wheel CLI/API test |

Million-event deep-offset pagination tests are marked `slow`; their small
pagination contracts still run across the compatibility matrix.

Coverage reporting writes `.coverage`/`coverage.xml`; building writes `dist/` and
intermediates. Dependency installation/build isolation may access the network.
The [acceptance script](../scripts/clean_wheel_agent_acceptance.py) uses temporary
paths but imports a reviewed executable fixture. These are more than YAML checks.

The nightly/manual job invokes `run_dataset_acceptance.py` with the single built
wheel. All `nightly` tests are selected automatically; the installed-wheel case
must appear exactly once. New mandatory gates also add their complete pytest
node IDs to `REQUIRED_TEST_NODES` in that runner. Do not register absent future
files. Missing wheels, missing/empty JUnit, missing required nodes, duplicate
identities, any skipped/failed/error test, or evidence for a different wheel fail
the gate. It uploads the pytest log, JUnit (including the test's evidence), and a
summary with complete executed/required test node IDs, actual checkout SHA and wheel
SHA-256, even after failure. `PT_SNAP_ACCEPTANCE_EVIDENCE_DIR` is available for
additional test-owned artifacts. Local invocation:

```bash
python .github/scripts/run_dataset_acceptance.py \
  --wheel dist/<built-wheel>.whl --output-dir .tmp/dataset-acceptance
```

The required installed-wheel case creates a clean venv without system packages
and runs its actual `pt-snap` console script from isolated HOME/CWD. Its trusted,
test-owned input has exactly 1,000,000 events; the default exporter produces two
full 500,000-event shards. All installed catalog entries are classified: currently
11 dataset-supported templates succeed with installed CLI/API equivalence and
independent known-result checks, while `event_frames` and
`active_memory_frame_tree_at_event` return explicit unsupported-dataset errors.
Both report commands run: `peak-memory` succeeds and `memory-tree` preserves the
corresponding dataset rejection. The allocation/free-request/free-completion
boundary assertions remain covered, alongside static occupancy, offset pages,
terminal survivors and unchanged source/manifest/member hashes. A second required
nightly case separately imports 500,002 events and proves the original final
short shard has exactly two real events, with the crossing completed lifetime
and the final survivor. Its evidence is stored in its own subdirectory so the
two gates cannot overwrite each other's command logs. This adds one half-million
event import plus five query subprocesses to the nightly job. Existing
synthetic scale/default-budget regressions remain separate source-level tests.
`PT_SNAP_ACCEPTANCE_WHEELHOUSE` optionally supplies dependencies for an offline
clean-venv install. Timings are recorded without machine-speed thresholds; this
does not claim live agents, live hardware capture or upstream GUI interoperability.

The ordinary PR tier excludes `nightly` tests; the required nightly/manual runner
must never skip them. Manually dispatch the exact published branch/commit and
verify the run's head SHA and summary; a PR run alone is not nightly evidence.

## Release Workflow

`release.yml` triggers on `v*` tag pushes and enforces:

`quality` → `build` → `publish` → `github-release`.

- `quality` invokes `./.github/workflows/test.yml` at the tagged commit.
- `build` fetches full history for setuptools-scm, builds sdist/wheel, verifies
  the installed wheel's version matches the tag, runs `pt-snap --version`, and
  extracts a nonempty matching `CHANGELOG.md` section before uploading artifacts.
- `publish` uses the protected `pypi` environment and OIDC trusted publishing.
- `github-release` publishes the same distributions and extracted notes only
  after PyPI publication succeeds.

Do not substitute a different commit's CI result or publish before version/notes
validation. For non-PR provenance checks, tag runs compare against the prior tag
(or root commit fallback); pushes use the before SHA with a root fallback.

## Verification

Review `pyproject.toml`, both workflow YAMLs, the provenance/acceptance scripts and
`tests/test_release_workflow.py` together when changing execution order. Validate
YAML and run `pytest tests/test_governance.py tests/test_release_workflow.py
tests/test_ci_tiers.py tests/test_dataset_acceptance_runner.py tests/test_wheel_audit.py` from
the repository root. Full CI tests the matrix and installed wheel; static tests
do not prove a release environment is configured or a publication occurred.

### Required paired differential profile

The scheduled/manual `dataset-acceptance` job also runs
`run_differential_acceptance.py --seed-count 200` after the installed-wheel
nightly gate. This separate source-query step is required, with no skip or
continue-on-error escape. Its JUnit report must contain exactly 400 distinct
seed/format test IDs (200 per v1/v2), matching all per-seed coverage artifacts,
expected query counts/templates, zero unexpected errors and actual scratch use.
A single-seed environment override is removed by the runner. Logs, source SHA,
summary, JUnit and compact timeline/coverage/failure JSON are always uploaded from
`.tmp/differential-acceptance/`; regenerated SQLite files stay out of stored artifacts. The ordinary PR matrix retains the default
20-seed profile. This does not make the differential step installed-wheel or
upstream-producer evidence.
