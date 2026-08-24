# Local Skill Evaluation

`tests/skills` evaluates repository agent skills without requiring a model,
network access, or GitHub CI. Live-agent adapters can use the same descriptors,
tool gateway, run record, and deterministic grader from a fresh local session.

## Descriptor Model

Each suite has one `suite.yaml` and explicit case references under
`suites/<skill>/`. The versioned contracts are documented in `schemas/` and
enforced by `harness/descriptors.py` with unknown fields rejected.

- A suite identifies the `SKILL.md`, result classifications, scored objectives,
  required decision branches, sandbox defaults, semantic tool policy, and cases.
  Runner defaults (`runner`, `repetitions`, `timeout_seconds`, `sandbox`) are
  validated and exposed as typed values on the loaded suite so adapters can
  enforce them.
- A case identifies its prompt, optional synthetic SnapshotDB, covered branches,
  required tool actions, partial ordering, forbidden actions, oracle facts,
  classification bounds, unknowns, and claim-to-tool evidence links. Actions may
  declare `expect_output`, a mapping that must appear in the matched call's
  recorded output before the action counts as matched. Cases may cap the total
  call count with `expected_tools.max_calls`; zero enforces refusal-only cases.
- Descriptor paths are repository-relative and cannot contain `..`. Fixture
  mount paths must be normalized absolute POSIX paths under `/fixtures/`.
- Diagnostic fixtures are declarative SQLite databases. Pickle inputs are never
  materialized or exposed to a diagnostic runner.

Validate a suite locally:

```bash
python -m tests.skills validate tests/skills/suites/pt-snap-memory-leak/suite.yaml
```

## Tool Gateway

Agent adapters should expose only semantic operations through
`RecordingToolGateway`. The gateway records successful, failed, and denied
attempts and enforces the suite allowlist and call budget. Adapters remain
responsible for process-level isolation: a fresh temporary working directory,
an isolated `HOME`, no network, a read-only project, read-only fixture mounts,
and cleared focus environment variables.

The gateway operation names are transport-independent. An adapter may implement
them with a CLI wrapper, MCP server, or another local agent tool, but raw command
spelling is not part of the grading contract.

## Run Record

A runner submits JSON with the following shape:

```json
{
  "tool_calls": [
    {
      "id": "call-1",
      "operation": "pt_snap.metadata",
      "arguments": {"database": "/fixtures/cache.db", "json": true},
      "status": "success",
      "output": {"status": "unavailable", "reason": "metadata_missing", "metadata": null}
    }
  ],
  "result": {
    "classification": "allocator/cache effect",
    "facts": {"device_id": 0},
    "claims": [
      {"id": "device_id", "evidence_call_ids": ["call-1"]}
    ],
    "unknowns": ["repeated-capture evidence"]
  },
  "final_response": "Evidence-backed user-facing response"
}
```

Grade a recorded run and optionally write local artifacts:

```bash
python -m tests.skills grade \
  tests/skills/suites/pt-snap-memory-leak/suite.yaml \
  allocator-cache run.json --output .skill-evals/runs/example
```

Safety objectives are hard gates. Scored objectives use normalized operation
arguments, required output evidence, partial ordering, tool budgets (suite-wide
and per case), oracle facts, classifications, required unknowns, and evidence
call IDs. Runs that omit required result fields or submit malformed result
shapes also hard-fail. Formatting and prose style receive no deterministic
score.

Generated transcripts and reports belong under `.skill-evals/`, which is
ignored by Git. Normal `pytest` runs never invoke a live model.
