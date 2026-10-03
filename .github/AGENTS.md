# Repository Automation

Parent scope: [repository](../AGENTS.md).

| Path | Contract |
| --- | --- |
| [workflows](workflows/AGENTS.md) | CI quality gates and tag-driven release ordering |
| [ISSUE_TEMPLATE](ISSUE_TEMPLATE/AGENTS.md) | Numbered issue forms and chooser configuration |
| `pull_request_template.md` | Default PR template and machine-parsed snapshot decision labels |
| `scripts/check_snapshot_provenance.py` | Base/head Git-blob comparison and PR declaration validation |
| `scripts/clean_wheel_agent_acceptance.py` | Supplied wheel acceptance in temporary home/CWD/venv |

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

The acceptance script installs a supplied wheel offline into a temporary venv
with system dependencies available, and verifies that `pt_snap_cli` resolves
inside that venv. It clears source/catalog/focus environment overrides and uses
temporary HOME/CWD for helper installation and import-created focus.

It then checks help, bundled catalog/install status, capabilities, trusted fixture
import/reuse, overview and a peak query. This is executable CLI acceptance, not a
live model evaluation. The script accepts only the expected committed
`snapshot_with_empty_cache.pkl` path; run fixture provenance verification first.

## Change Together

Keep guard labels, the default PR template, and workflow inputs aligned. Run
`pytest tests/test_governance.py tests/test_release_workflow.py` from the repository
root for governance/wiring changes. Read scripts before invoking them: the guard
is read-only, while wheel acceptance creates an environment and loads trusted
pickle data. Workflow/package changes also use the source packaging contracts.
