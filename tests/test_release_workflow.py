import re
from pathlib import Path

import yaml

WORKFLOW = Path(".github/workflows/release.yml")
CHANGELOG = Path("CHANGELOG.md")


def _workflow_text() -> str:
    return WORKFLOW.read_text()


def _workflow() -> dict:
    return yaml.load(_workflow_text(), Loader=yaml.BaseLoader)


def test_release_workflow_fetches_full_git_history_for_setuptools_scm() -> None:
    text = _workflow_text()

    assert "uses: actions/checkout@v4" in text
    assert "fetch-depth: 0" in text


def test_release_workflow_gates_publication_on_same_commit_quality_checks() -> None:
    jobs = _workflow()["jobs"]

    assert jobs["quality"]["uses"] == "./.github/workflows/test.yml"
    assert jobs["build"]["needs"] == "quality"
    assert jobs["publish"]["needs"] == "build"
    assert jobs["github-release"]["needs"] == "publish"


def test_release_workflow_verifies_built_package_version_against_tag() -> None:
    text = _workflow_text()

    assert "Verify built package version matches tag" in text
    assert "importlib.metadata" in text
    assert "version('pt-snap-cli')" in text or 'version("pt-snap-cli")' in text
    assert "Tag v$TAG does not match built package version" in text
    assert "tomllib.load" not in text
    assert "['project']['version']" not in text


def test_release_workflow_creates_github_release_from_changelog() -> None:
    text = _workflow_text()

    assert "Extract release notes from changelog" in text
    assert 'removeprefix("refs/tags/v")' in text
    assert "CHANGELOG.md does not contain release notes for ## [{tag}]" in text
    assert "release-notes.md" in text
    assert "gh release create" in text
    assert "TAG=${GITHUB_REF#refs/tags/}" in text
    assert '--title "$TAG"' in text
    assert "dist/*" in text

    build_steps = _workflow()["jobs"]["build"]["steps"]
    step_names = [step.get("name") for step in build_steps]
    assert step_names.index("Extract release notes from changelog") < step_names.index(
        "Upload build artifacts"
    )


def test_release_notes_regex_extracts_current_changelog_entry() -> None:
    tag = "0.1.1"
    text = CHANGELOG.read_text()
    pattern = rf"^## \[{re.escape(tag)}\].*?$(.*?)(?=^## \[|\Z)"

    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)

    assert match is not None
    notes = match.group(1).strip()
    assert notes
    assert "SnapshotDB" in notes
