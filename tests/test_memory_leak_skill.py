from pathlib import Path

SKILL_PATH = Path("skills/pt-snap-memory-leak/SKILL.md")


def test_memory_leak_skill_uses_current_pt_snap_surfaces() -> None:
    skill = SKILL_PATH.read_text()

    assert "name: pt-snap-memory-leak" in skill
    assert "`pt-snap-setup`" in skill
    assert "readiness.json" not in skill

    for template in (
        "memory_peak",
        "allocator_gap",
        "event",
        "block",
        "leak_detection",
        "active_memory_callstack_at_event",
    ):
        assert f"--template-use {template}" in skill or f"--template-info {template}" in skill


def test_memory_leak_skill_preserves_diagnostic_boundaries() -> None:
    skill = SKILL_PATH.read_text()

    required_guardrails = (
        "A single snapshot cannot confirm a leak.",
        "Do not run `pt-snap import`",
        "Do not run `pt-snap focus <database_path>`",
        "Do not use `block.state` as evidence for dynamic blocks.",
        "Event IDs are ordering markers, not timestamps",
        "Keep SnapshotDB access read-only.",
        "Label evidence, inference, and unknowns separately.",
    )
    for guardrail in required_guardrails:
        assert guardrail in skill


def test_memory_leak_skill_uses_conservative_classifications() -> None:
    skill = SKILL_PATH.read_text()

    for classification in (
        "strong leak candidate",
        "application retention",
        "framework lifecycle retention",
        "asynchronous free pending",
        "allocator/cache effect",
        "normal long-lived allocation",
        "inconclusive",
    ):
        assert f"`{classification}`" in skill

    assert "Do not use this category from end-of-trace survival alone." in skill
