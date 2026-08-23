from pathlib import Path

from tests.skills.harness.artifacts import write_run_artifacts
from tests.skills.harness.descriptors import load_suite
from tests.skills.harness.grader import RunRecord, ToolCall, grade_run

SUITE_PATH = Path("tests/skills/suites/pt-snap-memory-leak/suite.yaml")


def _passing_allocator_cache_run() -> RunRecord:
    return RunRecord(
        tool_calls=(
            ToolCall(
                "call-1",
                "pt_snap.metadata",
                {"database": "/fixtures/cache.db", "json": True},
            ),
            ToolCall(
                "call-2",
                "pt_snap.query",
                {"database": "/fixtures/cache.db", "device": 0, "template": "memory_peak"},
            ),
            ToolCall(
                "call-3",
                "pt_snap.query",
                {"database": "/fixtures/cache.db", "device": 0, "template": "allocator_gap"},
            ),
            ToolCall(
                "call-4",
                "pt_snap.query",
                {
                    "database": "/fixtures/cache.db",
                    "device": 0,
                    "template": "leak_detection",
                },
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
