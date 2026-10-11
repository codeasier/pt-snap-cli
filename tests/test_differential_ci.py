"""The 200-seed profile is a required scheduled/manual step, separate from PRs."""

from pathlib import Path

import yaml


def test_nightly_job_executes_and_preserves_required_200_seed_profile():
    workflow = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / ".github/workflows/test.yml").read_text()
    )
    job = workflow["jobs"]["dataset-acceptance"]
    assert (
        job["if"] == "github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'"
    )
    steps = job["steps"]
    names = [step.get("name") for step in steps]
    generic = names.index("Run required installed-wheel dataset acceptance")
    index = names.index("Run required 200-seed paired differential acceptance")
    assert generic < index
    step = steps[index]
    assert "if" not in step and not step.get("continue-on-error", False)
    assert step["run"].split() == [
        "python",
        ".github/scripts/run_differential_acceptance.py",
        "\\",
        "--seed-count",
        "200",
        "--output-dir",
        ".tmp/differential-acceptance",
    ]
    upload = steps[names.index("Upload paired differential evidence")]
    assert upload["if"] == "always()" and names.index(upload["name"]) > index
    assert set(upload["with"]["path"].splitlines()) == {
        ".tmp/differential-acceptance/*.log",
        ".tmp/differential-acceptance/*.xml",
        ".tmp/differential-acceptance/summary.json",
        ".tmp/differential-acceptance/pytest-temp/**/coverage.json",
        ".tmp/differential-acceptance/pytest-temp/**/timeline.json",
        ".tmp/differential-acceptance/pytest-temp/**/differential-failure.json",
    }
    assert upload["with"]["include-hidden-files"] is True
    assert upload["with"]["if-no-files-found"] == "error"
    # The ordinary PR matrix keeps the default20 profile and never inherits200.
    regular = workflow["jobs"]["test"]
    assert "PT_SNAP_DIFFERENTIAL_SEEDS" not in str(regular)
