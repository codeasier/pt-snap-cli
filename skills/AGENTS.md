# Authored Agent Workflows

Parent scope: [repository](../AGENTS.md).

## Workflow Ownership

| Skill | Boundary |
| --- | --- |
| [pt-snap-helper](pt-snap-helper/SKILL.md) | Routes by user goal and input type; read-only availability/host-loading checks and diagnostic preflight handoff |
| [pt-snap-setup](pt-snap-setup/SKILL.md) | Active interpreter/CLI ownership, explicitly approved package installation, re-verification |
| [pt-snap-ascend-npu-collect](pt-snap-ascend-npu-collect/SKILL.md) | Collect Ascend NPU pickles through capture configuration and artifact inventory |
| [pt-snap-memory-leak](pt-snap-memory-leak/SKILL.md) | End-live retention candidates, peak survival, callstack/release/iteration evidence |
| [pt-snap-memory-peak-breakdown](pt-snap-memory-peak-breakdown/SKILL.md) | Blocks and allocation stacks live at selected metric peaks |
| [pt-snap-memory-fragmentation](pt-snap-memory-fragmentation/SKILL.md) | Allocator gaps, segment retention/churn and fragmentation-consistent pressure |

## Mutation and Handoff Boundaries

- Setup preserves the selected `sys.executable` for every Python/pip command;
  canonical paths are for ownership comparison only. Do not assume Conda or
  switch environments. Explain PyPI/editable choices and obtain confirmation
  for each install attempt. Setup does not write focus/config or analysis reports.
- Collection skills guide capture configuration and list artifacts; they do not install,
  deserialize/import snapshots, persist focus or diagnose CSV/SVG/pickle inputs.
  Trusted import remains a separate decision.
- Helper distinguishes catalog source, inspected installation locations and
  host loading. Default `missing` does not mean unavailable in a custom directory
  or already-loaded host. `source_dir` proves neither installation nor loading.
  Helper may orient with read-only probes; it does not diagnose or copy/install.
- Diagnostic skills use explicit database/device and installed CLI surfaces.
  Missing tooling routes to setup. They do not mutate focus, import pickle or
  install packages. Prefer `--json` on supported commands.

## Diagnostic Evidence Contracts

- Start with full `capabilities --json` and `overview <db> --json`. Reuse only
  complete compatible results for the same environment/CLI and resolved database;
  apply the skill's identity/freshness checks. Read `import_metadata.status`,
  not just exit status or outer `ok`; preserve stop and legacy-data rules.
- Validate required query contracts from the catalog rather than probing each
  template again. A missing required template or failed probe is not permission
  to substitute raw SQL. Any separately justified fallback must stay read-only.
- Ranked leak windows replace earlier windows when widened; they are not offset
  pages to sum. Respect `top_n`, output caps and completeness flags.
- Peak/end survival requires complete per-block enumeration in the same database
  and device, matching `(id, allocEventId)` rather than address/callstack alone.
- Per-step claims need trusted iteration boundaries, count and source. Allocation
  events, cleanup events and trace duration are not iteration counts; insufficient
  evidence stays unknown. End-live allocations are candidates, not proven leaks;
  allocator gaps alone do not establish fragmentation or OOM causality.

## Packaging and Validation

Author `skills/<name>/SKILL.md` and mirror it identically into
`src/pt_snap_cli/bundled_skills/<name>/SKILL.md`. Catalog/destination/status and
uninstall preflight rules belong to [SkillService](../src/pt_snap_cli/core/AGENTS.md).
Changed installed skill files require host restart; disk status is not proof of
the current session's loaded content.

Run `pytest tests/test_bundled_skills.py tests/skills` from the repository root.
Use the [evaluation guide](../tests/skills/AGENTS.md) for focused contracts and
declarative suites. New instructions teaching CLI/query behavior also need the
owning executable tests; deterministic grading is distinct from live-model or
Ascend hardware validation.
