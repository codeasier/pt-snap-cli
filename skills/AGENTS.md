<!-- Parent: ../AGENTS.md -->

# skills

## Purpose
`skills` contains agent workflows shipped with the repository. Setup owns the
only Python-environment mutation boundary; diagnostic skills consume installed
`pt-snap` surfaces and keep snapshot analysis read-only.

## Scope
| Path | Responsibility |
| --- | --- |
| `pt-snap-setup/SKILL.md` | Detect the active interpreter, verify CLI ownership, request install approval, and re-verify the same environment. |
| `pt-snap-memory-peak-breakdown/SKILL.md` | Explain active memory at active, allocated, or reserved peak events without leak, fragmentation, or OOM overclaims. |
| `pt-snap-memory-fragmentation/SKILL.md` | Diagnose allocator gaps, runtime segment retention/churn, and fragmentation-consistent pressure without persisting analysis state. |

## Invariants
- Preserve the selected `sys.executable` path for every Python and pip command; canonical paths are only for ownership comparison.
- Never assume Conda, switch environments, use plain `pip`, or install automatically.
- Keep `editable` and PyPI choices explicit, and obtain confirmation before every install attempt.
- Do not add setup steps that write reports or modify pt-snap focus/configuration.
- Keep memory diagnostics SnapshotDB-only and read-only; pass database/device explicitly and delegate missing tooling to `pt-snap-setup`.
- Diagnostic skills must not install packages, import pickle snapshots, persist
  focus, or turn allocator gaps into definitive fragmentation claims.
- Prefer packaged query templates for diagnostics. Any raw SQLite fallback must
  document why a template is insufficient and enforce read-only access.

## Focused Tests
- Run `pytest tests/test_setup_skill.py` after setup-skill changes. The current executable test covers active-interpreter path preservation; review the remaining approval and reporting instructions statically.
- Run `pytest tests/test_memory_peak_breakdown_skill.py` after peak-breakdown skill changes; it locks command/template references, range fallback, and attribution caveats.
- Run `pytest tests/test_memory_fragmentation_skill.py` after fragmentation-skill
  changes; it checks current command/template references, read-only boundaries,
  runtime segment coverage, and conservative classifications.
