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
| `pt-snap-memory-leak/SKILL.md` | Diagnose end-of-trace live allocations, peak survival, callstack attribution, and release evidence without persisting analysis state. |

## Invariants
- Preserve the selected `sys.executable` path for every Python and pip command; canonical paths are only for ownership comparison.
- Never assume Conda, switch environments, use plain `pip`, or install automatically.
- Keep `editable` and PyPI choices explicit, and obtain confirmation before every install attempt.
- Do not add setup steps that write reports or modify pt-snap focus/configuration.
- Diagnostic skills must not install packages, import pickle snapshots, persist
  focus, or classify every allocation without a free event as a confirmed leak.
- Prefer packaged query templates for diagnostics. Any raw SQLite fallback must
  document why a template is insufficient and enforce read-only access.

## Focused Tests
- Run `pytest tests/skills/test_setup_contract.py` after setup-skill changes. The current executable test covers active-interpreter path preservation; review the remaining approval and reporting instructions statically.
- Run `pytest tests/skills` after diagnostic-skill changes. Static contracts
  check current surfaces and safety boundaries; suite/case evaluations cover
  decision paths, structured evidence, and tool-call policy.
