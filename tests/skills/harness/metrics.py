from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .descriptors import EvalCase
from .grader import GradeResult, RunRecord


def _normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


def run_output_bytes(run: RunRecord) -> int:
    """Count UTF-8 bytes of recorded tool outputs, errors, and the final response."""
    chunks: list[str] = [run.final_response]
    for call in run.tool_calls:
        if call.output is not None:
            chunks.append(
                json.dumps(call.output, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            )
        if call.error:
            chunks.append(call.error)
    return sum(len(chunk.encode("utf-8")) for chunk in chunks)


def is_error_conclusion(case: EvalCase, run: RunRecord) -> bool:
    """True when the run asserts a prohibited classification or prohibited claim."""
    classification = run.result.get("classification")
    if classification in case.prohibited_classifications:
        return True
    raw_claims = run.result.get("claims", [])
    claim_text = " ".join(
        str(claim.get("statement", "")) for claim in raw_claims if isinstance(claim, dict)
    )
    searchable = _normalize_text(f"{claim_text} {run.final_response}")
    return any(_normalize_text(prohibited) in searchable for prohibited in case.prohibited_claims)


@dataclass(frozen=True)
class CaseMetrics:
    case_id: str
    passed: bool
    score: float
    call_count: int
    output_bytes: int
    error_conclusion: bool

    def to_mapping(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "passed": self.passed,
            "score": self.score,
            "call_count": self.call_count,
            "output_bytes": self.output_bytes,
            "error_conclusion": self.error_conclusion,
        }


@dataclass(frozen=True)
class BaselineSummary:
    suite_id: str
    case_count: int
    passed_count: int
    task_success_rate: float
    mean_call_count: float
    mean_output_bytes: float
    error_conclusion_rate: float
    cases: tuple[CaseMetrics, ...]

    def to_mapping(self) -> dict[str, Any]:
        return {
            "suite_id": self.suite_id,
            "case_count": self.case_count,
            "passed_count": self.passed_count,
            "task_success_rate": self.task_success_rate,
            "mean_call_count": self.mean_call_count,
            "mean_output_bytes": self.mean_output_bytes,
            "error_conclusion_rate": self.error_conclusion_rate,
            "cases": [case.to_mapping() for case in self.cases],
        }


def collect_case_metrics(case: EvalCase, run: RunRecord, grade: GradeResult) -> CaseMetrics:
    return CaseMetrics(
        case_id=case.id,
        passed=grade.passed,
        score=grade.score,
        call_count=len(run.tool_calls),
        output_bytes=run_output_bytes(run),
        error_conclusion=is_error_conclusion(case, run),
    )


def summarize_metrics(suite_id: str, rows: Iterable[CaseMetrics]) -> BaselineSummary:
    cases = tuple(rows)
    case_count = len(cases)
    if case_count == 0:
        raise ValueError("baseline summary requires at least one case")
    passed_count = sum(case.passed for case in cases)
    error_count = sum(case.error_conclusion for case in cases)
    return BaselineSummary(
        suite_id=suite_id,
        case_count=case_count,
        passed_count=passed_count,
        task_success_rate=round(passed_count / case_count, 4),
        mean_call_count=round(sum(case.call_count for case in cases) / case_count, 4),
        mean_output_bytes=round(sum(case.output_bytes for case in cases) / case_count, 4),
        error_conclusion_rate=round(error_count / case_count, 4),
        cases=cases,
    )
