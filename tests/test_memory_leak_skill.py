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
    assert "`top_n` truncation applies to dynamic callstack groups only" in skill
    assert "static and preexisting groups are always returned in full" in skill
    assert "Match representative blocks by identity" in skill


def test_memory_leak_skill_matches_current_preexisting_group_semantics() -> None:
    skill = SKILL_PATH.read_text()

    assert "`[preexisting live] allocEventId=-1`" in skill
    assert "[static] allocEventId=-1, freeEventId=-1" in skill
    assert "are excluded from both groups" not in skill
    assert "counts only blocks with `allocEventId != -1`" not in skill


def test_memory_leak_skill_quantifies_unattributed_pre_snapshot_memory() -> None:
    skill = SKILL_PATH.read_text()

    assert '"allocEventId":-1,"min_freeEventId"' in skill
    assert "no attributable callstack" in skill
    assert "pre-snapshot memory" in skill


def test_memory_leak_skill_pages_pre_snapshot_bucket_before_summing() -> None:
    skill = SKILL_PATH.read_text()

    assert '"order_by":"id","order_dir":"ASC","limit":100,"offset":<offset>' in skill
    assert "Page through every matching row before summing" in skill
    assert "start with offset `0`, increase it by `100`" in skill
    assert "A single `-n 100` page is a sample, not the full bucket" in skill
    assert "silently undercounts" in skill


def test_memory_leak_skill_offers_read_only_aggregate_for_exact_total() -> None:
    skill = SKILL_PATH.read_text()

    assert "read-only aggregate instead of paging" in skill
    assert "non-negative decimal integer matching `^[0-9]+$`" in skill
    assert "COALESCE(SUM(size), 0) AS size_bytes" in skill
    assert "WHERE allocEventId = -1 AND freeEventId >= <peak_active_event_id + 1>" in skill
    assert "no row limit applies" in skill
    assert "fall back to the paginated sum above" in skill

    guardrail = "two documented read-only aggregates that templates do not expose"
    assert guardrail in skill
    assert "only for the optional lifetime aggregate" not in skill
    assert "the freed-block lifetime baseline (Step 6)" in skill
    assert "the exact `[preexisting live]` total (Step 4)" in skill


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
