<!-- Parent: ../AGENTS.md -->

# skill evaluations

## Purpose
`tests/skills` contains static skill contracts and a local-first evaluation
harness for versioned suite/case descriptors, synthetic SnapshotDB scenarios,
tool-call traces, deterministic grading, and runner adapters.

## Scope
| Path | Responsibility |
| --- | --- |
| `schemas/` | Human-readable v1 suite and case descriptor contracts. |
| `harness/` | Strict descriptor loading, synthetic fixture construction, trace grading, runner protocols, and local artifacts. |
| `suites/` | Reviewed skill-specific objectives, decision branches, cases, and declarative SQLite fixtures. |
| `README.md` | Descriptor, gateway, run-record, grading, and local command reference. |
| `test_*_contract.py` | Static and executable contracts for shipped `SKILL.md` files. |

## Invariants
- Keep evaluation definitions declarative; do not embed shell, Python, Jinja, or arbitrary expressions in YAML.
- Diagnostic suites use generated SnapshotDB files only. Never expose, import, or deserialize pickle fixtures in an agent run.
- Treat forbidden operations as hard failures and grade allowed tool calls by normalized semantics rather than shell text.
- Keep live model execution local and explicit. Normal pytest coverage must not require network access, provider credentials, or a model runtime.
- Write generated transcripts, databases, scores, and reports only under temporary directories or the ignored `.skill-evals/` directory.

## Focused Tests
- Run `pytest tests/skills` for harness, descriptor, fixture, grader, or skill contract changes.
- Run `python -m tests.skills validate tests/skills/suites/<skill>/suite.yaml` after editing a suite or case descriptor.
