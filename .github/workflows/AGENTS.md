# CI and Release Lifecycles

Parent scope: [automation](../AGENTS.md).

## Test Workflow

`test.yml` runs for main pushes, main-targeted PR opened/synchronize/reopened/edited
events, and `workflow_call`. Provenance, lint and Python test-matrix jobs are
independent. Concurrency is keyed by GitHub ref and superseded runs are cancelled.

| Job/step | Gate |
| --- | --- |
| Snapshot provenance | Full Git history; base/head comparison; PR decision required only in PR mode |
| Lint & Format | Python 3.13, editable dev install, Ruff, Black, basedpyright with the selected interpreter |
| Test matrix | Python 3.10–3.13; fixture provenance first, then pytest with branch coverage |
| Overall coverage | `pyproject.toml` fail-under 90 with branches enabled |
| Critical runtime coverage | Import backend 90; simulated allocator 88; snapshot mutator 84, checked independently |
| Python 3.13 packaging | Upload coverage, build wheel, run clean-wheel Agent acceptance |

Coverage reporting writes `.coverage`/`coverage.xml`; building writes `dist/` and
intermediates. Dependency installation/build isolation may access the network.
The [acceptance script](../scripts/clean_wheel_agent_acceptance.py) uses temporary
paths but imports a reviewed executable fixture. These are more than YAML checks.

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
YAML and run `pytest tests/test_governance.py tests/test_release_workflow.py` from
the repository root. Full CI tests the matrix and installed wheel; static tests
do not prove a release environment is configured or a publication occurred.
