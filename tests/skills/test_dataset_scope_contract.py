"""Shipped instructions: static contracts plus owning executable SQLite/CLI tests.

These grades do not execute a live model, NPU, original producer or GUI.
"""

from pathlib import Path

import pytest

SKILLS = (
    "pt-snap-helper",
    "pt-snap-memory-leak",
    "pt-snap-memory-peak-breakdown",
    "pt-snap-memory-fragmentation",
)


@pytest.mark.parametrize("name", SKILLS)
def test_dataset_scope_identity_and_provenance_are_shipped_identically(name):
    authored = Path("skills") / name / "SKILL.md"
    bundled = Path("src/pt_snap_cli/bundled_skills") / name / "SKILL.md"
    assert authored.read_bytes() == bundled.read_bytes()
    text = authored.read_text()
    for field in (
        "manifest.json",
        "compatibility-v1",
        "pt-snap-native-v2",
        "fingerprint",
        "dataset_support.supported",
        "metadata_missing",
        "lifecycle_id",
        "allocation_source",
        "free_source",
        "text_kind",
        "source_stack_id",
        "ordered_frames_complete",
        "range_complete",
    ):
        assert field in text
    assert "text-only" in text and "100000" in text and "RSS ceiling" in text
    assert "arbitrary" in text and "sibling" in text
    assert "ALL" in text and "allocation-only" in text
    assert "unknown reason" in text and "invalid metadata" in text


def test_updated_peak_capability_keeps_conservative_range_workflow_and_guards():
    text = Path("skills/pt-snap-memory-peak-breakdown/SKILL.md").read_text()
    branch = text.split("## Event-Range Workflow")[1].split("## Interpretation Rules")[0]
    assert "--start-id" in branch and "--end-id" in branch
    assert "Never fabricate an event ID" in branch
    assert "NULL" in branch and "empty range" in branch
    assert "--template-use memory_peak" in branch
    assert "--template-use active_memory_callstack_at_event" in branch
    assert "never substitute an unbounded report" in branch
