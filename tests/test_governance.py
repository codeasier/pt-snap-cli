from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

GUARD_PATH = Path(".github/scripts/check_snapshot_provenance.py")
PROVENANCE_PATH = "src/pt_snap_cli/snapshot/PROVENANCE.md"
SNAPSHOT_CODE = "src/pt_snap_cli/snapshot/representation.py"
OLD_SOURCE_SLUG = "memsnap" + "dump"
BRANDING_ALLOWLIST = {
    "src/pt_snap_cli/snapshot/PROVENANCE.md",
    f"docs/legal/{OLD_SOURCE_SLUG}-mit-relicensing.md",
    "docs/development/vendor-audit.md",
    f"docs/development/{OLD_SOURCE_SLUG}-test-migration.md",
    f"docs/development/{OLD_SOURCE_SLUG}-verification.md",
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
    assert expected in _load_guard().validate_provenance(changes, body)


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


def test_old_source_identity_is_confined_to_fixed_evidence_allowlist() -> None:
    tracked = subprocess.run(
        ["git", "ls-files", "-z"], check=True, capture_output=True
    ).stdout.split(b"\0")
    old_brand = OLD_SOURCE_SLUG.encode()
    offenders: set[str] = set()
    candidate_paths = {raw_path.decode() for raw_path in tracked if raw_path}
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

    for path in (Path("docs/en/quickstart.md"), Path("docs/zh/quickstart.md")):
        text = path.read_text()
        assert "arbitrary code" in text.lower() or "任意代码" in text
        assert "not a sandbox" in text.lower() or "不是沙箱" in text


def test_verification_runbook_records_every_used_cli_flag() -> None:
    text = Path(f"docs/development/{OLD_SOURCE_SLUG}-verification.md").read_text()
    for flag in (
        "--no-focus",
        "--output-dir",
        "--device",
        "--slices",
        "--max-entries",
        "--format",
        "--output",
    ):
        assert flag in text
    assert "STOP" in text
