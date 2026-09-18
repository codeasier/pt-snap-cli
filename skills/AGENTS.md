<!-- Parent: ../AGENTS.md -->

# skills

## Purpose
`skills` contains agent workflows shipped with the repository. The helper
skill is a read-only router by user goal and input type. Setup owns the
only Python-environment mutation boundary and installs after explicit approval;
collection skills guide Ascend NPU snapshot capture without importing
or diagnosing the pickle; diagnostic skills consume installed `pt-snap`
surfaces against existing SnapshotDB data without writes.

## Scope
| Path | Responsibility |
| --- | --- |
| `pt-snap-helper/SKILL.md` | Routes by user goal and input type to the five analysis skills; checks `pt-snap skill list --json`; does not install, import, or persist focus. |
| `pt-snap-setup/SKILL.md` | Detect the active interpreter, verify CLI ownership, request install approval, and re-verify the same environment. |
| `pt-snap-ascend-npu-collect/SKILL.md` | Collect Ascend NPU pickles via native APIs, framework config, or OOM env; inventory artifacts without import or diagnosis. |
| `pt-snap-memory-leak/SKILL.md` | Diagnose end-of-trace live allocations, peak survival, callstack attribution, and release evidence without persisting analysis state. |
| `pt-snap-memory-peak-breakdown/SKILL.md` | Explain active memory at active, allocated, or reserved peak events without leak, fragmentation, or OOM overclaims. |
| `pt-snap-memory-fragmentation/SKILL.md` | Diagnose allocator gaps, runtime segment retention/churn, and fragmentation-consistent pressure without persisting analysis state. |

## Invariants
- Preserve the selected `sys.executable` path for every Python and pip command; canonical paths are only for ownership comparison.
- Never assume Conda, switch environments, use plain `pip`, or install automatically.
- Keep `editable` and PyPI choices explicit, and obtain confirmation before every install attempt.
- Do not add setup steps that write reports or modify pt-snap focus/configuration.
- Collection skills guide capture configuration and artifact inventory only.
  They must not install packages, import or deserialize pickle snapshots,
  persist focus, treat CSV/SVG as SnapshotDB input, or start diagnostic
  queries. Import remains a separate trusted-input decision.
- Diagnostic skills must not install packages, import pickle snapshots, persist
  focus, classify every allocation without a free event as a confirmed leak, or
  turn allocator gaps into definitive fragmentation claims.
- Diagnostic skills pass the database and device explicitly and delegate missing
  tooling to `pt-snap-setup`.
- Helper skills stay read-only navigation. They must not install packages, copy
  skills, import pickle, persist focus, or run diagnostic analysis.
- Prefer packaged query templates for diagnostics. Any raw SQLite fallback must
  document why a template is insufficient and enforce read-only access.

## Packaging
Repository `skills/*/SKILL.md` is the authoring source. Wheel installs read
`src/pt_snap_cli/bundled_skills/`. After adding or editing a skill, copy the
same `SKILL.md` into that packaged tree. `pt-snap skill list`, `install`,
`upgrade`, and `uninstall` manage copies in the shared `.agents/skills`
tree, Claude's independent directories, optional Cursor/Codex extras, or
an explicit `--dir`. After install or upgrade, the host agent must be
restarted.

## Focused Tests
- Run `pytest tests/skills/test_helper_contract.py` after helper-skill changes.
  Static coverage checks routing names, current `--json` capability, skill-list
  availability, and the pickle/focus/install read-only boundary.
- Run `pytest tests/skills/test_setup_contract.py` after setup-skill changes. The current executable test covers active-interpreter path preservation; review the remaining approval and reporting instructions statically.
- Run `pytest tests/skills/test_ascend_npu_collect_contract.py` after
  collection-skill changes. The v1 evaluation harness accepts only
  `diagnostic-readonly` suites, so collection coverage stays in the static
  contract.
- Run `pytest tests/skills` after diagnostic-skill changes. Static contracts
  check current surfaces and safety boundaries; suite/case evaluations cover
  decision paths, structured evidence, and tool-call policy.
