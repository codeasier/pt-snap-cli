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
| Compatibility matrix | Python 3.10–3.12; fixture provenance first, then `pytest -m "not slow"` |
| Full test tier | Python 3.13; fixture provenance first, then all tests with branch coverage, including slow tests |
| Overall coverage | `pyproject.toml` fail-under 90 with branches enabled |
| Critical runtime coverage | Import backend 90; simulated allocator 88; snapshot mutator 84, checked independently |
| Python 3.13 packaging | Upload coverage, build wheel, run clean-wheel Agent acceptance |
| Nightly/manual dataset acceptance | Python 3.13; provenance, wheel build and audit, then required installed-wheel CLI/API test |

Million-event deep-offset pagination tests are marked `slow`; their small
pagination contracts still run across the compatibility matrix.

Coverage reporting writes `.coverage`/`coverage.xml`; building writes `dist/` and
intermediates. Dependency installation/build isolation may access the network.
The [acceptance script](../scripts/clean_wheel_agent_acceptance.py) uses temporary
paths but imports a reviewed executable fixture. These are more than YAML checks.

The nightly/manual job invokes `run_dataset_acceptance.py` with the single built
wheel. Missing wheels, missing/empty JUnit, skipped/failed tests, extra test cases,
or evidence for a different wheel fail the gate. It uploads the pytest log, JUnit
(including the test's evidence), and a summary with actual checkout SHA and wheel
SHA-256, even after failure. `PT_SNAP_ACCEPTANCE_EVIDENCE_DIR` is available for
additional test-owned artifacts. Local invocation:

```bash
python .github/scripts/run_dataset_acceptance.py \
  --wheel dist/<built-wheel>.whl --output-dir .tmp/dataset-acceptance
```

This tier initially exercises the existing 500,002-event `pip --target` acceptance
test. It does not claim a clean venv, two full 500,000-event shards, complete CLI
template coverage, live agents or upstream GUI interoperability. The ordinary
full suite may still skip this opt-in wheel test; the required nightly/manual
runner must never do so. Manually dispatch the exact published branch/commit and
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
