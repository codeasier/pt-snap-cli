"""Iteration contracts and deterministic eval fixtures; no live model is run."""

from copy import deepcopy
from pathlib import Path

import pytest

from pt_snap_cli.context import Context
from pt_snap_cli.query.executor import QueryExecutor
from pt_snap_cli.query.registry import QueryRegistry, _load_all_templates
from tests.skills.harness.descriptors import load_suite
from tests.skills.harness.fixtures import build_snapshotdb
from tests.skills.harness.grader import RunRecord, ToolCall, grade_run

SKILL_PATH = Path("skills/pt-snap-memory-leak/SKILL.md")
SUITE_PATH = Path("tests/skills/suites/pt-snap-memory-leak-iterations/suite.yaml")
CASE_IDS = ("trusted-three", "multiple-cleanups", "no-verified-markers", "incomplete-capture")


def test_iteration_evidence_precedes_both_positive_and_negative_classification() -> None:
    skill = SKILL_PATH.read_text()
    step = " ".join(skill.split("### 7. Classify findings conservatively")[1].split())
    step = step.split("## Output Template")[0]

    for required in (
        "Before any positive or negative per-step / per-iteration conclusion",
        '"not a per-step leak"',
        "trusted iteration count, boundaries mapped to event IDs, source, and coverage range",
        "workload code, logs, or an explicit verified marker convention",
        "allocator event counts, waveform minima, and cleanup counts are not iteration counts",
        "Do not directly count `segment_unmap` events as steps",
        "one iteration can perform multiple cleanups, or none",
        "fully covered iterations from partial iterations and uncaptured work",
        "per-step conclusion as `unknown`",
        "a conclusion scoped only to that subrange",
        "per-iteration accumulation a candidate, not a confirmed leak",
        "Jaccard similarity of `(action, callstackId)` sets",
        "Sets discard multiplicity, ordering, allocation identity, and byte sizes",
        "cannot prove that unreturned bytes are the only per-iteration difference",
    ):
        assert required in step
    assert step.index("trusted iteration count") < step.index("Use these result categories")


def test_iteration_output_and_checklist_require_source_and_coverage() -> None:
    skill = SKILL_PATH.read_text()
    output = skill.split("## Output Template")[1].split("## Guardrails")[0]
    checklist = skill.split("## Verification Checklist")[1]

    assert output.index("`Iteration evidence`") < output.index("`Findings`")
    for section in (output, checklist):
        for required in ("iteration count", "event-ID boundaries", "source", "coverage range"):
            assert required in section
        assert "positive or negative per-step" in section
        assert "`unknown`" in section
        assert "candidate, not a confirmed leak" in section
    assert "partial or uncaptured work" in checklist
    assert "Jaccard set similarity was not used to claim a unique byte difference" in checklist


@pytest.fixture
def iteration_outputs(tmp_path: Path):
    QueryRegistry.reset()
    _load_all_templates()
    database = build_snapshotdb(SUITE_PATH.parent / "fixtures/accumulation.yaml", tmp_path / "i.db")
    context = Context(database)
    executor = QueryExecutor(context)
    try:
        yield {
            "orient": {"device_ids": context.device_ids},
            "candidates": executor.execute_template("leak_detection", params={}, device_id=0),
            "events": executor.execute_template(
                "event", params={"order_by": "id", "order_dir": "ASC"}, device_id=0
            ),
        }
    finally:
        context.close()


def test_iteration_fixture_exposes_accumulation_but_no_step_markers(iteration_outputs) -> None:
    candidates = iteration_outputs["candidates"]
    events = iteration_outputs["events"]
    assert {row["allocEventId"] for row in candidates} == {1, 4, 7}
    assert sum(row["size"] for row in candidates) == 3 * 40 * 1024 * 1024
    assert [row["id"] for row in events if row["action"] == 1] == [2, 3, 5, 6, 8, 9]
    assert not any(row["action"] in (5, 6) for row in events)
    assert [row["active"] for row in events if row["id"] in (3, 6, 9)] == [
        41943040,
        83886080,
        125829120,
    ]


def _oracle_run(case, outputs) -> RunRecord:
    """Check the declarative oracle against real queries, not agent behavior."""
    return RunRecord(
        tool_calls=tuple(
            ToolCall(action.id, action.operation, dict(action.match), output=outputs[action.id])
            for action in case.actions
        ),
        result={
            "classification": case.allowed_classifications[0],
            "facts": deepcopy(case.oracle_facts),
            "claims": [
                {"id": claim, "evidence_call_ids": [produced_by]}
                for claim, produced_by in case.required_evidence
            ],
            "unknowns": list(case.required_unknowns),
        },
    )


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_iteration_eval_oracles_match_real_fixture_outputs(case_id, iteration_outputs) -> None:
    suite = load_suite(SUITE_PATH)
    assert {case.id for case in suite.cases} == set(CASE_IDS)
    assert set(suite.required_branches) <= {
        branch for case in suite.cases for branch in case.covers
    }
    case = suite.case(case_id)
    grade = grade_run(suite, case, _oracle_run(case, iteration_outputs))
    assert grade.passed, grade
    assert grade.score == 100


@pytest.mark.parametrize(
    ("case_id", "field", "unsupported_value"),
    [
        ("trusted-three", "iteration_count", 8),
        ("trusted-three", "iteration_count", 9),
        ("trusted-three", "iteration_boundaries", [[1, 9]]),
        ("trusted-three", "iteration_source", "waveform minima"),
        ("trusted-three", "coverage_range", "whole run assumed"),
        ("trusted-three", "confirmed_leak", True),
        ("trusted-three", "jaccard_proves_unique_byte_difference", True),
        ("multiple-cleanups", "iteration_count", 6),
        ("no-verified-markers", "iteration_count", 3),
        ("no-verified-markers", "per_step_conclusion", "per-step leak"),
        ("no-verified-markers", "per_step_conclusion", "not a per-step leak"),
        ("incomplete-capture", "whole_run_iteration_count", 3),
        ("incomplete-capture", "complete_iterations", 3),
        ("incomplete-capture", "whole_run_per_step_conclusion", "not a per-step leak"),
    ],
)
def test_iteration_eval_rejects_unsupported_conclusions(
    case_id, field, unsupported_value, iteration_outputs
) -> None:
    suite = load_suite(SUITE_PATH)
    case = suite.case(case_id)
    run = _oracle_run(case, iteration_outputs)
    run.result["facts"][field] = unsupported_value
    grade = grade_run(suite, case, run)
    assert not grade.passed
    assert not next(
        objective
        for objective in grade.objectives
        if objective.objective_id == "evidence.factual_accuracy"
    ).passed
