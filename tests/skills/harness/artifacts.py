from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .descriptors import REPO_ROOT, EvalCase, EvalSuite
from .grader import GradeResult, RunRecord


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_run_artifacts(
    output_directory: Path,
    suite: EvalSuite,
    case: EvalCase,
    run: RunRecord,
    grade: GradeResult,
) -> None:
    output_directory.mkdir(parents=True, exist_ok=False)
    manifest = {
        "suite_id": suite.id,
        "case_id": case.id,
        "skill_path": str(suite.skill_path.relative_to(REPO_ROOT)),
        "skill_sha256": _sha256(suite.skill_path),
        "suite_sha256": _sha256(suite.path),
        "case_sha256": _sha256(case.path),
    }
    (output_directory / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    with (output_directory / "trace.jsonl").open("w") as stream:
        for call in run.tool_calls:
            stream.write(
                json.dumps(
                    {
                        "id": call.id,
                        "operation": call.operation,
                        "arguments": call.arguments,
                        "status": call.status,
                        "output": call.output,
                        "error": call.error,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
    (output_directory / "outcome.json").write_text(
        json.dumps(
            {"result": run.result, "final_response": run.final_response},
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    (output_directory / "score.json").write_text(
        json.dumps(grade.to_mapping(), indent=2, sort_keys=True) + "\n"
    )
