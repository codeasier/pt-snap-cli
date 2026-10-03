import json
import shlex
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
        "active_blocks_at_event",
        "preexisting_live",
        "freed_block_lifetime",
    ):
        assert f"--template-use {template}" in skill or f"--template-info {template}" in skill
    assert "pt-snap capabilities --json" in skill
    assert "pt-snap overview '<db_path>' --json" in skill


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
    assert "increase `top_n` instead of concluding from" in skill
    assert "static and preexisting groups are always returned in full" in skill
    assert "Match representative blocks by identity" in skill


def test_memory_leak_skill_matches_current_preexisting_group_semantics() -> None:
    skill = SKILL_PATH.read_text()

    assert "`[preexisting live] allocEventId=-1`" in skill
    assert "[static] allocEventId=-1, freeEventId=-1" in skill
    assert "are excluded from both groups" not in skill
    assert "counts only blocks with `allocEventId != -1`" not in skill


def test_memory_leak_step4_queries_both_identity_sets_with_bounded_json_pages() -> None:
    skill = SKILL_PATH.read_text()
    prerequisite, workflow = skill.split("## Diagnostic Workflow", 1)
    assert "`active_blocks_at_event`" in prerequisite
    step4 = workflow.split("### 4.", 1)[1].split("### 5.", 1)[0]
    commands = [
        shlex.split(line)
        for line in step4.splitlines()
        if line.startswith("pt-snap query") and "--template-use active_blocks_at_event" in line
    ]
    assert len(commands) == 2
    for command, event in zip(
        commands, ("<peak_active_event_id>", "<final_event_id>"), strict=True
    ):
        assert command[:5] == ["pt-snap", "query", "<db_path>", "--device", "<device_id>"]
        assert "--json" in command
        assert int(command[command.index("-n") + 1]) == 500
        params = json.loads(command[command.index("--params") + 1].replace(event, "42"))
        assert params == {
            "event_id": 42,
            "include_static": True,
            "min_size": 0,
            "order_by": "id",
            "order_dir": "ASC",
            "offset": 0,
        }
    for requirement in (
        "same database and the same device",
        "advance the `offset` parameter by that page's `returned` count",
        "Continue until `has_more=false`",
        "An offset page still has `truncated=true`",
        "collecting all pages from offset 0 through the terminal page",
        "exact pair `(id, allocEventId)`",
        "sample-only evidence",
        "Unmatched sample rows are not proven new or released",
        "Do not report a full-set survival rate or claim zero new blocks from samples",
        "Only after both complete sets are collected",
        "`matched = peak ∩ final`",
        "`new_at_end = final - peak`",
        "`released_from_peak = peak - final`",
        "Compute these separately per category",
        "`len(matched) / len(peak)`",
        "`len(matched) / len(final)`",
        "empty denominator as unavailable",
        "lifecycle checks in Step 5",
        "Check real `freeEventId` values",
        "not proof of a leak",
    ):
        assert requirement in step4


def test_memory_leak_skill_cross_checks_preexisting_bucket_exactly() -> None:
    skill = SKILL_PATH.read_text()

    assert "cannot express the `freeEventId IS NULL` case" in skill
    assert "--template-use preexisting_live" in skill
    assert '"event_id":<peak_active_event_id>' in skill
    assert "sqlite3 -readonly" not in skill
    assert "returns a single row" in skill
    assert "nothing is silently undercounted" in skill
    assert "--template-use freed_block_lifetime" in skill
    assert "Do not use the `sqlite3` CLI or hand-assembled SQL" in skill
    assert "`preexisting_live` (Step 4)" in skill
    assert "`freed_block_lifetime` (Step 6)" in skill


def test_memory_leak_skill_has_no_incomplete_bucket_scan() -> None:
    skill = SKILL_PATH.read_text()

    assert '"allocEventId":-1,"min_freeEventId"' not in skill
    assert "fall back to the paginated sum above" not in skill


def test_memory_leak_skill_keeps_result_listings_bounded() -> None:
    skill = SKILL_PATH.read_text()

    address_query = '"order_dir":"ASC"}\' -n 100'
    assert address_query in skill
    assert "-n 0` and other unlimited settings materialize" in skill
    assert "the `offset` parameter" in skill
    assert "never request unlimited rows from a query" in skill
    assert "has_more" in skill
    assert "--json" in skill
    assert "--exact-total" in skill


def test_memory_leak_skill_interprets_percent_column_as_byte_share() -> None:
    skill = SKILL_PATH.read_text()

    assert "share of included active bytes" in skill
    assert "active_memory_callstack_at_event` entry in `pt-snap capabilities --json" in skill
    assert "rather than inferring them from the column name" in skill
    assert "byte share (`size_bytes / total size_bytes`) despite its name" not in skill


def test_memory_leak_skill_records_reduced_prerequisite_probes() -> None:
    skill = " ".join(SKILL_PATH.read_text().split())

    assert "2 calls from cold, 1 with one reusable result, 0 with both" in skill
    assert "Record tool-call count and output bytes separately" in skill
    assert "Do not probe templates one-by-one with `--template-info`" in skill


def test_memory_leak_skill_recovers_missing_focus_with_sibling_candidates() -> None:
    skill = SKILL_PATH.read_text()
    normalized = " ".join(skill.split())

    assert "#### Missing focus target with sibling candidates" in skill
    assert (
        "A displayed path or exit code 0 from `pt-snap focus` does not mean " "the target is usable"
    ) in normalized
    assert "Do not auto-select by name, size, or mtime." in skill
    assert "Even a single candidate requires an explicit user choice." in skill
    assert "Before the user confirms a path, do not run diagnostic queries" in skill
    assert ("the next inspect step is `pt-snap metadata '<db_path>' --json`") in skill
    assert "Do not start with `pt-snap query`" in skill
    assert "do not inherit the focused device from the missing target" in skill
    assert "`unavailable` with reason `metadata_missing`" in skill
