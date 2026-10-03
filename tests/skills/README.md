# Local Skill Evaluation

`tests/skills` evaluates repository agent skills without requiring a model,
network access, or GitHub CI. Live-agent adapters can use the same descriptors,
tool gateway, run record, and deterministic grader from a fresh local session.

## Descriptor Model

Each suite has one `suite.yaml` and explicit case references under
`suites/<skill>/`. The versioned contracts are documented in `schemas/` and
enforced by `harness/descriptors.py` with unknown fields rejected.

- A suite identifies the skill or evaluation contract, result classifications,
  scored objectives, required decision branches, sandbox defaults, semantic tool
  policy, and cases. Supported profiles are `diagnostic-readonly` and
  `agent-cli`. Runner defaults (`runner`, `repetitions`, `timeout_seconds`,
  `sandbox`) are validated and exposed as typed values on the loaded suite so
  adapters can enforce them.
- A case identifies its prompt, optional synthetic SnapshotDB, covered branches,
  required tool actions, partial ordering, forbidden actions, oracle facts,
  classification bounds, unknowns, and claim-to-tool evidence links. Actions may
  declare `expect_output`, a mapping that must appear in the matched call's
  recorded output before the action counts as matched. Actions may also declare
  `status` (`success` or `error`; default `success`) so recovery cases can
  require structured failures. Nested mappings and row lists in `expect_output`
  are matched recursively. Cases may cap the total call count with
  `expected_tools.max_calls`; zero enforces refusal-only cases.
- Descriptor paths are repository-relative and cannot contain `..`. Fixture
  mount paths must be unique, normalized absolute POSIX paths under `/fixtures/`.
  `additional_fixtures` can mount more read-only synthetic SnapshotDBs when a
  scenario depends on competing databases or devices. A semantic operation that
  must publish an artifact may declare an explicit `writable_outputs` path under
  `/outputs/`; it never makes project or fixture mounts writable.
- Diagnostic fixtures are declarative SQLite databases. Pickle inputs are never
  materialized or exposed to a diagnostic runner.

Validate a suite locally:

```bash
python -m tests.skills validate tests/skills/suites/pt-snap-memory-leak/suite.yaml
python -m tests.skills validate tests/skills/suites/pt-snap-agent-e2e/suite.yaml
```

## Tool Gateway

Agent adapters should expose only semantic operations through
`RecordingToolGateway`. The gateway records successful, failed, and denied
attempts and enforces the suite allowlist and call budget. Adapters should
raise `StructuredToolError` when a failed CLI call still has a JSON envelope;
the gateway retains that envelope in the graded trace. Adapters remain
responsible for process-level isolation: a fresh temporary working directory,
an isolated `HOME`, no network, a read-only project, read-only fixture mounts,
and cleared focus environment variables.

The gateway operation names are transport-independent. An adapter may implement
them with a CLI wrapper or another local agent tool, but raw command
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

## Final-answer minimum validity (issue #186)

Suite and case descriptors may opt in with a top-level `final_answer` block:

```yaml
final_answer:
  require_nonempty: true
  required_conclusions:
    database: [/fixtures/target.db]
    device: [device 1, device_id=1]
```

`require_nonempty` is a boolean, defaulting to `true` when the block is present.
`required_conclusions` defaults to `{}` and maps conclusion names to non-empty
lists of accepted non-empty phrases. Each named conclusion needs at least one
phrase in **`final_response` itself**, after Unicode case folding and whitespace
collapsing. This is literal substring matching, not a semantic judge: it does not
validate arbitrary paraphrases, negation, factual truth, or prose style. Authors
should declare meaningful phrases and accepted language variants; a non-empty
check alone deliberately accepts unrelated text.

- A case block **replaces the entire suite block**, rather than merging it.
  An omitted case block inherits the suite policy. With both omitted, legacy v1
  grading remains unchanged and the answer check reports `checked: false`.
- `{require_nonempty: false}` with no required conclusions explicitly disables
  the check for a case. `{}` enables just the default non-empty check. Required
  conclusions still apply if `require_nonempty` is false.
- Enabled checks apply to every classification, including correct refusals,
  blocked and unavailable results. Facts/claims in `result` cannot substitute for
  conclusions that the user must see in the final answer.
- Omitted `final_response` still defaults to `""` for legacy records. An explicit
  null, boolean, number, list or mapping is rejected by the record loader; none
  is converted to text. Unknown policy fields and malformed policy types are
  rejected by the descriptor loader.

Answer failure is a hard gate on overall `passed`. The existing `score` remains
the trace/result objective score (so it may be 100 even when `passed` is false).
Grade JSON, `score.json` artifacts and each baseline case separately expose
`trace_result` (`passed`, `score`) and `final_answer` (`checked`, nullable `passed`,
`violations`). An unchecked answer is not evidence of answer quality.
`execution_evidence.runner_execution_verified: false` explicitly records that
grading cannot verify runner execution. `grade` only grades a supplied record;
`baseline` only rescores recorded baselines. Suite runner defaults, recorded tool
calls and a perfect grade are not proof of a fresh agent/model run. Any actual
runner execution evidence must be collected separately by the adapter.

The Agent CLI suite opts in for all ten cases with named minimum conclusions;
its target records remain unchanged. Deterministic mutation tests reject empty,
whitespace-only and unrelated answers without live models or cloud judges.

### 最终答复最低有效性（中文）

suite 和 case 可用上述顶层 `final_answer` 声明确定性检查。
声明块存在时，布尔字段 `require_nonempty` 默认 `true`；
`required_conclusions` 默认 `{}`，将结论名称映射到非空候选短语列表。
每项结论都必须在 **`final_response` 本身**匹配至少一个短语；匹配先进行
Unicode 大小写折叠并合并空白，再检查字面子串。这不判断任意同义改写、否定关系、
事实真伪或文风；作者应声明有意义的短语和可接受的语言变体。仅非空检查仍允许无关文本。

- case 声明**整块替换** suite 策略，不逐字段合并；case 省略则继承 suite。
  两处均省略时保持旧版 v1 评分行为，报告 `checked: false`。
- `{require_nonempty: false}` 且无必需结论时显式关闭检查；`{}` 启用默认非空检查。
  即使 `require_nonempty: false`，已声明的必需结论仍会检查。
- 已启用的检查适用于所有分类，包括正确拒绝、blocked 和 unavailable；
  `result` 的 facts/claims 不能代替用户应在最终答复看到的结论。
- 旧记录省略 `final_response` 仍默认为空串；显式 null、布尔、数字、列表或映射
  会被加载器拒绝，不会转成字符串。策略未知字段和类型错误也会被拒绝。

答复检查失败会使整体 `passed` 为 false；原有 `score` 仍是 trace/result 目标分数，
因此可能同时出现 100 分和整体不通过。grade JSON、`score.json` 和 baseline 各案例
分别报告 `trace_result`（通过状态和分数）与 `final_answer`（是否检查、可为空的通过
状态和违规原因）。未检查不代表答复合格。
`execution_evidence.runner_execution_verified: false` 表明评分无法验证真实 runner
执行：`grade` 只评分输入记录，`baseline` 只重评历史记录。suite runner 配置、记录的
工具调用和满分都不能证明新执行了 agent/model；真实执行证据需由 adapter 另行采集。
Agent CLI 的全部十个案例已启用命名结论检查，target 记录未改写；确定性变异测试覆盖
空串、纯空白和无关答复，无需实时模型或云端 judge。

## Agent CLI baseline (issue #136)

`tests/skills/suites/pt-snap-agent-e2e/` grades the issue #136 end-to-end
scenarios plus sibling-database recovery when focus points at a missing file.
It is an `agent-cli` evaluation contract, not a shipped skill. Recorded runs
live under `baselines/pre-change/` (current CLI-only behavior) and
`baselines/target/` (the post-change Agent-friendly contract). The comparison
requires higher task success, lower error-conclusion rate, and bounded mean
calls/output; recovery cases may use extra calls when a structured failure must
be corrected.

Comparison metrics are task success rate, mean call count, mean output bytes,
and error-conclusion rate:

```bash
python -m tests.skills baseline \
  tests/skills/suites/pt-snap-agent-e2e/suite.yaml \
  tests/skills/suites/pt-snap-agent-e2e/baselines/pre-change \
  --output .skill-evals/baselines/pre-change.json
```

Diagnostic fixtures remain declarative SQLite databases. The import scenario
records `pt_snap.import` semantically and never materializes a pickle.
The release-gating clean-wheel check separately installs the built wheel into a
fresh venv, installs `pt-snap-helper` from package data, and completes import,
capability, overview, and peak-query discovery using JSON output.

Generated transcripts and reports belong under `.skill-evals/`, which is
ignored by Git. Normal `pytest` runs never invoke a live model.
