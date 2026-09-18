from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.skills.harness.descriptors import load_suite
from tests.skills.harness.gateway import RecordingToolGateway, ToolDeniedError
from tests.skills.harness.grader import RunRecord, grade_run
from tests.skills.harness.metrics import collect_case_metrics, summarize_metrics

SUITE_DIRECTORY = Path("tests/skills/suites/pt-snap-agent-e2e")
SUITE_PATH = SUITE_DIRECTORY / "suite.yaml"
TARGET_BASELINE = SUITE_DIRECTORY / "baselines" / "target"
PRE_CHANGE_BASELINE = SUITE_DIRECTORY / "baselines" / "pre-change"
CASE_IDS = (
    "cli-only-help-discovery",
    "wrong-template-recovery",
    "explicit-multi-target",
    "truncated-query",
    "live-blocks-unconfirmed",
    "missing-database",
    "import-success",
)


def _load_run(directory: Path, case_id: str) -> RunRecord:
    return RunRecord.from_mapping(json.loads((directory / f"{case_id}.json").read_text()))


def _summarize(directory: Path):
    suite = load_suite(SUITE_PATH)
    rows = []
    for case in suite.cases:
        run = _load_run(directory, case.id)
        grade = grade_run(suite, case, run)
        rows.append((case, run, grade, collect_case_metrics(case, run, grade)))
    return suite, rows, summarize_metrics(suite.id, (row[3] for row in rows))


def test_agent_e2e_suite_covers_issue_136_scenarios() -> None:
    suite = load_suite(SUITE_PATH)

    assert suite.id == "pt-snap-agent-e2e"
    assert suite.profile == "agent-cli"
    assert suite.skill_name == "pt-snap-agent-e2e"
    assert [case.id for case in suite.cases] == list(CASE_IDS)
    assert set(suite.required_branches) <= {
        branch for case in suite.cases for branch in case.covers
    }
    assert "pt_snap.import" in suite.allowed_operations
    assert "pickle.access" in suite.forbidden_operations


def test_target_baseline_is_a_perfect_score() -> None:
    _suite, rows, summary = _summarize(TARGET_BASELINE)

    assert summary.task_success_rate == 1.0
    assert summary.error_conclusion_rate == 0.0
    assert summary.passed_count == summary.case_count == len(CASE_IDS)
    assert all(grade.passed and grade.score == 100 for _case, _run, grade, _metrics in rows)


def test_pre_change_baseline_records_current_gaps() -> None:
    _suite, rows, summary = _summarize(PRE_CHANGE_BASELINE)
    by_id = {case.id: (grade, metrics) for case, _run, grade, metrics in rows}

    assert summary.task_success_rate == 0.0
    assert summary.passed_count == 0
    assert summary.error_conclusion_rate == 0.8571
    assert summary.mean_call_count == 1.0
    assert all(not grade.passed for grade, _metrics in by_id.values())
    assert by_id["wrong-template-recovery"][1].error_conclusion is False
    assert by_id["live-blocks-unconfirmed"][1].error_conclusion is True
    assert by_id["missing-database"][1].error_conclusion is True


def test_error_status_actions_match_structured_failures() -> None:
    suite = load_suite(SUITE_PATH)
    case = suite.case("wrong-template-recovery")
    run = _load_run(TARGET_BASELINE, case.id)

    grade = grade_run(suite, case, run)

    assert grade.matched_actions == {
        "mistyped_query": "call-1",
        "corrected_query": "call-2",
    }
    assert case.actions[0].status == "error"


def test_agent_cli_gateway_allows_import_and_denies_pickle_access() -> None:
    suite = load_suite(SUITE_PATH)
    gateway = RecordingToolGateway(
        suite, lambda operation, arguments: {"db_path": "/fixtures/imported.db"}
    )

    assert gateway.call("pt_snap.import", {"json": True}) == {"db_path": "/fixtures/imported.db"}
    with pytest.raises(ToolDeniedError, match="agent-cli"):
        gateway.call("pickle.access", {"path": "/fixtures/trusted-snapshot.pkl"})

    assert [call.status for call in gateway.calls] == ["success", "denied"]


def test_baseline_cli_writes_metrics(tmp_path: Path, monkeypatch, capsys) -> None:
    from tests.skills import __main__ as skills_main

    output = tmp_path / "metrics.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "tests.skills",
            "baseline",
            str(SUITE_PATH),
            str(PRE_CHANGE_BASELINE),
            "--output",
            str(output),
        ],
    )

    assert skills_main.main() == 0
    payload = json.loads(output.read_text())
    printed = json.loads(capsys.readouterr().out)
    assert payload == printed
    assert payload["task_success_rate"] == 0.0
    assert payload["error_conclusion_rate"] == 0.8571
    assert [case["case_id"] for case in payload["cases"]] == list(CASE_IDS)
