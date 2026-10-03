# Skill Contracts and Local Evaluations

Parent scope: [test contracts](../AGENTS.md).
Authored workflows: [skills](../../skills/AGENTS.md).

## Harness and Suites

| Path | Responsibility |
| --- | --- |
| `schemas/`, `harness/descriptors.py` | Strict, versioned declarative suite/case contracts |
| `harness/fixtures.py`, `gateway.py` | Synthetic SnapshotDB construction and semantic tool-call policy |
| `harness/grader.py`, `runners.py` | Normalized run records, deterministic grades and runner adapters |
| `harness/artifacts.py`, `metrics.py` | Local run artifacts, call/output/error/task metrics |
| `suites/pt-snap-agent-e2e/` | CLI discovery/recovery and acceptance branches, recorded baseline runs |
| `suites/pt-snap-memory-leak/` | Address reuse, pending free, allocator cache and pickle refusal |
| `suites/pt-snap-memory-leak-iterations/` | Trusted iteration markers, missing markers, multiple cleanups and incomplete capture |
| `README.md`, `__main__.py` | Harness formats and validate/grade/baseline command entry |
| `test_*_contract.py` | Static and executable contracts for authored skill content and routing indexes |

## Test Routing and Policy

- `test_helper_contract.py` / `test_helper_availability.py` cover routing and the
  difference between scoped filesystem status and host-loaded skills.
- `test_preflight_contract.py` covers capabilities/overview order, full-result
  reuse and nested metadata status handling across diagnostic skills.
- `test_setup_contract.py` covers active-interpreter preservation; remaining
  approval instructions also need static review. `test_ascend_npu_collect_contract.py`
  verifies capture-only workflow boundaries without hardware execution.
- Memory leak/peak/fragmentation and iteration contract modules check shipped
  instructions. Harness unit tests verify descriptors, fixtures, gateway and
  grading; static contract success is not evidence of a live model run.

Keep YAML definitions declarative: no embedded shell, Python, Jinja or executable
expressions. Diagnostic runs use generated databases and never receive pickle
fixtures. The `agent-cli` profile may require semantic `pt_snap.import`, but the
evaluation still must not materialize pickle inputs. Forbidden operations are
hard failures; grade normalized semantics rather than shell spelling.

Live model execution is explicit and local, outside normal pytest. Keep generated
databases, transcripts, grades and reports in temporary paths or `.skill-evals/`.
Baseline aggregation reads recorded runs; it does not execute an agent.

## Focused Commands

From the repository root:

```bash
pytest tests/skills
python -m tests.skills validate tests/skills/suites/pt-snap-memory-leak-iterations/suite.yaml
python -m tests.skills baseline tests/skills/suites/pt-snap-agent-e2e/suite.yaml tests/skills/suites/pt-snap-agent-e2e/baselines/target
```

`grade` and `baseline` can write reports when given `--output`; choose an ignored
or temporary location. Authored skill changes also need bundled-copy parity tests
and actual CLI/query tests for the commands the instructions teach.
