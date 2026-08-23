from __future__ import annotations

import argparse
import json
from pathlib import Path

from .harness.artifacts import write_run_artifacts
from .harness.descriptors import load_suite
from .harness.grader import RunRecord, grade_run


def _validate(args: argparse.Namespace) -> int:
    suite = load_suite(args.suite)
    covered = sorted({branch for case in suite.cases for branch in case.covers})
    print(
        json.dumps(
            {
                "suite": suite.id,
                "skill": suite.skill_name,
                "cases": [case.id for case in suite.cases],
                "covered_branches": covered,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _grade(args: argparse.Namespace) -> int:
    suite = load_suite(args.suite)
    case = suite.case(args.case)
    run = RunRecord.from_mapping(json.loads(args.run.read_text()))
    grade = grade_run(suite, case, run)
    if args.output is not None:
        write_run_artifacts(args.output, suite, case, run, grade)
    print(json.dumps(grade.to_mapping(), indent=2, sort_keys=True))
    return 0 if grade.passed else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and grade local skill evaluations")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="validate a suite and its cases")
    validate_parser.add_argument("suite", type=Path)
    validate_parser.set_defaults(handler=_validate)

    grade_parser = subparsers.add_parser("grade", help="grade a recorded agent run")
    grade_parser.add_argument("suite", type=Path)
    grade_parser.add_argument("case")
    grade_parser.add_argument("run", type=Path)
    grade_parser.add_argument("--output", type=Path)
    grade_parser.set_defaults(handler=_grade)

    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
