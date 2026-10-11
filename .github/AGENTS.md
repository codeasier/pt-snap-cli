# Repository Automation

Parent scope: [repository](../AGENTS.md).

| Path | Contract |
| --- | --- |
| [workflows](workflows/AGENTS.md) | CI quality gates and tag-driven release ordering |
| [ISSUE_TEMPLATE](ISSUE_TEMPLATE/AGENTS.md) | Numbered issue forms and chooser configuration |
| `pull_request_template.md` | Default PR template and machine-parsed snapshot decision labels |
| `scripts/check_snapshot_provenance.py` | Base/head Git-blob comparison and PR declaration validation |
| `scripts/clean_wheel_agent_acceptance.py` | Supplied wheel acceptance in temporary home/CWD/venv |
| `scripts/run_differential_acceptance.py` | Source-query 200-seed/v1-v2 acceptance with exact executed identities and coverage evidence |
| `scripts/run_dataset_acceptance.py` | Required installed-wheel dataset test with fail-closed JUnit and artifact evidence |

## Provenance Guard

The guard compares the supplied base/head commits, not just working-tree content.
Changes anywhere under `src/pt_snap_cli/snapshot/`, including `AGENTS.md`, trigger
the PR decision requirement. Supply exactly one `Snapshot provenance decision:`
with `updated` or `no-update`. `updated` requires new nonblank provenance content;
`no-update` requires one specific `Snapshot provenance no-update reason:` and no
provenance-file change. Placeholder text and duplicate declarations fail.

Existing provenance lines cannot be rewritten, reordered or deleted. This
content check also runs on main pushes and tag releases. Preserve PR `edited`
events so correcting a declaration can rerun CI.

## Installed-Wheel Acceptance

The acceptance script audits a supplied wheel against source and validates the
reviewed fixture manifest before installing or importing. It installs offline
into a temporary venv with system dependencies available by default. Supplying
`--wheelhouse` instead installs dependencies offline into a venv without system
packages and verifies their installed paths too. It verifies that `pt_snap_cli`
resolves inside the venv, clears source/catalog/focus/resource-limit overrides,
disables user site packages, and uses temporary HOME/CWD for skill installation
and import-created focus.

It then checks help, bundled catalog/install status, capabilities, trusted fixture
import/reuse, overview and a peak query. This is executable CLI acceptance, not a
live model evaluation. `--events-per-slice 4096` adds native-v2 and compatibility-v1
sharded imports/reuse, directory/manifest discovery, installed helper/peak skill
guidance, and real peak/cross-shard event parity with the standalone CLI. It
requires at least two physical slices on the selected device and verifies that
explicit dataset operations do not change focus. The script accepts only the
expected committed `snapshot_with_empty_cache.pkl` path, rejects an unhydrated
pointer, and runs the provenance gate itself; also run fixture provenance tests
before acceptance. Its output explicitly distinguishes offline CLI execution,
stored-baseline grading (not run here), and live-agent execution (not run).

Harness changes use `pytest tests/test_clean_wheel_agent_acceptance.py` plus an
actual audited-wheel invocation; mocked guard tests alone are not acceptance.

## Change Together

Keep guard labels, the default PR template, and workflow inputs aligned. Run
`pytest tests/test_governance.py tests/test_release_workflow.py` from the repository
root for governance/wiring changes. Read scripts before invoking them: the guard
is read-only, while wheel acceptance creates an environment and loads trusted
pickle data. Workflow/package changes also use the source packaging contracts.
