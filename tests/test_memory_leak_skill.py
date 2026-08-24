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


def test_memory_leak_skill_quotes_paths_safely() -> None:
    skill = SKILL_PATH.read_text()

    assert "'<db_path>'" in skill
    assert '"<db_path>"' not in skill
    assert "Never place a substituted value inside double quotes" in skill
    assert "argument array" in skill
    assert "treat that value as untrusted input to quoting" in skill


def test_memory_leak_skill_has_no_unused_range_input() -> None:
    skill = SKILL_PATH.read_text()

    assert "An event range to investigate" not in skill
    assert "event range, final event ID" not in skill


def test_memory_leak_skill_reports_occupancy_with_identity_evidence() -> None:
    skill = SKILL_PATH.read_text()

    assert "occupancy comparison" in skill
    assert "not a block-identity survival test" in skill
    assert "`top_n` truncation" in skill
    assert "Match representative blocks by identity" in skill


def test_memory_leak_skill_quantifies_unattributed_pre_snapshot_memory() -> None:
    skill = SKILL_PATH.read_text()

    assert '"allocEventId":-1,"min_freeEventId"' in skill
    assert "no attributable callstack" in skill
    assert "pre-snapshot memory" in skill


def test_memory_leak_skill_keeps_result_listings_bounded() -> None:
    skill = SKILL_PATH.read_text()

    address_query = '"order_dir":"ASC"}\' -n 100'
    assert address_query in skill
    assert "-n 0` and other unlimited settings materialize" in skill
    assert "the `offset` parameter" in skill
    assert "never request unlimited rows from a query" in skill


def test_memory_leak_skill_interprets_percent_column_as_byte_share() -> None:
    skill = SKILL_PATH.read_text()

    assert "share of included active bytes" in skill
    assert "byte share (`size_bytes / total size_bytes`) despite its name" in skill
