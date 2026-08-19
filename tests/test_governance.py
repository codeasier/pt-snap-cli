from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
import yaml

GUARD_PATH = Path(".github/scripts/check_snapshot_provenance.py")
PROVENANCE_PATH = "src/pt_snap_cli/snapshot/PROVENANCE.md"
SNAPSHOT_CODE = "src/pt_snap_cli/snapshot/representation.py"
OLD_SOURCE_SLUG = "memsnap" + "dump"
BRANDING_ALLOWLIST = {
    "src/pt_snap_cli/snapshot/PROVENANCE.md",
    f"docs/legal/{OLD_SOURCE_SLUG}-mit-relicensing.md",
}
ISSUE_TEMPLATE_DIR = Path(".github/ISSUE_TEMPLATE")
ISSUE_FORM_NAMES = {
    "01-bug-report.yml",
    "02-feature-request.yml",
    "03-documentation.yml",
    "04-question.yml",
}


def _load_guard() -> ModuleType:
    spec = importlib.util.spec_from_file_location("snapshot_provenance_guard", GUARD_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("changes", "body", "expected"),
    [
        (["README.md"], "", "No snapshot runtime changes"),
        (
            [SNAPSHOT_CODE, PROVENANCE_PATH],
            "Snapshot provenance decision: updated",
            "Snapshot provenance updated",
        ),
        (
            [SNAPSHOT_CODE],
            "Snapshot provenance decision: no-update\n"
            "Snapshot provenance no-update reason: Test-only fixture naming; runtime history is unchanged.",
            "Snapshot provenance evaluated with no update",
        ),
    ],
)
def test_snapshot_provenance_guard_accepts_valid_decisions(
    changes: list[str], body: str, expected: str
) -> None:
    inserted = [b"new evidence\n"] if PROVENANCE_PATH in changes else []
    assert expected in _load_guard().validate_provenance(changes, body, inserted)


@pytest.mark.parametrize(
    "body",
    [
        "",
        "Snapshot provenance decision: <!-- updated | no-update -->",
        "Snapshot provenance decision: maybe",
        "Snapshot provenance decision: no-update",
        "Snapshot provenance decision: no-update\nSnapshot provenance no-update reason:",
        "Snapshot provenance decision: no-update\nSnapshot provenance no-update reason: TODO",
        "Snapshot provenance decision: no-update\n"
        "Snapshot provenance no-update reason: <!-- required only for no-update -->",
        "Snapshot provenance decision: no-update\nSnapshot provenance decision: updated\n"
        "Snapshot provenance no-update reason: Runtime is unchanged.",
    ],
)
def test_snapshot_provenance_guard_rejects_missing_or_placeholder_evaluation(body: str) -> None:
    with pytest.raises(ValueError):
        _load_guard().validate_provenance([SNAPSHOT_CODE], body)


def test_snapshot_provenance_guard_requires_declaration_change_for_updated_decision() -> None:
    with pytest.raises(ValueError, match="requires a change"):
        _load_guard().validate_provenance([SNAPSHOT_CODE], "Snapshot provenance decision: updated")


def test_snapshot_provenance_guard_requires_inserted_content_for_updated_decision() -> None:
    with pytest.raises(ValueError, match="requires new content"):
        _load_guard().validate_provenance(
            [SNAPSHOT_CODE, PROVENANCE_PATH],
            "Snapshot provenance decision: updated",
        )


def test_snapshot_provenance_guard_rejects_provenance_change_for_no_update() -> None:
    body = (
        "Snapshot provenance decision: no-update\n"
        "Snapshot provenance no-update reason: Runtime history is unchanged."
    )
    with pytest.raises(ValueError, match="cannot include a change"):
        _load_guard().validate_provenance([SNAPSHOT_CODE, PROVENANCE_PATH], body)


@pytest.mark.parametrize(
    "head",
    [
        None,
        b"first\nthird\n",
        b"first\nchanged\nthird\n",
        b"first\nsecond\n",
        b"second\nfirst\nthird\n",
    ],
)
def test_snapshot_provenance_append_only_rejects_destructive_edits(
    head: bytes | None,
) -> None:
    with pytest.raises(ValueError):
        _load_guard().validate_append_only(b"first\nsecond\nthird\n", head)


@pytest.mark.parametrize(
    ("head", "inserted"),
    [
        (b"first\nnew section\nsecond\nthird\n", [b"new section\n"]),
        (b"first\nsecond\nthird\nnew appendix\n", [b"new appendix\n"]),
        (b"first\nsecond\nthird\n", []),
    ],
)
def test_snapshot_provenance_append_only_accepts_insertions(
    head: bytes,
    inserted: list[bytes],
) -> None:
    assert _load_guard().validate_append_only(b"first\nsecond\nthird\n", head) == inserted


def test_snapshot_provenance_guard_cli_compares_committed_blobs(tmp_path: Path) -> None:
    guard_path = GUARD_PATH.resolve()

    def git(*args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    git("init", "-q")
    git("config", "user.name", "Test")
    git("config", "user.email", "test@example.com")
    provenance = tmp_path / PROVENANCE_PATH
    provenance.parent.mkdir(parents=True)
    provenance.write_text("first\nsecond\n")
    code = tmp_path / SNAPSHOT_CODE
    code.write_text("before\n")
    git("add", ".")
    git("commit", "-qm", "base")
    base = git("rev-parse", "HEAD")

    provenance.write_text("first\ninserted\nsecond\n")
    code.write_text("after\n")
    git("add", ".")
    git("commit", "-qm", "append")
    head = git("rev-parse", "HEAD")
    env = os.environ.copy()
    env["PR_BODY"] = "Snapshot provenance decision: updated"

    accepted = subprocess.run(
        [
            sys.executable,
            str(guard_path),
            "--base",
            base,
            "--head",
            head,
            "--require-decision",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )

    assert accepted.returncode == 0, accepted.stderr
    assert "Snapshot provenance updated" in accepted.stdout


def test_old_source_identity_is_confined_to_fixed_evidence_allowlist() -> None:
    tracked = subprocess.run(
        ["git", "ls-files", "-z"], check=True, capture_output=True
    ).stdout.split(b"\0")
    old_brand = OLD_SOURCE_SLUG.encode()
    offenders: set[str] = set()
    candidate_paths = {
        raw_path.decode() for raw_path in tracked if raw_path and Path(raw_path.decode()).exists()
    }
    # Include newly created evidence files before their first commit; every other
    # candidate still comes from git's tracked-file manifest.
    candidate_paths.update(path for path in BRANDING_ALLOWLIST if Path(path).exists())
    for path_string in candidate_paths:
        raw_path = path_string.encode()
        if not raw_path:
            continue
        path = Path(path_string)
        if old_brand in raw_path.lower() or old_brand in path.read_bytes().lower():
            offenders.add(path.as_posix())

    assert offenders == BRANDING_ALLOWLIST

    unsupported_names = (("pt_snap_" + "analyzer").encode(), ("pt-snap-" + "analyzer").encode())
    unsupported_hits = {
        path_string
        for path_string in candidate_paths
        if any(term in Path(path_string).read_bytes().lower() for term in unsupported_names)
    }
    assert not unsupported_hits


def test_bilingual_docs_record_split_and_pickle_security_contract() -> None:
    for path in (Path("docs/en/splitting.md"), Path("docs/zh/splitting.md")):
        text = path.read_text()
        for flag in ("--output", "--device", "--slices", "--max-entries", "--format"):
            assert flag in text
        assert "<source-stem>__device-<id>__slice-<index>.<ext>" in text
        assert "arbitrary code" in text.lower() or "任意代码" in text
        assert "not a sandbox" in text.lower() or "不是沙箱" in text
        assert "builtins" in text.lower()

    for path in (
        Path("docs/en/quickstart.md"),
        Path("docs/zh/quickstart.md"),
        Path("docs/en/database.md"),
        Path("docs/zh/database.md"),
    ):
        text = path.read_text()
        assert "arbitrary code" in text.lower() or "任意代码" in text
        assert "not a sandbox" in text.lower() or "不是沙箱" in text
        assert "builtins" in text.lower()


def test_github_issue_forms_and_default_pr_template_use_supported_paths() -> None:
    forms = {
        path.name
        for path in ISSUE_TEMPLATE_DIR.iterdir()
        if path.suffix in {".yml", ".yaml"} and path.name != "config.yml"
    }
    assert forms == ISSUE_FORM_NAMES

    for name in ISSUE_FORM_NAMES:
        form = yaml.load((ISSUE_TEMPLATE_DIR / name).read_text(), Loader=yaml.BaseLoader)
        assert form["name"]
        assert form["description"]
        assert form["body"]

    config = yaml.load((ISSUE_TEMPLATE_DIR / "config.yml").read_text(), Loader=yaml.BaseLoader)
    assert "issue_templates" not in config
    assert all("/discussions" not in link["url"] for link in config["contact_links"])
    assert Path(".github/pull_request_template.md").is_file()
    assert not list(Path(".github/PULL_REQUEST_TEMPLATE").glob("*.md"))

    guard = _load_guard()
    pr_body = Path(".github/pull_request_template.md").read_text()
    assert pr_body.count(f"{guard.DECISION_LABEL}:") == 1
    assert pr_body.count(f"{guard.REASON_LABEL}:") == 1
    with pytest.raises(ValueError):
        guard.validate_provenance([SNAPSHOT_CODE], pr_body)
