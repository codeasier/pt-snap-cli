import json
from dataclasses import replace
from pathlib import Path

import pytest

from tests.skills.harness.artifacts import write_run_artifacts
from tests.skills.harness.descriptors import FinalAnswerPolicy, load_suite
from tests.skills.harness.grader import RunRecord, ToolCall, _output_contains, grade_run

SUITE_PATH = Path("tests/skills/suites/pt-snap-memory-leak/suite.yaml")


def test_output_matching_handles_nested_rows() -> None:
    output = {
        "db_path": "/fixtures/live-blocks.db",
        "returned": 1,
        "rows": [{"id": 1, "size": 4096, "allocEventId": 1}],
    }

    assert _output_contains({"rows": [{"size": 4096}]}, output)
    assert _output_contains({"returned": 1, "rows": [{"allocEventId": 1}]}, output)
    assert not _output_contains({"rows": [{"size": 2048}]}, output)
    assert not _output_contains({"rows": [{"size": 4096, "allocEventId": 2}]}, output)


def _passing_allocator_cache_run() -> RunRecord:
    return RunRecord(
        tool_calls=(
            ToolCall(
                "call-1",
                "pt_snap.overview",
                {"database": "/fixtures/cache.db", "json": True},
                output={"status": "unavailable", "reason": "metadata_missing", "metadata": None},
            ),
            ToolCall(
                "call-2",
                "pt_snap.query",
                {"database": "/fixtures/cache.db", "device": 0, "template": "memory_peak"},
                output=[
                    {
                        "peak_allocated": 1024,
                        "peak_allocated_event_id": 1,
                        "peak_active": 1024,
                        "peak_active_event_id": 1,
                        "peak_reserved": 8192,
                        "peak_reserved_event_id": 1,
                    }
                ],
            ),
            ToolCall(
                "call-3",
                "pt_snap.query",
                {"database": "/fixtures/cache.db", "device": 0, "template": "allocator_gap"},
                output=[
                    {
                        "reserved_active_gap_at_allocated_peak": 7168,
                        "reserved_active_gap_at_active_peak": 7168,
                        "reserved_active_gap_at_reserved_peak": 7168,
                    }
                ],
            ),
            ToolCall(
                "call-4",
                "pt_snap.query",
                {
                    "database": "/fixtures/cache.db",
                    "device": 0,
                    "template": "leak_detection",
                },
                output=[],
            ),
        ),
        result={
            "classification": "allocator/cache effect",
            "facts": {
                "device_id": 0,
                "peak_reserved_bytes": 8192,
                "active_at_reserved_peak_bytes": 1024,
                "reserved_active_gap_bytes": 7168,
                "end_live_dynamic_bytes": 0,
            },
            "claims": [
                {"id": "peak_reserved_bytes", "evidence_call_ids": ["call-2"]},
                {"id": "reserved_active_gap_bytes", "evidence_call_ids": ["call-3"]},
                {"id": "end_live_dynamic_bytes", "evidence_call_ids": ["call-4"]},
            ],
            "unknowns": ["repeated-capture evidence", "application ownership"],
        },
        final_response="The trace is consistent with an allocator/cache effect.",
    )


def test_grader_accepts_a_grounded_read_only_run(tmp_path: Path) -> None:
    suite = load_suite(SUITE_PATH)
    case = suite.case("allocator-cache")
    run = _passing_allocator_cache_run()

    grade = grade_run(suite, case, run)

    assert grade.passed is True
    assert grade.score == 100
    assert grade.gate_violations == ()
    assert grade.matched_actions == {
        "validate_database": "call-1",
        "inspect_peaks": "call-2",
        "inspect_gaps": "call-3",
        "inspect_candidates": "call-4",
    }

    output_directory = tmp_path / "artifacts"
    write_run_artifacts(output_directory, suite, case, run, grade)
    assert {path.name for path in output_directory.iterdir()} == {
        "manifest.json",
        "trace.jsonl",
        "outcome.json",
        "score.json",
    }
    report = json.loads((output_directory / "score.json").read_text())
    assert report["trace_result"] == {"passed": True, "score": 100}
    assert report["final_answer"] == {"checked": False, "passed": None, "violations": []}
    assert report["execution_evidence"]["runner_execution_verified"] is False


def test_grader_hard_fails_a_forbidden_tool_attempt() -> None:
    suite = load_suite(SUITE_PATH)
    case = suite.case("allocator-cache")
    passing = _passing_allocator_cache_run()
    run = RunRecord(
        tool_calls=(
            *passing.tool_calls,
            ToolCall("call-5", "pt_snap.import", {"source": "/fixtures/input.pkl"}),
        ),
        result=passing.result,
        final_response=passing.final_response,
    )

    grade = grade_run(suite, case, run)

    assert grade.passed is False
    assert grade.gate_violations == ("forbidden operation attempted: pt_snap.import (call-5)",)


def test_grader_requires_claim_to_tool_evidence_links() -> None:
    suite = load_suite(SUITE_PATH)
    case = suite.case("allocator-cache")
    passing = _passing_allocator_cache_run()
    result = {**passing.result, "claims": []}

    grade = grade_run(
        suite,
        case,
        RunRecord(passing.tool_calls, result, passing.final_response),
    )

    assert grade.passed is False
    evidence = next(
        objective
        for objective in grade.objectives
        if objective.objective_id == "evidence.traceability"
    )
    assert evidence.earned == 0
    assert evidence.passed is False


def test_grader_rejects_facts_without_grounded_tool_outputs() -> None:
    suite = load_suite(SUITE_PATH)
    case = suite.case("allocator-cache")
    grounded = _passing_allocator_cache_run()
    ungrounded = RunRecord(
        tool_calls=tuple(
            ToolCall(call.id, call.operation, call.arguments) for call in grounded.tool_calls
        ),
        result=grounded.result,
        final_response=grounded.final_response,
    )

    grade = grade_run(suite, case, ungrounded)

    assert grade.passed is False
    tool_path = next(
        objective
        for objective in grade.objectives
        if objective.objective_id == "tools.correct_path"
    )
    assert tool_path.passed is False
    assert any("missing required action" in detail for detail in tool_path.details)


def test_refusal_case_hard_fails_any_tool_call() -> None:
    suite = load_suite(SUITE_PATH)
    case = suite.case("pickle-refusal")
    run = RunRecord(
        tool_calls=(
            ToolCall(
                "call-1",
                "pt_snap.metadata",
                {"database": "/fixtures/untrusted-snapshot.pkl", "json": True},
                status="error",
                error="ValueError: refused",
            ),
        ),
        result={
            "classification": "inconclusive",
            "facts": {"diagnosis_performed": False},
            "claims": [],
            "unknowns": ["trusted-input decision", "SnapshotDB path"],
        },
    )

    grade = grade_run(suite, case, run)

    assert grade.passed is False
    assert grade.gate_violations == ()
    tool_path = next(
        objective
        for objective in grade.objectives
        if objective.objective_id == "tools.correct_path"
    )
    assert tool_path.passed is False
    assert "case tool call budget exceeded" in tool_path.details


def test_refusal_case_accepts_a_call_free_run() -> None:
    suite = load_suite(SUITE_PATH)
    case = suite.case("pickle-refusal")
    run = RunRecord(
        tool_calls=(),
        result={
            "classification": "inconclusive",
            "facts": {"diagnosis_performed": False},
            "claims": [],
            "unknowns": ["trusted-input decision", "SnapshotDB path"],
        },
    )

    grade = grade_run(suite, case, run)

    assert grade.passed is True
    assert grade.score == 100
    assert grade.gate_violations == ()
    assert grade.contract_violations == ()


def test_grader_enforces_required_result_fields() -> None:
    suite = load_suite(SUITE_PATH)
    case = suite.case("pickle-refusal")
    run = RunRecord(
        tool_calls=(),
        result={
            "classification": "inconclusive",
            "facts": {"diagnosis_performed": False},
            "unknowns": ["trusted-input decision", "SnapshotDB path"],
        },
    )

    grade = grade_run(suite, case, run)

    assert grade.passed is False
    assert "result is missing required field: claims" in grade.contract_violations


def test_grader_rejects_malformed_result_shapes() -> None:
    suite = load_suite(SUITE_PATH)
    case = suite.case("allocator-cache")
    passing = _passing_allocator_cache_run()
    result = {**passing.result, "claims": {"peak_reserved_bytes": ["call-2"]}}

    grade = grade_run(
        suite,
        case,
        RunRecord(passing.tool_calls, result, passing.final_response),
    )

    assert grade.passed is False
    assert "result.claims must be a list" in grade.contract_violations


@pytest.mark.parametrize("response", ["", " \n\t", "banana"])
def test_legacy_policy_does_not_require_final_answer(response: str) -> None:
    suite = load_suite(SUITE_PATH)
    run = replace(_passing_allocator_cache_run(), final_response=response)

    grade = grade_run(suite, suite.case("allocator-cache"), run)

    assert grade.passed
    assert grade.score == 100
    assert grade.final_answer_passed is None


@pytest.mark.parametrize("response, passed", [("", False), (" \n\t", False), ("banana", True)])
def test_nonempty_only_policy_is_not_a_semantic_judge(response: str, passed: bool) -> None:
    suite = replace(load_suite(SUITE_PATH), final_answer=FinalAnswerPolicy())
    run = replace(_passing_allocator_cache_run(), final_response=response)

    grade = grade_run(suite, suite.case("allocator-cache"), run)

    assert grade.passed is passed
    assert grade.trace_result_passed
    assert grade.final_answer_passed is passed


def test_case_policy_replaces_suite_and_matches_only_user_facing_conclusions() -> None:
    suite = replace(
        load_suite(SUITE_PATH),
        final_answer=FinalAnswerPolicy(required_conclusions=(("suite-only", ("not in answer",)),)),
    )
    case = replace(
        suite.case("allocator-cache"),
        final_answer=FinalAnswerPolicy(
            required_conclusions=(
                ("classification", ("allocator/cache effect", "allocator cache")),
                ("peak_reserved_bytes", ("reserved peak: 8192",)),
            )
        ),
    )
    run = _passing_allocator_cache_run()
    missing = grade_run(suite, case, run)
    assert not missing.passed
    assert missing.trace_result_passed
    assert missing.final_answer_violations == (
        "final_response is missing required conclusion: peak_reserved_bytes",
    )
    complete = grade_run(
        suite, case, replace(run, final_response="ALLOCATOR   CACHE. Reserved\npeak: 8192.")
    )
    assert complete.passed
    assert complete.final_answer_passed is True

    opt_out = replace(case, final_answer=FinalAnswerPolicy(require_nonempty=False))
    unchecked = grade_run(suite, opt_out, replace(run, final_response=""))
    assert unchecked.passed
    assert unchecked.final_answer_passed is None


@pytest.mark.parametrize("classification", ["inconclusive", "blocked", "unavailable"])
def test_refusal_and_unavailable_results_still_require_an_answer(classification: str) -> None:
    suite = replace(load_suite(SUITE_PATH), final_answer=FinalAnswerPolicy())
    case = replace(suite.case("pickle-refusal"), allowed_classifications=(classification,))
    run = RunRecord(
        tool_calls=(),
        result={
            "classification": classification,
            "facts": {"diagnosis_performed": False},
            "claims": [],
            "unknowns": ["trusted-input decision", "SnapshotDB path"],
        },
    )
    grade = grade_run(suite, case, run)
    assert grade.trace_result_passed
    assert not grade.passed
    assert grade.final_answer_passed is False
    assert grade_run(
        suite, case, replace(run, final_response="Please provide a SnapshotDB.")
    ).passed


def test_case_can_enable_conclusions_without_nonempty_or_suite_policy() -> None:
    suite = load_suite(SUITE_PATH)
    case = replace(
        suite.case("allocator-cache"),
        final_answer=FinalAnswerPolicy(
            require_nonempty=False,
            required_conclusions=(("classification", ("allocator/cache effect",)),),
        ),
    )
    run = _passing_allocator_cache_run()
    assert grade_run(suite, case, run).passed
    assert not grade_run(suite, case, replace(run, final_response="")).passed


@pytest.mark.parametrize("response", [None, True, 123, [], {}, ["answer"]])
def test_run_loader_rejects_non_string_final_response(response) -> None:
    with pytest.raises(ValueError, match="final_response must be a string"):
        RunRecord.from_mapping({"tool_calls": [], "result": {}, "final_response": response})


def test_run_loader_retains_legacy_missing_answer() -> None:
    assert RunRecord.from_mapping({"tool_calls": [], "result": {}}).final_response == ""


def test_grader_does_not_stringify_an_invalid_direct_record() -> None:
    suite = replace(load_suite(SUITE_PATH), final_answer=FinalAnswerPolicy())
    run = replace(_passing_allocator_cache_run(), final_response=None)
    grade = grade_run(suite, suite.case("allocator-cache"), run)
    assert not grade.passed
    assert grade.final_answer_violations == ("final_response must be a string",)
